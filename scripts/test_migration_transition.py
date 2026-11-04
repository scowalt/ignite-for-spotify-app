from dataclasses import replace
from pathlib import Path
import json
import multiprocessing
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fixtures.migration_transition import SqliteRuntime, catalogue, recovery_receipt
from migration_plan import prepare_transition
from migration_record import descriptor_summary
from migration_transition import MigrationTransition, MigrationTransitionRejected
from test_deployment_transaction import candidate


def interrupted_migration(workspace, mode):
    MigrationTransition(workspace).migrate(SqliteRuntime(workspace, mode), recovery_receipt())


class MigrationTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name) / ('c' * 64)
        self.workspace.mkdir(mode=0o700)
        self.runtime = SqliteRuntime(self.workspace)
        self.runtime.initialize()
        self.before = self.runtime.inspect_database(self.workspace)
        self.plan = prepare_transition(self.before, catalogue(1), catalogue(2))
        self.release = replace(candidate(), migrations=descriptor_summary(catalogue(2)), hangfire_sha256='f' * 64, migration_engine_sha256='e' * 64)
        self.transition = MigrationTransition(self.workspace)

    def test_verified_transition_is_durable_and_cannot_be_migrated_again(self):
        self.transition.prepare(self.release, self.plan)
        self.assertEqual(self.transition.migrate(self.runtime, recovery_receipt()), 'verified')
        reopened = MigrationTransition(self.workspace)
        self.assertEqual(reopened.status()['phase'], 'verified')
        self.assertEqual(reopened.migrate(self.runtime, recovery_receipt()), 'committed')
        self.assertEqual((self.workspace / 'events').read_text().splitlines().count('migrate'), 1)

    def test_noop_catalogue_never_executes_sql_and_remains_prior_compatible(self):
        plan = prepare_transition(self.before, catalogue(1), catalogue(1))
        release = replace(self.release, migrations=descriptor_summary(catalogue(1)))
        self.transition.prepare(release, plan)
        self.assertEqual(self.transition.migrate(self.runtime, recovery_receipt()), 'verified')
        self.assertEqual(self.transition.recover(self.runtime), 'unchanged')
        self.assertNotIn('migrate', (self.workspace / 'events').read_text().splitlines())

    def test_recovery_rechecks_an_earlier_unchanged_observation(self):
        self.transition.prepare(self.release, self.plan)
        self.assertEqual(self.transition.recover(self.runtime), 'unchanged')
        connection = sqlite3.connect(self.runtime.database)
        try:
            connection.execute('CREATE TABLE unexpected (id INTEGER)')
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(self.transition.recover(self.runtime), 'uncertain')

    def test_expiry_after_commit_never_admits_the_application_as_verified(self):
        clock = [time.time()]
        transition = MigrationTransition(self.workspace, clock=lambda: clock[0])
        transition.prepare(self.release, self.plan)
        class SlowRuntime(SqliteRuntime):
            def migrate_database(self, plan, workspace):
                super().migrate_database(plan, workspace)
                clock[0] += 301
        self.assertEqual(transition.migrate(SlowRuntime(self.workspace), recovery_receipt()), 'committed')
        self.assertEqual(transition.status()['phase'], 'committed')

    def test_exception_after_commit_is_not_mistaken_for_a_rolled_back_batch(self):
        self.transition.prepare(self.release, self.plan)
        self.runtime.mode = 'fail-after-commit'
        self.assertEqual(self.transition.migrate(self.runtime, recovery_receipt()), 'committed')
        state = MigrationTransition(self.workspace).status()
        self.assertEqual(state['phase'], 'committed')
        self.assertEqual(state['observed']['schema_sha256'], catalogue(2)['schema_sha256'])
        self.assertNotIn('fixture-private-value', json.dumps(state))

    def test_failed_batch_can_only_be_reported_unchanged_after_stopping_and_settlement(self):
        self.transition.prepare(self.release, self.plan)
        self.runtime.mode = 'rollback'
        self.assertEqual(self.transition.migrate(self.runtime, recovery_receipt()), 'unchanged')
        self.assertEqual(self.transition.status()['observed'], self.before)
        self.assertEqual((self.workspace / 'events').read_text().splitlines()[-4:], ['stop', 'quiesced', 'settle', 'inspect'])

    def killed_transition(self, mode):
        self.transition.prepare(self.release, self.plan)
        context = multiprocessing.get_context('fork')
        process = context.Process(target=interrupted_migration, args=(self.workspace, mode))
        process.start()
        try:
            deadline = time.monotonic() + 10
            while not (self.workspace / 'ready').exists() and process.is_alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.workspace / 'ready').exists())
            self.assertEqual(self.transition.status()['phase'], 'migration_started')
            self.assertEqual(MigrationTransition(self.workspace).migrate(self.runtime, recovery_receipt()), 'busy')
            self.assertEqual(MigrationTransition(self.workspace).recover(self.runtime), 'busy')
            process.kill()
            process.join(5)
            self.assertFalse(process.is_alive())
        finally:
            if process.is_alive():
                process.kill()
            process.join(5)
            process.close()

    def test_killed_uncommitted_writer_is_settled_without_replaying_sql(self):
        self.killed_transition('hold-before-commit')
        self.assertTrue(self.runtime.database.with_name('application.db-journal').exists())
        with self.assertRaises(sqlite3.OperationalError):
            self.runtime.inspect_database(self.workspace)
        reopened = MigrationTransition(self.workspace)
        self.assertEqual(reopened.recover(self.runtime), 'unchanged')
        self.assertEqual(reopened.status()['observed'], self.before)
        self.assertEqual((self.workspace / 'events').read_text().splitlines().count('migrate'), 1)

    def test_killed_controller_after_commit_preserves_committed_outcome_and_never_replays(self):
        self.killed_transition('hold-after-commit')
        reopened = MigrationTransition(self.workspace)
        self.assertEqual(reopened.recover(self.runtime), 'committed')
        self.assertEqual(reopened.status()['observed']['schema_sha256'], catalogue(2)['schema_sha256'])
        self.assertEqual(reopened.migrate(self.runtime, recovery_receipt()), 'committed')
        self.assertEqual((self.workspace / 'events').read_text().splitlines().count('migrate'), 1)

    def test_failed_writer_shutdown_cannot_read_or_settle_and_is_latched(self):
        self.transition.prepare(self.release, self.plan)
        self.runtime.mode = 'stop-fails'
        (self.workspace / 'events').write_text('')
        self.assertEqual(self.transition.recover(self.runtime), 'blocked')
        self.assertEqual(self.transition.recover(self.runtime), 'blocked')
        self.assertEqual((self.workspace / 'events').read_text().splitlines(), ['stop'])
        self.assertIsNone(self.transition.status()['observed'])

    def test_fresh_verified_backup_with_reserved_time_is_required_before_sql(self):
        self.transition.prepare(self.release, self.plan)
        for change in [{'restore_verified': False}, {'snapshot_bytes': 256 * 1024**2 + 1},
                       {'scratch_bytes': 1024**3 + 1}, {'additional_remote_bytes': 512 * 1024**2 + 1},
                       {'snapshot_time': '2000-01-01T00:00:00+00:00'}, {'extra': 'not-for-state'}]:
            with self.subTest(change=change):
                with self.assertRaises(MigrationTransitionRejected):
                    self.transition.migrate(self.runtime, recovery_receipt() | change)
                self.assertEqual(self.transition.status()['phase'], 'prepared')
        clock = time.time()
        delayed = MigrationTransition(self.workspace, clock=lambda: clock + 121)
        with self.assertRaises(MigrationTransitionRejected):
            delayed.migrate(self.runtime, recovery_receipt())
        self.assertEqual(self.runtime.inspect_database(self.workspace), self.before)
        self.assertNotIn('migrate', (self.workspace / 'events').read_text().splitlines())

    def test_unknown_observed_history_stays_uncertain_and_never_becomes_rollback_permission(self):
        self.transition.prepare(self.release, self.plan)
        connection = sqlite3.connect(self.runtime.database)
        try:
            connection.execute('CREATE TABLE unexpected (id INTEGER)')
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(self.transition.migrate(self.runtime, recovery_receipt()), 'uncertain')
        self.assertEqual(self.transition.recover(self.runtime), 'uncertain')
        self.assertNotIn('migrate', (self.workspace / 'events').read_text().splitlines())

    def test_state_and_release_binding_refuse_overwrite_and_untrusted_metadata(self):
        with self.assertRaises(MigrationTransitionRejected):
            self.transition.prepare(replace(self.release, artifact_digest='sha256:' + 'd' * 64), self.plan)
        self.assertFalse((self.workspace / 'migration.json').exists())
        with self.assertRaises(MigrationTransitionRejected):
            self.transition.prepare(replace(self.release, migrations=descriptor_summary(catalogue(1))), self.plan)
        self.transition.prepare(self.release, self.plan)
        with self.assertRaises(MigrationTransitionRejected):
            self.transition.prepare(self.release, self.plan)
        path = self.workspace / 'migration.json'
        original = path.read_bytes()
        for payload in [b'{}', b'{"schema":1,"schema":1}', b'x' * (8 * 1024**2 + 1)]:
            path.write_bytes(payload)
            with self.assertRaises(MigrationTransitionRejected):
                self.transition.recover(self.runtime)
        path.write_bytes(original)
        os.chmod(path, 0o644)
        with self.assertRaises(MigrationTransitionRejected):
            self.transition.status()
        os.chmod(path, 0o600)
        path.unlink()
        path.symlink_to(self.workspace / 'absent')
        with self.assertRaises(MigrationTransitionRejected):
            self.transition.prepare(self.release, self.plan)
        with self.assertRaises(MigrationTransitionRejected):
            self.transition.status()

    def test_failed_durable_intent_write_is_not_lock_contention_or_permission_to_run_sql(self):
        self.transition.prepare(self.release, self.plan)
        with patch('os.fsync', side_effect=BlockingIOError('fixture filesystem failure')):
            with self.assertRaises(BlockingIOError):
                self.transition.migrate(self.runtime, recovery_receipt())
        self.assertEqual(self.transition.status()['phase'], 'prepared')
        self.assertEqual(self.runtime.inspect_database(self.workspace), self.before)
        self.assertNotIn('migrate', (self.workspace / 'events').read_text().splitlines())


if __name__ == '__main__':
    unittest.main()
