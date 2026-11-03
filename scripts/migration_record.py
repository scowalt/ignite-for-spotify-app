import base64
from dataclasses import dataclass
import datetime
import hashlib
import json
from pathlib import Path
import re


DESCRIPTOR_LIMIT = 1024**2
HISTORY_LIMIT = 2 * 1024**2


class MigrationMetadataRejected(ValueError):
    pass


def _reject():
    raise MigrationMetadataRejected('migration_metadata_invalid')


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            _reject()
        result[name] = value
    return result


def decode(payload, limit=DESCRIPTOR_LIMIT):
    if not isinstance(payload, bytes) or len(payload) > limit:
        _reject()
    try:
        return json.loads(payload, object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError):
        raise MigrationMetadataRejected('migration_metadata_invalid') from None


def _keys(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        _reject()


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _identifier(value):
    return (isinstance(value, str) and len(value) <= 128 and
            re.fullmatch(r'[0-9]{4}_[a-z0-9_]+\.sql', value) is not None and not value.startswith('0000_'))


def catalogue_hash(migrations):
    text = 'ignite-database-catalogue-v1\n'
    text += ''.join(row['id'] + '\t' + row['sha256'] + '\t' + row['delivery'] + '\n' for row in migrations)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class MigrationSummary:
    protocol: int
    catalogue_sha256: str
    baseline_schema_sha256: str
    schema_sha256: str
    migration_count: int


def parse_summary(value):
    fields = ['protocol', 'catalogue_sha256', 'baseline_schema_sha256', 'schema_sha256', 'migration_count']
    _keys(value, fields)
    if type(value['protocol']) is not int or value['protocol'] != 1:
        _reject()
    if type(value['migration_count']) is not int or not 1 <= value['migration_count'] <= 4096:
        _reject()
    if any(not _hash(value[key]) for key in ['catalogue_sha256', 'baseline_schema_sha256', 'schema_sha256']):
        _reject()
    if value['migration_count'] == 1 and value['baseline_schema_sha256'] != value['schema_sha256']:
        _reject()
    return MigrationSummary(**value)


def descriptor_summary(descriptor):
    return parse_summary({key: descriptor[key] for key in ['protocol', 'catalogue_sha256', 'baseline_schema_sha256', 'schema_sha256']} | {'migration_count': len(descriptor['migrations'])})


def parse_inspection(payload):
    value = decode(payload, HISTORY_LIMIT)
    _keys(value, ['schema', 'schema_sha256', 'history'])
    if type(value['schema']) is not int or value['schema'] != 1 or not _hash(value['schema_sha256']):
        _reject()
    rows = value['history']
    if rows is None:
        return value
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        _reject()
    previous = ''
    for row in rows:
        _keys(row, ['id', 'sha256', 'applied_at'])
        if not _identifier(row['id']) or not _hash(row['sha256']) or row['id'][:4] <= previous:
            _reject()
        previous = row['id'][:4]
        stamp = row['applied_at']
        if not isinstance(stamp, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{7}\+00:00', stamp):
            _reject()
        try:
            parsed = datetime.datetime.fromisoformat(stamp)
        except ValueError:
            raise MigrationMetadataRejected('migration_metadata_invalid') from None
        if parsed > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=30):
            _reject()
    return value


def hangfire_identity(payload):
    value = decode(payload, HISTORY_LIMIT)
    libraries = value.get('libraries') if isinstance(value, dict) else None
    if not isinstance(libraries, dict) or len(libraries) > 10000:
        _reject()
    found = {}
    required = {'hangfire.aspnetcore', 'hangfire.core', 'hangfire.netcore', 'hangfire.storage.sqlite', 'sqlite-net-pcl'}
    for identity, metadata in libraries.items():
        if not isinstance(identity, str) or '/' not in identity:
            _reject()
        name, version = identity.rsplit('/', 1)
        name = name.lower()
        if not (name.startswith('hangfire.') or name == 'sqlite-net-pcl'):
            continue
        if (name in found or len(name) > 128 or not re.fullmatch(r'[a-z0-9.-]+', name) or
                not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9.-]+)?', version) or
                not isinstance(metadata, dict) or metadata.get('type') != 'package'):
            _reject()
        checksum = metadata.get('sha512')
        if not isinstance(checksum, str) or not checksum.startswith('sha512-') or len(checksum) != 95:
            _reject()
        try:
            digest = base64.b64decode(checksum[7:], validate=True)
        except ValueError:
            raise MigrationMetadataRejected('migration_metadata_invalid') from None
        if len(digest) != 64:
            _reject()
        found[name] = (version, digest.hex())
    if not required.issubset(found):
        _reject()
    text = 'ignite-hangfire-storage-v1\n' + ''.join(name + '\t' + version + '\t' + checksum + '\n' for name, (version, checksum) in sorted(found.items()))
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def verify_source_descriptor(payload, root):
    descriptor = parse_descriptor(payload)
    root = Path(root).resolve()
    directory = root / 'backend/src/Ignite.Infrastructure/Data/Migrations'
    try:
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            _reject()
        paths = sorted(directory.iterdir(), key=lambda path: path.name)
        if len(paths) > 4097 or any(path.is_symlink() or not path.is_file() for path in paths):
            _reject()
        if any(path.name != 'manifest.json' and not _identifier(path.name) for path in paths):
            _reject()
        metadata_path = directory / 'manifest.json'
        if metadata_path.stat().st_size > DESCRIPTOR_LIMIT:
            _reject()
        metadata = decode(metadata_path.read_bytes())
        _keys(metadata, ['schema', 'migrations'])
        if type(metadata['schema']) is not int or metadata['schema'] != 1:
            _reject()
        expected_policy = [{key: row[key] for key in ['id', 'delivery']} for row in descriptor['migrations']]
        if metadata['migrations'] != expected_policy:
            _reject()
        sql_paths = [path for path in paths if path.name != 'manifest.json']
        if [path.name for path in sql_paths] != [row['id'] for row in descriptor['migrations']]:
            _reject()
        total = 0
        for path, row in zip(sql_paths, descriptor['migrations']):
            size = path.stat().st_size
            total += size
            if size > 1024**2 or total > 16 * 1024**2:
                _reject()
            content = path.read_bytes()
            if len(content) != size or not content.strip() or content.startswith(b'\xef\xbb\xbf') or b'\r' in content or b'\x00' in content:
                _reject()
            content.decode('utf-8')
            if hashlib.sha256(content).hexdigest() != row['sha256']:
                _reject()
    except (OSError, UnicodeError, ValueError):
        raise MigrationMetadataRejected('migration_source_mismatch') from None
    return descriptor


def parse_descriptor(payload):
    value = decode(payload)
    _keys(value, ['protocol', 'catalogue_sha256', 'baseline_schema_sha256', 'schema_sha256', 'migrations'])
    if type(value['protocol']) is not int or value['protocol'] != 1:
        _reject()
    if any(not _hash(value[key]) for key in ['catalogue_sha256', 'baseline_schema_sha256', 'schema_sha256']):
        _reject()
    rows = value['migrations']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        _reject()
    previous = ''
    for index, row in enumerate(rows):
        _keys(row, ['id', 'sha256', 'delivery'])
        if not _identifier(row['id']) or not _hash(row['sha256']) or row['id'][:4] <= previous:
            _reject()
        previous = row['id'][:4]
        if index == 0:
            if row['id'] != '0001_initial.sql' or row['delivery'] != 'baseline':
                _reject()
        elif row['delivery'] not in ['automatic-schema', 'manual']:
            _reject()
    if value['catalogue_sha256'] != catalogue_hash(rows):
        _reject()
    if len(rows) == 1 and value['baseline_schema_sha256'] != value['schema_sha256']:
        _reject()
    return value
