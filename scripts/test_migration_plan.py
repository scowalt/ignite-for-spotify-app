from copy import deepcopy
import unittest

from migration_plan import MigrationPlanRejected, classify_transition, prepare_transition, validate_transition
from migration_record import catalogue_hash


STAMP = '2026-01-01T00:00:00.0000000+00:00'


def descriptor(count=1):
    migrations = [{'id': '0001_initial.sql', 'sha256': '1' * 64, 'delivery': 'baseline'}]
    if count == 2:
        migrations.append({'id': '0002_extra.sql', 'sha256': '2' * 64, 'delivery': 'automatic-schema'})
    return {'protocol': 1, 'catalogue_sha256': catalogue_hash(migrations), 'baseline_schema_sha256': 'a' * 64,
            'schema_sha256': ('a' if count == 1 else 'b') * 64, 'migrations': migrations}


def inspection(count=1):
    value = descriptor(count)
    return {'schema': 1, 'schema_sha256': value['schema_sha256'],
            'history': [{key: row[key] for key in ['id', 'sha256']} | {'applied_at': STAMP} for row in value['migrations']]}


class MigrationPlanTests(unittest.TestCase):
    def test_a_committed_target_is_never_classified_as_unchanged(self):
        plan = prepare_transition(inspection(), descriptor(), descriptor(2))
        self.assertEqual(plan['mode'], 'apply')
        self.assertEqual(classify_transition(plan, inspection()), 'unchanged')
        self.assertEqual(classify_transition(plan, inspection(2)), 'committed')
        self.assertEqual(validate_transition(plan), plan)

    def test_legacy_adoption_is_explicit_baseline_only_and_is_a_committed_transition(self):
        before = {**inspection(), 'history': None}
        with self.assertRaises(MigrationPlanRejected):
            prepare_transition(before, None, descriptor())
        plan = prepare_transition(before, None, descriptor(), legacy_schema_sha256='a' * 64)
        self.assertEqual(plan['mode'], 'adopt')
        self.assertEqual(classify_transition(plan, inspection()), 'committed')
        for expected, target in [('c' * 64, descriptor()), ('a' * 64, descriptor(2))]:
            with self.assertRaises(MigrationPlanRejected):
                prepare_transition(before, None, target, legacy_schema_sha256=expected)

    def test_unknown_schema_or_rewritten_history_is_never_rollback_permission(self):
        plan = prepare_transition(inspection(), descriptor(), descriptor(2))
        variants = [inspection(), inspection(2), inspection(2)]
        variants[0]['schema_sha256'] = 'c' * 64
        variants[1]['history'][0]['applied_at'] = '2026-01-02T00:00:00.0000000+00:00'
        variants[2]['history'][1]['sha256'] = '3' * 64
        for observed in variants:
            self.assertEqual(classify_transition(plan, observed), 'uncertain')

    def test_manual_pending_changes_and_nonidentical_applied_prefixes_are_refused(self):
        for field, value in [('delivery', 'manual'), ('sha256', '4' * 64), ('id', '0001_replaced.sql')]:
            target = descriptor(2)
            target['migrations'][1 if field == 'delivery' else 0][field] = value
            target['catalogue_sha256'] = catalogue_hash(target['migrations'])
            with self.assertRaises(MigrationPlanRejected):
                prepare_transition(inspection(), descriptor(), target)
        with self.assertRaises(MigrationPlanRejected):
            prepare_transition(inspection(2), descriptor(2), descriptor())

    def test_noop_requires_identical_catalogue_and_schema_and_preserves_timestamp_identity(self):
        plan = prepare_transition(inspection(), descriptor(), descriptor())
        self.assertEqual(plan['mode'], 'none')
        self.assertEqual(classify_transition(plan, inspection()), 'unchanged')
        changed = deepcopy(plan)
        changed['mode'] = 'apply'
        with self.assertRaises(MigrationPlanRejected):
            validate_transition(changed)
        changed['mode'] = 'none'
        changed['extra'] = 'not-permitted'
        with self.assertRaises(MigrationPlanRejected):
            validate_transition(changed)
        plan['before']['history'][0]['sha256'] = '9' * 64
        with self.assertRaises(MigrationPlanRejected):
            classify_transition(plan, inspection())


if __name__ == '__main__':
    unittest.main()
