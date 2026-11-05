from dataclasses import asdict, replace
import hashlib
import json
import multiprocessing
import time
from pathlib import Path
import tempfile
import unittest

from deployment_transaction import Deployment, StateRejected
from test_deployment_transaction import InterruptedProcess, RuntimeFixture, candidate, image_set
from fixtures.migration_transition import SqliteRuntime, catalogue
from migration_plan import prepare_transition
from migration_record import descriptor_summary


POLICY = {'runtime_contract_sha256': '1' * 64, 'engine_sha256': '2' * 64,
          'hangfire_sha256': '3' * 64, 'legacy_schema_sha256': '4' * 64}


def state_hash(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class MigrationRuntimeFixture(RuntimeFixture):
    def __init__(self, volume):
        super().__init__()
        self.sql = SqliteRuntime(volume)
        self.sql.initialize(journal=False)
        self.backend_running = True
        self.target_count = 1
        self.legacy_schema = catalogue(1)['baseline_schema_sha256']

    def preflight(self, release, prior, workspace):
        super().preflight(release, prior, workspace)
        before = self.sql.inspect_database(workspace)
        previous = None if before['history'] is None else catalogue(len(before['history']))
        return prepare_transition(before, previous, catalogue(self.target_count),
                                  legacy_schema_sha256=self.legacy_schema if previous is None else None)

    def quiesce(self, workspace):
        self.backend_running = self.backup_running = False

    def require_quiesced(self, workspace):
        if self.backend_running or self.backup_running:
            raise RuntimeError('fixture writers not quiesced')
        self.sql.require_quiesced(workspace)

    def backup(self, workspace):
        self.require_quiesced(workspace)
        return super().backup(workspace)

    def inspect_database(self, workspace):
        return self.sql.inspect_database(workspace)

    def inspect_stopped_database(self, workspace):
        self.require_quiesced(workspace)
        return self.sql.inspect_stopped_database(workspace)

    def migrate_database(self, plan, workspace):
        self.require_quiesced(workspace)
        return self.sql.migrate_database(plan, workspace)

    def stop_database_writers(self, workspace):
        self.sql.stop_database_writers(workspace)
        self.quiesce(workspace)

    def stop_migration_writer(self, workspace):
        self.sql.stop_migration_writer(workspace)

    def settle_database(self, workspace):
        self.require_quiesced(workspace)
        self.sql.settle_database(workspace)

    def switch_backend(self, release, workspace):
        self.require_quiesced(workspace)
        self.backend_running = True
        super().switch_backend(release, workspace)

    def verify(self, images, workspace):
        if not self.backend_running:
            raise RuntimeError('fixture backend unavailable')
        super().verify(images, workspace)

    def rollback(self, prior, workspace):
        self.require_quiesced(workspace)
        super().rollback(prior, workspace)
        self.backend_running = True


def run_migration_process(root, release, runtime):
    Deployment(root).run(release, runtime)


class MigrationDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'deployment'
        self.deployment = Deployment(self.root)
        self.active = {'source_sha': 'a' * 40, 'images': image_set('a'), 'order': [42, 1], 'artifact_digest': None}
        self.deployment.bootstrap(self.active, 'b' * 64)

    def migration_case(self):
        volume = Path(self.temporary.name) / 'volume'
        volume.mkdir()
        runtime = MigrationRuntimeFixture(volume)
        policy = POLICY | {'legacy_schema_sha256': runtime.legacy_schema}
        self.deployment.upgrade_migrations('d' * 64, policy, expected_state_sha256=state_hash(self.deployment.status()))
        release = replace(candidate(), contract_sha256='d' * 64, migrations=descriptor_summary(catalogue(1)),
                          migration_engine_sha256=policy['engine_sha256'], hangfire_sha256=policy['hangfire_sha256'])
        return runtime, release

    def test_read_only_check_holds_global_lock_and_cannot_enter_recovery(self):
        runtime, release = self.migration_case()
        before = self.deployment.status()
        outcomes = []
        runtime.during_preflight = lambda: outcomes.append(Deployment(self.root).run(release, runtime))
        self.assertEqual(self.deployment.check(release, runtime), 'verified_without_deployment')
        self.assertEqual(outcomes, ['busy'])
        self.assertEqual(self.deployment.status(), before)
        self.assertTrue(runtime.backend_running and runtime.backup_running)
        self.assertFalse(runtime.recovery_verified)
        runtime.during_preflight = None
        runtime.interrupt_dependents = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(release, runtime)
        pending = self.deployment.status()
        with self.assertRaises(StateRejected):
            self.deployment.check(release, runtime)
        self.assertEqual(self.deployment.status(), pending)

    def test_baseline_adoption_commits_only_after_quiescence_backup_and_healthy_images(self):
        runtime, release = self.migration_case()
        self.assertEqual(self.deployment.run(release, runtime), 'deployed')
        state = Deployment(self.root).status()
        self.assertEqual(state['active']['images'], dict(release.images))
        self.assertEqual(state['active_migrations'], asdict(release.migrations))
        self.assertIsNone(state['transaction'])
        self.assertTrue(runtime.backend_running and runtime.backup_running)
        self.assertFalse(runtime.owned_plaintext)
        self.assertEqual(len(runtime.inspect_database(None)['history']), 1)
        self.assertEqual(Deployment(self.root).run(release, runtime), 'unchanged')

    def test_committed_adoption_health_failure_stops_for_forward_fix_without_prior_image(self):
        runtime, release = self.migration_case()
        runtime.fail_backend_health = True
        self.assertEqual(self.deployment.run(release, runtime), 'manual_recovery')
        state = self.deployment.status()
        self.assertEqual(state['active'], self.active)
        self.assertEqual(state['transaction']['phase'], 'manual_recovery')
        self.assertEqual(state['transaction']['failure_phase'], 'switch_started')
        self.assertTrue(runtime.rollback_available)
        self.assertFalse(runtime.backend_running or runtime.backup_running)
        self.assertFalse(runtime.owned_plaintext)
        self.assertEqual(len(runtime.inspect_database(None)['history']), 1)
        self.assertEqual(Deployment(self.root).run(None, runtime), 'manual_recovery')

    def test_noop_schema_health_failure_permits_one_verified_prior_image_rollback(self):
        runtime, release = self.migration_case()
        self.assertEqual(self.deployment.run(release, runtime), 'deployed')
        previous = self.deployment.status()['active']
        replacement = replace(release, run_number=44, images=tuple(image_set('d').items()), artifact_digest='sha256:' + 'd' * 64)
        runtime.fail_backend_health = True
        self.assertEqual(self.deployment.run(replacement, runtime), 'rolled_back')
        self.assertEqual(self.deployment.status()['active'], previous)
        self.assertFalse(runtime.rollback_available)
        self.assertTrue(runtime.backend_running and runtime.backup_running)
        self.assertEqual(self.deployment.run(replacement, runtime), 'failed_release_fenced')
        self.assertEqual(self.deployment.attempt(replacement.artifact_digest)['outcome'], 'rolled_back')

    def test_committed_schema_expansion_never_restarts_an_older_catalogue(self):
        runtime, release = self.migration_case()
        self.assertEqual(self.deployment.run(release, runtime), 'deployed')
        runtime.target_count = 2
        replacement = replace(release, run_number=44, images=tuple(image_set('d').items()), artifact_digest='sha256:' + 'd' * 64,
                              migrations=descriptor_summary(catalogue(2)))
        runtime.interrupt_dependents = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(replacement, runtime)
        self.assertEqual(Deployment(self.root).run(None, runtime), 'manual_recovery')
        self.assertEqual(len(runtime.inspect_database(None)['history']), 2)
        self.assertTrue(runtime.rollback_available)
        self.assertFalse(runtime.backend_running or runtime.backup_running)

    def test_killed_outer_controller_does_not_replay_an_uncommitted_migration(self):
        runtime, release = self.migration_case()
        self.assertEqual(self.deployment.run(release, runtime), 'deployed')
        runtime.target_count = 2
        runtime.sql.mode = 'hold-before-commit'
        replacement = replace(release, run_number=44, images=tuple(image_set('d').items()), artifact_digest='sha256:' + 'd' * 64,
                              migrations=descriptor_summary(catalogue(2)))
        process = multiprocessing.get_context('fork').Process(target=run_migration_process, args=(self.root, replacement, runtime))
        process.start()
        try:
            deadline = time.monotonic() + 10
            while not (runtime.sql.workspace / 'ready').exists() and process.is_alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((runtime.sql.workspace / 'ready').exists())
            self.assertEqual(self.deployment.status()['transaction']['phase'], 'migration_started')
            self.assertEqual(self.deployment.run(None, runtime), 'busy')
            process.kill()
            process.join(5)
            self.assertFalse(process.is_alive())
            self.assertEqual(Deployment(self.root).run(None, runtime), 'rolled_back')
            self.assertEqual(len(runtime.inspect_database(None)['history']), 1)
            self.assertEqual((runtime.sql.workspace / 'events').read_text().splitlines().count('migrate'), 2)
        finally:
            if process.is_alive():
                process.kill()
            process.join(5)
            process.close()

    def test_policy_and_prior_catalogue_mismatches_fail_before_quiescence(self):
        runtime, release = self.migration_case()
        before = self.deployment.status()
        for changes in [{'migration_engine_sha256': 'f' * 64}, {'hangfire_sha256': 'f' * 64}, {'migrations': None}]:
            with self.assertRaises(StateRejected):
                self.deployment.run(replace(release, **changes), runtime)
            self.assertEqual(self.deployment.status(), before)
        runtime.legacy_schema = '9' * 64
        self.assertEqual(self.deployment.run(release, runtime), 'preflight_failed')
        self.assertTrue(runtime.backend_running and runtime.backup_running)
        self.assertFalse(runtime.recovery_verified)

    def test_committed_outer_state_retries_cleanup_without_redeploying_or_migrating(self):
        runtime, release = self.migration_case()
        runtime.fail_final_cleanup = True
        self.assertEqual(self.deployment.run(release, runtime), 'cleanup_required')
        self.assertEqual(self.deployment.status()['transaction']['phase'], 'committed')
        runtime.fail_final_cleanup = False
        runtime.fail_backend_health = True
        self.assertEqual(Deployment(self.root).run(None, runtime), 'deployed')
        self.assertEqual((runtime.sql.workspace / 'events').read_text().splitlines().count('migrate'), 1)
        self.assertTrue(runtime.rollback_available)

    def test_interrupted_compatible_rollback_is_not_repeated_by_polling(self):
        runtime, release = self.migration_case()
        self.assertEqual(self.deployment.run(release, runtime), 'deployed')
        replacement = replace(release, run_number=44, images=tuple(image_set('d').items()), artifact_digest='sha256:' + 'd' * 64)
        runtime.fail_backend_health = True
        runtime.interrupt_rollback = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(replacement, runtime)
        self.assertEqual(self.deployment.status()['transaction']['phase'], 'rollback_started')
        self.assertEqual(Deployment(self.root).run(None, runtime), 'manual_recovery')
        self.assertFalse(runtime.rollback_available)

    def test_upgrade_rejects_stale_snapshot_or_pending_transaction_without_mutation(self):
        before = self.deployment.status()
        with self.assertRaises(StateRejected):
            self.deployment.upgrade_migrations('d' * 64, POLICY, expected_state_sha256='0' * 64)
        self.assertEqual(self.deployment.status(), before)
        runtime = RuntimeFixture()
        runtime.interrupt_dependents = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(candidate(), runtime)
        pending = self.deployment.status()
        with self.assertRaises(StateRejected):
            self.deployment.upgrade_migrations('d' * 64, POLICY, expected_state_sha256=state_hash(pending))
        self.assertEqual(self.deployment.status(), pending)

    def test_explicit_upgrade_preserves_active_release_and_replay_failure_fences(self):
        before = self.deployment.status()
        before['high_water_order'] = [50, 1]
        before['failed_digests'] = ['sha256:' + 'c' * 64]
        (self.root / 'state.json').write_text(json.dumps(before))
        self.deployment.upgrade_migrations('d' * 64, POLICY, expected_state_sha256=state_hash(before))
        after = Deployment(self.root).status()
        self.assertEqual(after['schema'], 2)
        self.assertEqual(after['migration_policy'], POLICY)
        self.assertEqual(after['contract_sha256'], 'd' * 64)
        self.assertIsNone(after['active_migrations'])
        for field in ['active', 'high_water_order', 'failed_digests', 'transaction']:
            self.assertEqual(after[field], before[field])
        with self.assertRaises(StateRejected):
            self.deployment.upgrade_migrations('d' * 64, POLICY, expected_state_sha256=state_hash(after))


if __name__ == '__main__':
    unittest.main()
