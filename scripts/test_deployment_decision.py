import unittest

from deployment_decision import decide_deployment


class DeploymentDecisionTests(unittest.TestCase):
    def test_an_already_active_release_does_not_repeat_a_deployment(self):
        result = decide_deployment(
            {'artifact_digest': 'sha256:' + 'a' * 64, 'order': [42, 1]},
            {'artifact_digest': 'sha256:' + 'a' * 64, 'order': [42, 1]},
            [], None,
        )
        self.assertEqual(result, 'unchanged')

    def test_failed_or_non_forward_releases_do_not_repeat_mutations(self):
        active = {'artifact_digest': 'sha256:' + 'a' * 64, 'order': [42, 2]}
        candidate = {'artifact_digest': 'sha256:' + 'b' * 64, 'order': [43, 1]}
        self.assertEqual(decide_deployment(active, candidate, [candidate['artifact_digest']], None), 'failed_release_fenced')
        for order in [[41, 1], [42, 1], [42, 2]]:
            self.assertEqual(decide_deployment(active, {**candidate, 'order': order}, [], None), 'stale_release')
        self.assertEqual(decide_deployment(active, candidate, [], None), 'deploy')
        self.assertEqual(decide_deployment(active, None, [], None), 'waiting')

    def test_interrupted_work_is_recovered_before_any_new_or_duplicate_release(self):
        active = {'artifact_digest': 'sha256:' + 'a' * 64, 'order': [42, 1]}
        interrupted = {'candidate_digest': 'sha256:' + 'b' * 64, 'phase': 'switch_started'}
        for candidate in [None, active, {'artifact_digest': 'sha256:' + 'c' * 64, 'order': [44, 1]}]:
            self.assertEqual(decide_deployment(active, candidate, [], interrupted), 'recover_prior')
        self.assertEqual(decide_deployment(active, None, [], {**interrupted, 'phase': 'rollback_started'}), 'manual_recovery')
        self.assertEqual(decide_deployment(active, None, [], {**interrupted, 'phase': 'rolled_back'}), 'finalize_rollback')
        committed = {'candidate_digest': active['artifact_digest'], 'phase': 'verified'}
        self.assertEqual(decide_deployment(active, None, [], committed), 'finalize_commit')
        self.assertEqual(decide_deployment(active, None, [], {**committed, 'phase': 'committed'}), 'finalize_commit')
        self.assertEqual(decide_deployment(active, None, [], {**interrupted, 'phase': 'unrecognized'}), 'manual_recovery')


if __name__ == '__main__':
    unittest.main()
