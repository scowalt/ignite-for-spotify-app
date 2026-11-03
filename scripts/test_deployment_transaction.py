from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import multiprocessing
import os
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment_transaction import Deployment, StateRejected
from release_record import ReleaseRecord
from migration_record import MigrationSummary


def image_set(character):
    return {name: 'ghcr.io/scowalt/ignite-for-spotify-app/' + name + '@sha256:' + character * 64
            for name in ['backend', 'backup', 'frontend']}


def candidate(character='c', number=43):
    return ReleaseRecord('d' * 40, 123, 1, number, 'b' * 64, tuple(sorted(image_set(character).items())), 'sha256:' + character * 64)


class InterruptedProcess(BaseException):
    pass


class RuntimeFixture:
    def __init__(self):
        self.images = image_set('a')
        self.recovery_verified = False
        self.unrelated_identity = 'original'
        self.backup_running = True
        self.owned_plaintext = False
        self.fail_dependents = False
        self.fail_backend_health = False
        self.interrupt_dependents = False
        self.rollback_available = True
        self.fail_rollback = False
        self.interrupt_rollback = False
        self.during_preflight = None
        self.fail_final_cleanup = False
        self.recovery_override = {}
        self.require_clean_switch = False
        self.during_cleanup = None

    def preflight(self, release, prior, workspace):
        if self.during_preflight:
            self.during_preflight()
        if self.images != prior['images']:
            raise RuntimeError('fixture runtime drift')

    def backup(self, workspace):
        self.backup_running = False
        self.owned_plaintext = True
        self.recovery_verified = True
        return {'snapshot_id': 'e' * 64, 'repository_id': 'f' * 64, 'snapshot_bytes': 1000,
                'snapshot_time': datetime.now(timezone.utc).isoformat(),
                'scratch_bytes': 3000, 'additional_remote_bytes': 500, 'restore_verified': True,
                **self.recovery_override}

    def switch_backend(self, release, workspace):
        if not self.recovery_verified or (self.require_clean_switch and self.owned_plaintext):
            raise RuntimeError('fixture unsafe mutation')
        self.images['backend'] = dict(release.images)['backend']
        if self.fail_backend_health:
            raise RuntimeError('fixture backend readiness failed')

    def switch_dependents(self, release, workspace):
        if self.interrupt_dependents:
            raise InterruptedProcess()
        if self.fail_dependents:
            raise RuntimeError('fixture-sensitive-error-value')
        self.images.update(dict(release.images))
        self.backup_running = True

    def verify(self, images, workspace):
        if self.images != images or not self.backup_running:
            raise RuntimeError('fixture unhealthy runtime')

    def rollback(self, prior, workspace):
        if not self.rollback_available:
            raise RuntimeError('fixture repeated rollback')
        self.rollback_available = False
        if self.interrupt_rollback:
            raise InterruptedProcess()
        if self.fail_rollback:
            raise RuntimeError('fixture rollback failed')
        self.images = deepcopy(prior['images'])
        self.backup_running = True

    def cleanup(self, workspace):
        if self.during_cleanup:
            self.during_cleanup()
        if self.fail_final_cleanup and self.images == image_set('c'):
            raise RuntimeError('fixture cleanup failed')
        self.owned_plaintext = False


def blocked_preflight(root, ready):
    runtime = RuntimeFixture()
    runtime.during_preflight = lambda: (ready.set(), time.sleep(60))
    Deployment(root).run(candidate(), runtime)


class DeploymentTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'deployment'
        self.runtime = RuntimeFixture()
        self.deployment = Deployment(self.root)
        self.active = {'source_sha': 'a' * 40, 'images': image_set('a'), 'order': [42, 1], 'artifact_digest': None}
        self.deployment.bootstrap(self.active, 'b' * 64)

    def test_legacy_transactions_cannot_ignore_migration_metadata(self):
        before = self.deployment.status()
        release = replace(candidate(), migrations=MigrationSummary(1, '1' * 64, '2' * 64, '3' * 64, 2), hangfire_sha256='4' * 64)
        with self.assertRaises(StateRejected):
            self.deployment.run(release, self.runtime)
        self.assertEqual(self.deployment.status(), before)
        self.assertEqual(self.runtime.images, image_set('a'))
        self.assertTrue(self.runtime.backup_running)

    def test_success_is_durable_and_polling_does_not_repeat_the_deployment(self):
        release = candidate()
        self.assertEqual(self.deployment.run(release, self.runtime), 'deployed')
        reopened = Deployment(self.root)
        status = reopened.status()
        self.assertEqual(status['active']['images'], image_set('c'))
        self.assertEqual(status['high_water_order'], [43, 1])
        self.assertIsNone(status['transaction'])
        self.assertEqual(reopened.run(release, self.runtime), 'unchanged')
        self.assertEqual(self.runtime.images, image_set('c'))
        self.assertEqual(self.runtime.unrelated_identity, 'original')
        self.assertFalse(self.runtime.owned_plaintext)

    def test_failed_partial_update_rolls_back_once_and_stays_fenced_after_restart(self):
        self.runtime.fail_dependents = True
        release = candidate()
        self.assertEqual(self.deployment.run(release, self.runtime), 'rolled_back')
        reopened = Deployment(self.root)
        status = reopened.status()
        self.assertEqual(status['active'], self.active)
        self.assertEqual(status['high_water_order'], [43, 1])
        self.assertEqual(reopened.run(release, self.runtime), 'failed_release_fenced')
        self.assertEqual(self.runtime.images, image_set('a'))
        self.assertTrue(self.runtime.backup_running)
        self.assertFalse(self.runtime.owned_plaintext)
        self.assertNotIn('fixture-sensitive-error-value', str(status))

    def test_interrupted_partial_update_recovers_without_fetching_a_new_release(self):
        self.runtime.interrupt_dependents = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(candidate(), self.runtime)
        reopened = Deployment(self.root)
        self.assertEqual(reopened.run(None, self.runtime), 'rolled_back')
        self.assertEqual(reopened.status()['active'], self.active)
        self.assertEqual(reopened.run(candidate(), self.runtime), 'failed_release_fenced')
        self.assertEqual(self.runtime.images, image_set('a'))
        self.assertTrue(self.runtime.backup_running)
        self.assertFalse(self.runtime.owned_plaintext)

    def test_failed_rollback_cleans_owned_plaintext_and_requires_manual_recovery(self):
        self.runtime.fail_dependents = True
        self.runtime.fail_rollback = True
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'manual_recovery')
        self.assertFalse(self.runtime.owned_plaintext)
        reopened = Deployment(self.root)
        self.assertEqual(reopened.run(None, self.runtime), 'manual_recovery')
        self.assertEqual(reopened.run(candidate('d', 44), self.runtime), 'manual_recovery')
        self.assertEqual(reopened.status()['transaction']['phase'], 'rollback_started')
        self.assertEqual(reopened.status()['active'], self.active)

    def test_concurrent_invocation_cannot_enter_a_second_transaction(self):
        observed = []
        self.runtime.during_preflight = lambda: observed.append(Deployment(self.root).run(candidate('d', 44), RuntimeFixture()))
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'deployed')
        self.assertEqual(observed, ['busy'])
        self.assertEqual(self.deployment.status()['active']['images'], image_set('c'))

    def test_committed_release_survives_cleanup_failure_without_redeployment(self):
        self.runtime.fail_final_cleanup = True
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'cleanup_required')
        self.assertEqual(self.deployment.status()['active']['images'], image_set('c'))
        self.runtime.fail_final_cleanup = False
        self.runtime.fail_dependents = True
        reopened = Deployment(self.root)
        self.assertEqual(reopened.run(None, self.runtime), 'deployed')
        self.assertFalse(self.runtime.owned_plaintext)
        self.assertIsNone(reopened.status()['transaction'])
        self.assertTrue(self.runtime.rollback_available)

    def test_unreviewed_state_and_contract_inputs_are_refused_before_runtime_actions(self):
        invalid = Deployment(Path(self.temporary.name) / 'invalid')
        with self.assertRaises(StateRejected):
            invalid.bootstrap({**self.active, 'secret': 'not-state-metadata'}, 'b' * 64)
        wrong_contract = ReleaseRecord('d' * 40, 123, 1, 43, '0' * 64, tuple(sorted(image_set('c').items())), 'sha256:' + 'c' * 64)
        with self.assertRaises(StateRejected):
            self.deployment.run(wrong_contract, self.runtime)
        self.assertEqual(self.deployment.status()['active'], self.active)
        self.assertFalse(self.runtime.recovery_verified)
        self.assertTrue(self.runtime.rollback_available)
        self.assertTrue(self.runtime.backup_running)

    def test_preflight_drift_never_overwrites_unrecognized_running_images(self):
        self.runtime.images = image_set('9')
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'preflight_failed')
        self.assertEqual(self.runtime.images, image_set('9'))
        self.assertTrue(self.runtime.rollback_available)
        self.assertFalse(self.runtime.recovery_verified)
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'failed_release_fenced')

    def test_untrusted_filesystem_state_is_rejected_instead_of_reinitialized(self):
        original = self.deployment.status()
        state_file = self.root / 'state.json'
        malformed = [b'{}', b'{"schema":1,"schema":1}', b'x' * (2 * 1024**2 + 1),
                     json.dumps({**original, 'high_water_order': [1, 1]}).encode(),
                     json.dumps({**original, 'unexpected': 'not-allowed'}).encode()]
        for raw in malformed:
            with self.subTest(size=len(raw)):
                state_file.write_bytes(raw)
                with self.assertRaises(StateRejected):
                    self.deployment.run(candidate(), self.runtime)
        state_file.unlink()
        target = Path(self.temporary.name) / 'external-state.json'
        target.write_text(json.dumps(original))
        state_file.symlink_to(target)
        with self.assertRaises(StateRejected):
            self.deployment.status()
        self.assertFalse(self.runtime.recovery_verified)
        self.assertTrue(self.runtime.rollback_available)
        self.assertEqual(self.runtime.images, image_set('a'))
        os.chmod(self.root, 0o755)
        with self.assertRaises(StateRejected):
            Deployment(self.root)

    def test_only_fresh_verified_bounded_recovery_receipts_allow_image_mutations(self):
        changes = [{'restore_verified': False}, {'snapshot_bytes': 256 * 1024**2 + 1},
                   {'scratch_bytes': 1024**3 + 1}, {'additional_remote_bytes': 512 * 1024**2 + 1},
                   {'snapshot_time': '2000-01-01T00:00:00+00:00'}, {'secret': 'not-for-state'}]
        for number, change in enumerate(changes):
            with self.subTest(change=change):
                runtime = RuntimeFixture()
                runtime.recovery_override = change
                deployment = Deployment(Path(self.temporary.name) / str(number))
                deployment.bootstrap(self.active, 'b' * 64)
                self.assertEqual(deployment.run(candidate(), runtime), 'rolled_back')
                self.assertEqual(runtime.images, image_set('a'))
                self.assertTrue(runtime.backup_running)
                self.assertFalse(runtime.owned_plaintext)
                self.assertEqual(deployment.status()['active'], self.active)
                self.assertNotIn('not-for-state', str(deployment.status()))

    def test_completed_attempt_retains_recovery_and_identity_evidence(self):
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'deployed')
        report = Deployment(self.root).attempt(candidate().artifact_digest)
        self.assertEqual(report['outcome'], 'deployed')
        transaction = report['state']['transaction']
        self.assertEqual(transaction['recovery']['snapshot_id'], 'e' * 64)
        self.assertEqual(transaction['candidate']['images'], image_set('c'))
        self.assertEqual(transaction['prior']['images'], image_set('a'))
        self.assertEqual(report['state']['high_water_order'], [43, 1])

    def test_owned_plaintext_is_removed_before_application_images_change(self):
        self.runtime.require_clean_switch = True
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'deployed')
        self.assertEqual(self.runtime.images, image_set('c'))

    def test_killed_process_releases_the_lock_and_is_not_blindly_retried(self):
        context = multiprocessing.get_context('fork')
        ready = context.Event()
        process = context.Process(target=blocked_preflight, args=(self.root, ready))
        process.start()
        try:
            self.assertTrue(ready.wait(5))
            self.assertEqual(self.deployment.run(candidate('d', 44), self.runtime), 'busy')
            process.kill()
            process.join(5)
            self.assertFalse(process.is_alive())
            self.assertEqual(self.deployment.run(None, self.runtime), 'preflight_failed')
            self.assertEqual(self.deployment.run(candidate(), self.runtime), 'failed_release_fenced')
            self.assertEqual(self.runtime.images, image_set('a'))
            self.assertTrue(self.runtime.rollback_available)
        finally:
            if process.is_alive():
                process.kill()
            process.join(5)
            process.close()

    def test_backend_health_failure_is_audited_before_dependent_images_change(self):
        self.runtime.fail_backend_health = True
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'rolled_back')
        report = self.deployment.attempt(candidate().artifact_digest)
        self.assertEqual(report['state']['transaction']['failure_phase'], 'switch_started')
        self.assertEqual(report['state']['transaction']['recovery']['snapshot_id'], 'e' * 64)
        self.assertEqual(self.runtime.images, image_set('a'))

    def test_pending_recovery_takes_priority_over_an_unreviewed_new_contract(self):
        self.runtime.interrupt_dependents = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(candidate(), self.runtime)
        unreviewed = ReleaseRecord('f' * 40, 124, 1, 44, '0' * 64, tuple(sorted(image_set('d').items())), 'sha256:' + 'd' * 64)
        self.assertEqual(Deployment(self.root).run(unreviewed, self.runtime), 'rolled_back')
        self.assertEqual(self.runtime.images, image_set('a'))

    def test_expired_backup_after_slow_cleanup_does_not_allow_image_mutation(self):
        clock = [time.time()]
        self.runtime.during_cleanup = lambda: clock.__setitem__(0, clock[0] + 600)
        with patch('time.time', side_effect=lambda: clock[0]):
            self.assertEqual(self.deployment.run(candidate(), self.runtime), 'rolled_back')
        self.assertEqual(self.runtime.images, image_set('a'))

    def test_filesystem_failure_is_not_misreported_as_lock_contention(self):
        with patch('os.fsync', side_effect=BlockingIOError('fixture disk failure')):
            with self.assertRaises(BlockingIOError):
                self.deployment.run(candidate(), self.runtime)
        self.assertFalse(self.runtime.recovery_verified)
        self.assertEqual(self.deployment.status()['active'], self.active)

    def test_bootstrap_never_replaces_an_existing_dangling_state_link(self):
        other = Deployment(Path(self.temporary.name) / 'dangling')
        link = other.root / 'state.json'
        link.symlink_to(Path(self.temporary.name) / 'absent-target')
        with self.assertRaises(StateRejected):
            other.bootstrap(self.active, 'b' * 64)
        self.assertTrue(link.is_symlink())

    def test_full_failure_fence_stops_before_an_unrecordable_attempt(self):
        state = self.deployment.status()
        state['failed_digests'] = ['sha256:' + format(number, '064x') for number in range(4096)]
        (self.root / 'state.json').write_text(json.dumps(state))
        self.assertEqual(self.deployment.run(candidate(), self.runtime), 'manual_recovery')
        self.assertFalse(self.runtime.recovery_verified)
        self.assertTrue(self.runtime.rollback_available)
        self.assertEqual(self.runtime.images, image_set('a'))

    def test_interrupted_rollback_is_never_restarted_by_polling(self):
        self.runtime.fail_dependents = True
        self.runtime.interrupt_rollback = True
        with self.assertRaises(InterruptedProcess):
            self.deployment.run(candidate(), self.runtime)
        self.assertEqual(Deployment(self.root).run(None, self.runtime), 'manual_recovery')
        self.assertEqual(Deployment(self.root).run(candidate('d', 44), self.runtime), 'manual_recovery')
        self.assertFalse(self.runtime.owned_plaintext)
        self.assertEqual(self.deployment.status()['transaction']['phase'], 'rollback_started')


if __name__ == '__main__':
    unittest.main()
