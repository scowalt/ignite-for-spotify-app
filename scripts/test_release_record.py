from dataclasses import replace
import copy
import json
from pathlib import Path
import tempfile
import unittest

from release_record import CONTRACT_PATHS, ReleaseRejected, SignatureProof, create_release_record, deployment_contract, validate_release


class ReleaseRecordTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            'schema': 1,
            'repository': 'scowalt/ignite-for-spotify-app',
            'source_sha': 'a' * 40,
            'run_id': 123,
            'run_attempt': 1,
            'run_number': 42,
            'contract_sha256': 'b' * 64,
            'images': {
                'backend': 'ghcr.io/scowalt/ignite-for-spotify-app/backend@sha256:' + 'c' * 64,
                'backup': 'ghcr.io/scowalt/ignite-for-spotify-app/backup@sha256:' + 'd' * 64,
                'frontend': 'ghcr.io/scowalt/ignite-for-spotify-app/frontend@sha256:' + 'e' * 64,
            },
        }
        self.run = {
            'id': 123, 'run_attempt': 1, 'run_number': 42,
            'head_sha': 'a' * 40, 'head_branch': 'main', 'event': 'push',
            'status': 'completed', 'conclusion': 'success', 'workflow_id': 403197563,
            'path': '.github/workflows/ci.yml',
            'repository': {'id': 1441388195}, 'head_repository': {'id': 1441388195},
        }
        self.proof = SignatureProof(
            artifact_digest='sha256:' + 'f' * 64,
            source_sha='a' * 40,
            identity='https://github.com/scowalt/ignite-for-spotify-app/.github/workflows/deploy.yml@refs/heads/main',
            issuer='https://token.actions.githubusercontent.com',
        )

    def test_verified_complete_release_selects_one_coherent_digest_set(self):
        release = validate_release(json.dumps(self.record).encode(), self.proof, self.run, 'b' * 64)
        self.assertEqual(release.source_sha, 'a' * 40)
        self.assertEqual(release.order, (42, 1))
        self.assertEqual(dict(release.images), self.record['images'])
        self.assertEqual(release.artifact_digest, 'sha256:' + 'f' * 64)

    def test_signature_must_bind_the_trusted_publisher_and_this_revision(self):
        for changes in [
            {'issuer': 'https://other.example'},
            {'identity': 'https://github.com/other/repo/.github/workflows/deploy.yml@refs/heads/main'},
            {'source_sha': '0' * 40},
            {'artifact_digest': 'latest'},
            {'artifact_digest': None},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ReleaseRejected):
                validate_release(json.dumps(self.record).encode(), replace(self.proof, **changes), self.run, 'b' * 64)

    def test_incomplete_mutable_or_wrong_namespace_images_are_rejected(self):
        cases = []
        missing = copy.deepcopy(self.record)
        missing['images'].pop('backup')
        cases.append(missing)
        for image in ['ghcr.io/scowalt/ignite-for-spotify-app/backend:latest',
                      'ghcr.io/scowalt/ignite-for-spotify-2/backend@sha256:' + 'c' * 64,
                      'ghcr.io/scowalt/ignite-for-spotify-app/frontend@sha256:' + 'c' * 64]:
            altered = copy.deepcopy(self.record)
            altered['images']['backend'] = image
            cases.append(altered)
        for record in cases:
            with self.subTest(record=record), self.assertRaises(ReleaseRejected):
                validate_release(json.dumps(record).encode(), self.proof, self.run, 'b' * 64)

    def test_schema_identity_and_contract_changes_require_review(self):
        for change in [{'schema': True}, {'schema': 2}, {'repository': 'other/repo'},
                       {'source_sha': 'main'}, {'run_id': True}, {'run_number': 0},
                       {'run_attempt': -1}, {'contract_sha256': '0' * 64}, {'extra': 'unreviewed'}]:
            with self.subTest(change=change), self.assertRaises(ReleaseRejected):
                validate_release(json.dumps({**self.record, **change}).encode(), self.proof, self.run, 'b' * 64)
        for payload in [b'[]', b'null', b'{', b' ' * 32769,
                        json.dumps(self.record).replace('"schema": 1', '"schema": 1, "schema": 1').encode()]:
            with self.subTest(payload_type=type(payload)), self.assertRaises(ReleaseRejected):
                validate_release(payload, self.proof, self.run, 'b' * 64)

    def test_only_the_matching_successful_trusted_main_run_is_deployable(self):
        for changes in [{'status': 'in_progress'}, {'conclusion': 'failure'}, {'event': 'pull_request'},
                        {'head_branch': 'feature'}, {'head_sha': '0' * 40}, {'id': 124},
                        {'run_attempt': 2}, {'run_number': 43}, {'workflow_id': 1},
                        {'path': '.github/workflows/unreviewed.yml'}, {'repository': {'id': 1}},
                        {'head_repository': {'id': 1}}, {'repository': None}]:
            with self.subTest(changes=changes), self.assertRaises(ReleaseRejected):
                validate_release(json.dumps(self.record).encode(), self.proof, {**self.run, **changes}, 'b' * 64)
        for run in [None, {}, []]:
            with self.subTest(run=run), self.assertRaises(ReleaseRejected):
                validate_release(json.dumps(self.record).encode(), self.proof, run, 'b' * 64)
        release = validate_release(json.dumps(self.record).encode(), self.proof, {**self.run, 'event': 'workflow_dispatch'}, 'b' * 64)
        self.assertEqual(release.run_id, 123)

    def test_contract_tracks_reviewed_runtime_inputs_not_unrelated_documentation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in CONTRACT_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('reviewed fixture')
            baseline = deployment_contract(root)
            self.assertRegex(baseline, r'^[a-f0-9]{64}$')
            (root / 'README.md').write_text('documentation-only change')
            self.assertEqual(deployment_contract(root), baseline)
            changed = root / CONTRACT_PATHS[0]
            changed.write_text('changed runtime contract')
            self.assertNotEqual(deployment_contract(root), baseline)
            changed.unlink()
            with self.assertRaises(ReleaseRejected):
                deployment_contract(root)
            changed.symlink_to(root / 'README.md')
            with self.assertRaises(ReleaseRejected):
                deployment_contract(root)

    def test_publisher_record_is_bounded_to_trusted_ci_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in CONTRACT_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('reviewed fixture')
            env = {'GITHUB_REPOSITORY': 'scowalt/ignite-for-spotify-app', 'GITHUB_REF': 'refs/heads/main',
                   'GITHUB_EVENT_NAME': 'push', 'GITHUB_SHA': 'a' * 40,
                   'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_NUMBER': '42',
                   'UNRELATED_SECRET': 'do-not-include'}
            payload = create_release_record(root, env, self.record['images'])
            self.assertNotIn(b'do-not-include', payload)
            record = json.loads(payload)
            self.assertEqual(record['run_id'], 123)
            self.assertEqual(record['source_sha'], 'a' * 40)
            self.assertEqual(record['images'], self.record['images'])
            release = validate_release(payload, self.proof, self.run, deployment_contract(root))
            self.assertEqual(release.order, (42, 1))
            for changed in [{'GITHUB_REF': 'refs/pull/1/merge'}, {'GITHUB_REPOSITORY': 'other/repo'}, {'GITHUB_RUN_ID': 'no'}, {'GITHUB_EVENT_NAME': 'pull_request'}]:
                with self.subTest(changed=changed), self.assertRaises(ReleaseRejected):
                    create_release_record(root, {**env, **changed}, self.record['images'])

    def test_unsigned_release_is_not_deployable(self):
        with self.assertRaises(ReleaseRejected):
            validate_release(json.dumps(self.record).encode(), None, self.run, 'b' * 64)


if __name__ == '__main__':
    unittest.main()
