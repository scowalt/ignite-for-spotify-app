import json

from migration_record import parse_descriptor, parse_inspection


class MigrationPlanRejected(ValueError):
    pass


def _reject():
    raise MigrationPlanRejected('migration_transition_invalid')


def _matches(inspection, catalogue):
    history = inspection['history']
    return (inspection['schema_sha256'] == catalogue['schema_sha256'] and history is not None and
            [{key: row[key] for key in ['id', 'sha256']} for row in history] ==
            [{key: row[key] for key in ['id', 'sha256']} for row in catalogue['migrations']])


def prepare_transition(before, prior, candidate, *, legacy_schema_sha256=None):
    try:
        before = parse_inspection(json.dumps(before).encode())
        candidate = parse_descriptor(json.dumps(candidate).encode())
        if prior is None:
            if (before['history'] is not None or len(candidate['migrations']) != 1 or
                    legacy_schema_sha256 != before['schema_sha256'] or
                    before['schema_sha256'] != candidate['baseline_schema_sha256']):
                _reject()
            mode = 'adopt'
        else:
            prior = parse_descriptor(json.dumps(prior).encode())
            if legacy_schema_sha256 is not None or not _matches(before, prior):
                _reject()
            applied = len(prior['migrations'])
            if (candidate['baseline_schema_sha256'] != prior['baseline_schema_sha256'] or
                    candidate['migrations'][:applied] != prior['migrations'] or
                    any(row['delivery'] != 'automatic-schema' for row in candidate['migrations'][applied:])):
                _reject()
            mode = 'apply' if len(candidate['migrations']) > applied else 'none'
            if mode == 'none' and candidate != prior:
                _reject()
        return {'schema': 1, 'mode': mode, 'before': before, 'prior': prior,
                'candidate': candidate, 'legacy_schema_sha256': legacy_schema_sha256}
    except (ValueError, TypeError, KeyError, RecursionError):
        raise MigrationPlanRejected('migration_transition_invalid') from None


def validate_transition(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'mode', 'before', 'prior', 'candidate', 'legacy_schema_sha256'}:
        _reject()
    expected = prepare_transition(value['before'], value['prior'], value['candidate'], legacy_schema_sha256=value['legacy_schema_sha256'])
    if type(value['schema']) is not int or value != expected:
        _reject()
    return expected


def classify_transition(plan, observed):
    plan = validate_transition(plan)
    observed = parse_inspection(json.dumps(observed).encode())
    if observed == plan['before']:
        return 'unchanged'
    old_history = plan['before']['history'] or []
    if (plan['mode'] != 'none' and _matches(observed, plan['candidate']) and
            observed['history'][:len(old_history)] == old_history):
        return 'committed'
    return 'uncertain'
