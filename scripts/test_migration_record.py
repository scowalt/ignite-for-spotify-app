import base64
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from migration_record import MigrationMetadataRejected, descriptor_summary, parse_descriptor, parse_inspection, parse_summary, verify_source_descriptor, hangfire_identity


DESCRIPTOR = {
    'protocol': 1,
    'catalogue_sha256': 'b546f0a40bfec1545cbc9f0b5e19b697967c5e43b186842d29d9ad8695d5856d',
    'baseline_schema_sha256': 'a' * 64,
    'schema_sha256': 'b' * 64,
    'migrations': [
        {'id': '0001_initial.sql', 'sha256': 'fc2e52c16b9d7d9c943b71f73924d872a81feaebabf0ebf95fd7fe5ebff42447', 'delivery': 'baseline'},
        {'id': '0002_note.sql', 'sha256': '94eba019e9aaada38dfbf837a68a2e90a4f0f2357c695925dbd35e0f2b73ce0d', 'delivery': 'automatic-schema'},
    ],
}


class MigrationRecordTests(unittest.TestCase):
    def test_descriptor_uses_the_same_canonical_binding_as_the_native_generator(self):
        self.assertEqual(parse_descriptor(json.dumps(DESCRIPTOR).encode()), DESCRIPTOR)

    def test_signed_summary_is_bounded_and_preserves_all_descriptor_bindings(self):
        summary = descriptor_summary(parse_descriptor(json.dumps(DESCRIPTOR).encode()))
        self.assertEqual(summary.migration_count, 2)
        self.assertEqual(summary.schema_sha256, 'b' * 64)
        self.assertEqual(summary, parse_summary(asdict(summary)))
        for key, bad in [('protocol', True), ('migration_count', 0), ('schema_sha256', 'b' * 63)]:
            value = asdict(summary) | {key: bad}
            with self.assertRaises(MigrationMetadataRejected):
                parse_summary(value)

    def test_inspection_distinguishes_legacy_from_valid_history_without_normalizing_timestamps(self):
        legacy = {'schema': 1, 'schema_sha256': 'a' * 64, 'history': None}
        self.assertEqual(parse_inspection(json.dumps(legacy).encode()), legacy)
        stamped = legacy | {'history': [{'id': '0001_initial.sql', 'sha256': DESCRIPTOR['migrations'][0]['sha256'], 'applied_at': '2026-01-01T00:00:00.1234567+00:00'}]}
        self.assertEqual(parse_inspection(json.dumps(stamped).encode()), stamped)
        for bad in [[], stamped['history'] * 2, [stamped['history'][0] | {'applied_at': 'not-a-time'}]]:
            with self.assertRaises(MigrationMetadataRejected):
                parse_inspection(json.dumps(legacy | {'history': bad}).encode())

    def test_publisher_binds_image_metadata_to_the_exact_checked_out_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'backend/src/Ignite.Infrastructure/Data/Migrations'
            directory.mkdir(parents=True)
            (directory / '0001_initial.sql').write_text('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n')
            (directory / '0002_note.sql').write_text('ALTER TABLE sample ADD COLUMN note TEXT;\n')
            metadata = {'schema': 1, 'migrations': [{key: row[key] for key in ['id', 'delivery']} for row in DESCRIPTOR['migrations']]}
            (directory / 'manifest.json').write_text(json.dumps(metadata))
            payload = json.dumps(DESCRIPTOR).encode()
            self.assertEqual(verify_source_descriptor(payload, root), DESCRIPTOR)
            with (directory / '0002_note.sql').open('a') as stream:
                stream.write('\n')
            with self.assertRaises(MigrationMetadataRejected):
                verify_source_descriptor(payload, root)

    def test_job_storage_identity_tracks_resolved_provider_content_not_unrelated_packages(self):
        names = ['Hangfire.AspNetCore', 'Hangfire.Core', 'Hangfire.NetCore', 'Hangfire.Storage.SQLite', 'sqlite-net-pcl']
        libraries = {name + '/1.0.0': {'type': 'package', 'sha512': 'sha512-' + base64.b64encode(b'a' * 64).decode()} for name in names}
        payload = {'libraries': libraries}
        baseline = hangfire_identity(json.dumps(payload).encode())
        self.assertRegex(baseline, r'^[a-f0-9]{64}$')
        libraries['unrelated/2.0.0'] = {'type': 'package'}
        self.assertEqual(hangfire_identity(json.dumps(payload).encode()), baseline)
        libraries['Hangfire.Core/1.0.0']['sha512'] = 'sha512-' + base64.b64encode(b'b' * 64).decode()
        self.assertNotEqual(hangfire_identity(json.dumps(payload).encode()), baseline)
        del libraries['Hangfire.Storage.SQLite/1.0.0']
        with self.assertRaises(MigrationMetadataRejected):
            hangfire_identity(json.dumps(payload).encode())

    def test_changed_sql_or_policy_cannot_reuse_a_descriptor_binding(self):
        for field, value in [('sha256', 'c' * 64), ('delivery', 'manual')]:
            changed = json.loads(json.dumps(DESCRIPTOR))
            changed['migrations'][1][field] = value
            with self.assertRaises(MigrationMetadataRejected):
                parse_descriptor(json.dumps(changed).encode())


if __name__ == '__main__':
    unittest.main()
