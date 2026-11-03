from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

from migration_record import catalogue_hash


BASELINE = 'CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL);'
JOURNAL = 'CREATE TABLE __ignite_migrations (position INTEGER PRIMARY KEY, id TEXT, sha256 TEXT, applied_at TEXT);'
EXPANSION = 'CREATE TABLE extra (payload BLOB);'
STAMP = '2026-01-01T00:00:00.0000000+00:00'


def schema_hash(connection):
    definitions = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' AND name != '__ignite_migrations' ORDER BY name").fetchall()
    return hashlib.sha256(json.dumps(definitions, separators=(',', ':')).encode()).hexdigest()


def catalogue(count):
    with closing(sqlite3.connect(':memory:')) as connection:
        connection.execute(BASELINE)
        baseline = schema_hash(connection)
        if count == 2:
            connection.execute(EXPANSION)
        target = schema_hash(connection)
    migrations = [{'id': '0001_initial.sql', 'sha256': '1' * 64, 'delivery': 'baseline'}]
    if count == 2:
        migrations.append({'id': '0002_extra.sql', 'sha256': '2' * 64, 'delivery': 'automatic-schema'})
    return {'protocol': 1, 'catalogue_sha256': catalogue_hash(migrations), 'baseline_schema_sha256': baseline,
            'schema_sha256': target, 'migrations': migrations}


def recovery_receipt():
    return {'snapshot_id': 'a' * 64, 'repository_id': 'b' * 64, 'snapshot_bytes': 1024,
            'snapshot_time': datetime.now(timezone.utc).isoformat(), 'scratch_bytes': 2048,
            'additional_remote_bytes': 512, 'restore_verified': True}


class SqliteRuntime:
    def __init__(self, workspace, mode='normal'):
        self.workspace = Path(workspace)
        self.database = self.workspace / 'application.db'
        self.mode = mode

    def initialize(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute(BASELINE)
            connection.execute(JOURNAL)
            connection.execute("INSERT INTO sample VALUES (1, 'original')")
            connection.execute('INSERT INTO __ignite_migrations VALUES (1, ?, ?, ?)', ('0001_initial.sql', '1' * 64, STAMP))

    def record(self, name):
        with (self.workspace / 'events').open('a') as stream:
            stream.write(name + '\n')

    def require_quiesced(self, workspace):
        self.record('quiesced')
        pid_path = self.workspace / 'writer.pid'
        if pid_path.exists():
            try:
                os.kill(int(pid_path.read_text()), 0)
            except ProcessLookupError:
                return
            raise RuntimeError('fixture writer still exists')

    def stop_database_writers(self, workspace):
        self.record('stop')
        if self.mode == 'stop-fails':
            raise RuntimeError('fixture-private-value')

    def settle_database(self, workspace):
        self.record('settle')
        connection = sqlite3.connect(self.database.as_uri() + '?mode=rw', uri=True, timeout=1)
        try:
            connection.execute('BEGIN IMMEDIATE')
            assert connection.execute('PRAGMA quick_check').fetchone() == ('ok',)
            connection.rollback()
        finally:
            connection.close()

    def inspect_database(self, workspace):
        self.record('inspect')
        connection = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=1)
        try:
            history = [{'id': identifier, 'sha256': checksum, 'applied_at': stamp} for identifier, checksum, stamp in
                       connection.execute('SELECT id,sha256,applied_at FROM __ignite_migrations ORDER BY position')]
            return {'schema': 1, 'schema_sha256': schema_hash(connection), 'history': history}
        finally:
            connection.close()

    def migrate_database(self, plan, workspace):
        self.record('migrate')
        assert plan['mode'] == 'apply'
        connection = sqlite3.connect(self.database.as_uri() + '?mode=rw', uri=True, timeout=1)
        pid_path = self.workspace / 'writer.pid'
        pid_path.write_text(str(os.getpid()))
        try:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute(EXPANSION)
            connection.execute('INSERT INTO extra VALUES (zeroblob(6000000))')
            connection.execute('INSERT INTO __ignite_migrations VALUES (2, ?, ?, ?)', ('0002_extra.sql', '2' * 64, STAMP))
            if self.mode == 'rollback':
                raise RuntimeError('fixture-private-value')
            if self.mode == 'hold-before-commit':
                (self.workspace / 'ready').write_text('uncommitted')
                time.sleep(60)
            connection.commit()
            if self.mode == 'hold-after-commit':
                (self.workspace / 'ready').write_text('committed')
                time.sleep(60)
            if self.mode == 'fail-after-commit':
                raise RuntimeError('fixture-private-value')
        finally:
            connection.close()
            pid_path.unlink(missing_ok=True)

    def stop_migration_writer(self, workspace):
        self.record('writer-stopped')
        self.require_quiesced(workspace)
