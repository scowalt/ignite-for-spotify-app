import unittest

from deployment_decision import decide_deployment


class DeploymentDecisionTests(unittest.TestCase):
    def setUp(self):
        self.active = {'artifact_digest': 'sha256:' + 'a' * 64, 'order': [42, 1]}
        self.candidate = {'artifact_digest': 'sha256:' + 'b' * 64, 'order': [43, 1]}
        self.state = {'active': self.active, 'high_water_order': [42, 1], 'failed_digests': [], 'transaction': None}

    def test_an_already_active_release_does_not_repeat_a_deployment(self):
        self.assertEqual(decide_deployment(self.state, self.active), 'unchanged')

    def test_failed_or_non_forward_releases_do_not_repeat_mutations(self):
        failed = {**self.state, 'failed_digests': [self.candidate['artifact_digest']]}
        self.assertEqual(decide_deployment(failed, self.candidate), 'failed_release_fenced')
        for order in [[41, 1], [42, 1]]:
            self.assertEqual(decide_deployment(self.state, {**self.candidate, 'order': order}), 'stale_release')
        self.assertEqual(decide_deployment(self.state, self.candidate), 'deploy')
        self.assertEqual(decide_deployment(self.state, None), 'waiting')

    def test_rollback_does_not_erase_the_high_water_replay_fence(self):
        state = {**self.state, 'high_water_order': [44, 1]}
        for order in [[43, 1], [44, 1]]:
            self.assertEqual(decide_deployment(state, {**self.candidate, 'order': order}), 'stale_release')
        self.assertEqual(decide_deployment(state, {**self.candidate, 'order': [44, 2]}), 'deploy')

    def test_interrupted_work_is_recovered_before_any_new_or_duplicate_release(self):
        interrupted = {'candidate_digest': self.candidate['artifact_digest'], 'phase': 'switch_started'}
        for candidate in [None, self.active, {'artifact_digest': 'sha256:' + 'c' * 64, 'order': [44, 1]}]:
            self.assertEqual(decide_deployment({**self.state, 'transaction': interrupted}, candidate), 'recover_prior')
        def interrupted_state(phase, digest):
            return {**self.state, 'transaction': {'phase': phase, 'candidate_digest': digest}}
        self.assertEqual(decide_deployment(interrupted_state('rollback_started', self.candidate['artifact_digest']), None), 'manual_recovery')
        self.assertEqual(decide_deployment(interrupted_state('rolled_back', self.candidate['artifact_digest']), None), 'finalize_rollback')
        for phase in ['verified', 'committed']:
            self.assertEqual(decide_deployment(interrupted_state(phase, self.active['artifact_digest']), None), 'finalize_commit')
        self.assertEqual(decide_deployment(interrupted_state('unrecognized', self.candidate['artifact_digest']), None), 'manual_recovery')


if __name__ == '__main__':
    unittest.main()
