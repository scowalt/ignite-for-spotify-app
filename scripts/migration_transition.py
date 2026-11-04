from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

from migration_plan import classify_transition, validate_transition
from migration_record import decode, descriptor_summary, parse_inspection
from release_record import REPOSITORY, ReleaseRecord


LIMIT = 8 * 1024**2


class MigrationTransitionRejected(ValueError):
    pass


class _Busy(RuntimeError):
    pass


def _reject():
    raise MigrationTransitionRejected('migration_transition_state_invalid')


def _hex(value, length, prefix=''):
    return isinstance(value, str) and re.fullmatch(re.escape(prefix) + '[a-f0-9]{' + str(length) + '}', value) is not None


def _private_file(descriptor):
    metadata = os.fstat(descriptor)
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or
            metadata.st_mode & 0o077 or metadata.st_nlink != 1):
        _reject()


class MigrationTransition:
    def __init__(self, workspace, *, clock=None):
        self.workspace = Path(workspace)
        self.clock = clock or time.time
        self.path = self.workspace / 'migration.json'
        self._directory()

    def _directory(self):
        metadata = self.workspace.lstat()
        if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or
                metadata.st_mode & 0o077 or not _hex(self.workspace.name, 64)):
            _reject()

    @contextmanager
    def _lock(self):
        self._directory()
        descriptor = os.open(self.workspace / 'migration.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            _private_file(descriptor)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise _Busy() from None
            yield
        finally:
            os.close(descriptor)

    def _recovery_valid(self, value, created_at):
        fields = {'snapshot_id', 'repository_id', 'snapshot_time', 'snapshot_bytes', 'scratch_bytes',
                  'additional_remote_bytes', 'restore_verified'}
        if not isinstance(value, dict) or set(value) != fields:
            return False
        if (not _hex(value['snapshot_id'], 64) or not _hex(value['repository_id'], 64) or
                value['restore_verified'] is not True or not isinstance(value['snapshot_time'], str) or len(value['snapshot_time']) > 64):
            return False
        for name, minimum, maximum in [('snapshot_bytes', 1, 256 * 1024**2), ('scratch_bytes', 1, 1024**3),
                                       ('additional_remote_bytes', 0, 512 * 1024**2)]:
            if type(value[name]) is not int or not minimum <= value[name] <= maximum:
                return False
        try:
            stamp = datetime.fromisoformat(value['snapshot_time'])
            return stamp.utcoffset() == timedelta(0) and created_at - 30 <= stamp.timestamp() <= self.clock() + 30
        except (ValueError, TypeError, OverflowError):
            return False

    def _fresh(self, recovery, created_at, reserve=0):
        return (self._recovery_valid(recovery, created_at) and
                self.clock() - datetime.fromisoformat(recovery['snapshot_time']).timestamp() <= 300 - reserve)

    def _validate(self, state):
        fields = {'schema', 'candidate_digest', 'source_sha', 'backend_image', 'contract_sha256', 'hangfire_sha256', 'migration_engine_sha256',
                  'created_at', 'plan', 'phase', 'recovery', 'observed'}
        phases = {'prepared', 'migration_started', 'verified', 'recovery_started', 'unchanged', 'committed', 'uncertain', 'blocked'}
        if (not isinstance(state, dict) or set(state) != fields or type(state['schema']) is not int or state['schema'] != 1 or
                state['candidate_digest'] != 'sha256:' + self.workspace.name or not _hex(state['source_sha'], 40) or
                not _hex(state['backend_image'], 64, 'ghcr.io/' + REPOSITORY + '/backend@sha256:') or
                not _hex(state['contract_sha256'], 64) or not _hex(state['hangfire_sha256'], 64) or
                not _hex(state['migration_engine_sha256'], 64) or
                type(state['created_at']) is not int or not 0 < state['created_at'] <= self.clock() + 30 or
                not isinstance(state['phase'], str) or state['phase'] not in phases):
            _reject()
        plan = validate_transition(state['plan'])
        recovery, observed, phase = state['recovery'], state['observed'], state['phase']
        if recovery is not None and not self._recovery_valid(recovery, state['created_at']):
            _reject()
        if phase == 'prepared' and recovery is not None:
            _reject()
        if phase in ['migration_started', 'verified'] and recovery is None:
            _reject()
        if phase in ['prepared', 'migration_started', 'recovery_started', 'blocked']:
            if observed is not None:
                _reject()
        else:
            outcome = classify_transition(plan, observed)
            expected = ('unchanged' if plan['mode'] == 'none' else 'committed') if phase == 'verified' else phase
            if outcome != expected:
                _reject()
        return state

    def status(self):
        try:
            self._directory()
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as stream:
                _private_file(stream.fileno())
                payload = stream.read(LIMIT + 1)
            return self._validate(decode(payload, LIMIT))
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            raise MigrationTransitionRejected('migration_transition_state_invalid') from None

    def _save(self, state):
        self._validate(state)
        payload = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
        if len(payload) > LIMIT:
            _reject()
        self._directory()
        descriptor, name = tempfile.mkstemp(prefix='.migration-', dir=self.workspace)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.workspace, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(name).unlink(missing_ok=True)

    def prepare(self, release, plan):
        with self._lock():
            if self.path.exists() or self.path.is_symlink() or not isinstance(release, ReleaseRecord):
                _reject()
            plan = validate_transition(plan)
            if release.migrations != descriptor_summary(plan['candidate']):
                _reject()
            state = {'schema': 1, 'candidate_digest': release.artifact_digest, 'source_sha': release.source_sha,
                     'backend_image': dict(release.images).get('backend'), 'contract_sha256': release.contract_sha256,
                     'hangfire_sha256': release.hangfire_sha256, 'migration_engine_sha256': release.migration_engine_sha256,
                     'created_at': int(self.clock()), 'plan': plan,
                     'phase': 'prepared', 'recovery': None, 'observed': None}
            self._save(state)

    def _recover(self, runtime, state):
        if state['phase'] in ['committed', 'uncertain', 'blocked']:
            return state['phase']
        state['phase'], state['observed'] = 'recovery_started', None
        self._save(state)
        try:
            runtime.stop_database_writers(self.workspace)
            runtime.require_quiesced(self.workspace)
            runtime.settle_database(self.workspace)
            observed = parse_inspection(json.dumps(runtime.inspect_stopped_database(self.workspace)).encode())
            outcome = classify_transition(state['plan'], observed)
        except Exception:
            observed, outcome = None, 'blocked'
        state['observed'], state['phase'] = observed, outcome
        self._save(state)
        return outcome

    def recover(self, runtime):
        try:
            with self._lock():
                return self._recover(runtime, self.status())
        except _Busy:
            return 'busy'

    def migrate(self, runtime, recovery):
        try:
            with self._lock():
                state = self.status()
                if state['phase'] != 'prepared':
                    return self._recover(runtime, state)
                if not self._fresh(recovery, state['created_at'], reserve=180):
                    raise MigrationTransitionRejected('migration_recovery_not_fresh')
                runtime.require_quiesced(self.workspace)
                observed = parse_inspection(json.dumps(runtime.inspect_stopped_database(self.workspace)).encode())
                if observed != state['plan']['before']:
                    return self._recover(runtime, state)
                if not self._fresh(recovery, state['created_at'], reserve=180):
                    raise MigrationTransitionRejected('migration_recovery_not_fresh')
                state['phase'], state['recovery'] = 'migration_started', deepcopy(recovery)
                self._save(state)
                verified = False
                try:
                    if state['plan']['mode'] != 'none':
                        runtime.migrate_database(deepcopy(state['plan']), self.workspace)
                    runtime.stop_migration_writer(self.workspace)
                    runtime.require_quiesced(self.workspace)
                    observed = parse_inspection(json.dumps(runtime.inspect_stopped_database(self.workspace)).encode())
                    expected = 'unchanged' if state['plan']['mode'] == 'none' else 'committed'
                    verified = classify_transition(state['plan'], observed) == expected and self._fresh(recovery, state['created_at'])
                except Exception:
                    pass
                if not verified:
                    return self._recover(runtime, state)
                state['phase'], state['observed'] = 'verified', observed
                self._save(state)
                return 'verified'
        except _Busy:
            return 'busy'
