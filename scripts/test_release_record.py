import base64
from dataclasses import replace
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_migration_record import DESCRIPTOR
from release_record import CONTRACT_PATHS, MIGRATION_CONTRACT_PATHS, runtime_contract, ReleasePending, ReleaseRejected, SignatureProof, create_release_record, deployment_contract, validate_release


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

    def test_version_two_binds_migration_and_job_storage_metadata_to_the_release(self):
        migrations = {'protocol': 1, 'catalogue_sha256': '1' * 64, 'baseline_schema_sha256': '2' * 64,
                      'schema_sha256': '3' * 64, 'migration_count': 2}
        record = self.record | {'schema': 2, 'migrations': migrations, 'hangfire_sha256': '4' * 64}
        with self.assertRaises(ReleaseRejected):
            validate_release(json.dumps(record).encode(), self.proof, self.run, 'b' * 64)
        release = validate_release(json.dumps(record).encode(), self.proof, self.run, 'b' * 64, allow_migrations=True)
        self.assertEqual(release.migrations.catalogue_sha256, '1' * 64)
        self.assertEqual(release.hangfire_sha256, '4' * 64)
        for change in [{'migrations': None}, {'migrations': migrations | {'protocol': True}},
                       {'hangfire_sha256': 'not-a-hash'}, {'schema': 1}]:
            with self.subTest(change=change), self.assertRaises(ReleaseRejected):
                validate_release(json.dumps(record | change).encode(), self.proof, self.run, 'b' * 64, allow_migrations=True)

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

    def test_migration_protocol_pins_safety_code_separately_from_host_configuration_and_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in CONTRACT_PATHS + MIGRATION_CONTRACT_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('reviewed fixture')
            legacy = deployment_contract(root)
            host = runtime_contract(root)
            full = deployment_contract(root, migration_protocol=True)
            self.assertNotEqual(full, legacy)
            sql = root / 'backend/src/Ignite.Infrastructure/Data/Migrations/0002_added.sql'
            sql.parent.mkdir(parents=True, exist_ok=True)
            sql.write_text('CREATE TABLE extra (id INTEGER);\n')
            self.assertEqual(deployment_contract(root, migration_protocol=True), full)
            (root / MIGRATION_CONTRACT_PATHS[0]).write_text('changed migration safety logic')
            self.assertNotEqual(deployment_contract(root, migration_protocol=True), full)
            self.assertEqual(runtime_contract(root), host)
            self.assertEqual(deployment_contract(root), legacy)
            (root / CONTRACT_PATHS[0]).write_text('changed runtime config')
            self.assertNotEqual(runtime_contract(root), host)

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

    def test_publisher_creates_v2_only_with_source_bound_catalogue_and_resolved_storage_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in CONTRACT_PATHS + MIGRATION_CONTRACT_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('reviewed fixture')
            migrations = root / 'backend/src/Ignite.Infrastructure/Data/Migrations'
            migrations.mkdir()
            (migrations / '0001_initial.sql').write_text('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n')
            (migrations / '0002_note.sql').write_text('ALTER TABLE sample ADD COLUMN note TEXT;\n')
            (migrations / 'manifest.json').write_text(json.dumps({'schema': 1, 'migrations': [{key: row[key] for key in ['id', 'delivery']} for row in DESCRIPTOR['migrations']]}))
            names = ['Hangfire.AspNetCore', 'Hangfire.Core', 'Hangfire.NetCore', 'Hangfire.Storage.SQLite', 'sqlite-net-pcl']
            deps = json.dumps({'libraries': {name + '/1.0.0': {'type': 'package', 'sha512': 'sha512-' + base64.b64encode(b'a' * 64).decode()} for name in names}}).encode()
            env = {'GITHUB_REPOSITORY': 'scowalt/ignite-for-spotify-app', 'GITHUB_REF': 'refs/heads/main',
                   'GITHUB_EVENT_NAME': 'push', 'GITHUB_SHA': 'a' * 40,
                   'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_NUMBER': '42'}
            descriptor = json.dumps(DESCRIPTOR).encode()
            payload = create_release_record(root, env, self.record['images'], migration_descriptor=descriptor, backend_deps=deps)
            self.assertEqual(json.loads(payload)['schema'], 2)
            verified = validate_release(payload, self.proof, self.run, deployment_contract(root, migration_protocol=True), allow_migrations=True)
            self.assertEqual(verified.migrations.catalogue_sha256, DESCRIPTOR['catalogue_sha256'])
            for missing in [{'migration_descriptor': descriptor}, {'backend_deps': deps}]:
                with self.assertRaises(ReleaseRejected):
                    create_release_record(root, env, self.record['images'], **missing)
            (migrations / '0002_note.sql').write_text('SELECT 1;\n')
            with self.assertRaises(ReleaseRejected):
                create_release_record(root, env, self.record['images'], migration_descriptor=descriptor, backend_deps=deps)

    def test_finishing_trusted_workflow_is_deferred_not_treated_as_a_deployment_failure(self):
        with self.assertRaises(ReleasePending):
            validate_release(json.dumps(self.record).encode(), self.proof, {**self.run, 'status': 'in_progress', 'conclusion': None}, 'b' * 64)
        with self.assertRaises(ReleaseRejected) as failure:
            validate_release(json.dumps(self.record).encode(), self.proof, {**self.run, 'status': 'in_progress', 'head_sha': '0' * 40}, 'b' * 64)
        self.assertNotIsInstance(failure.exception, ReleasePending)

    def test_unsigned_release_is_not_deployable(self):
        with self.assertRaises(ReleaseRejected):
            validate_release(json.dumps(self.record).encode(), None, self.run, 'b' * 64)


if __name__ == '__main__':
    unittest.main()
