from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

from deployment_decision import decide_deployment
from release_record import REPOSITORY, ReleaseRecord


class StateRejected(ValueError):
    pass


class _Busy(RuntimeError):
    pass


def _hex(value, length, prefix=''):
    return isinstance(value, str) and re.fullmatch(re.escape(prefix) + '[a-f0-9]{' + str(length) + '}', value) is not None


def _order(value):
    return isinstance(value, list) and len(value) == 2 and all(type(x) is int and 0 < x < 2**63 for x in value)


def _image_set(value):
    return (isinstance(value, dict) and set(value) == {'backend', 'backup', 'frontend'} and
            all(_hex(reference, 64, 'ghcr.io/' + REPOSITORY + '/' + name + '@sha256:') for name, reference in value.items()))


def _release_set(value):
    return (isinstance(value, dict) and set(value) == {'source_sha', 'images', 'order', 'artifact_digest'} and
            _hex(value['source_sha'], 40) and _image_set(value['images']) and _order(value['order']) and
            (value['artifact_digest'] is None or _hex(value['artifact_digest'], 64, 'sha256:')))


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise StateRejected('Duplicate state field.')
        value[key] = item
    return value


def _recovery(value, accepted_at):
    fields = {'snapshot_id', 'repository_id', 'snapshot_time', 'snapshot_bytes', 'scratch_bytes',
              'additional_remote_bytes', 'restore_verified'}
    if not isinstance(value, dict) or set(value) != fields:
        return False
    if (not _hex(value['snapshot_id'], 64) or not _hex(value['repository_id'], 64) or
            value['restore_verified'] is not True or not isinstance(value['snapshot_time'], str) or
            len(value['snapshot_time']) > 64):
        return False
    for field, minimum, maximum in [('snapshot_bytes', 1, 256 * 1024**2), ('scratch_bytes', 1, 1024**3),
                                    ('additional_remote_bytes', 0, 512 * 1024**2)]:
        if type(value[field]) is not int or not minimum <= value[field] <= maximum:
            return False
    try:
        stamp = datetime.fromisoformat(value['snapshot_time'])
        return stamp.utcoffset() == timedelta(0) and accepted_at - 30 <= stamp.timestamp() <= time.time() + 30
    except (ValueError, TypeError, OverflowError):
        return False


def _validate_state(state):
    fields = {'schema', 'contract_sha256', 'active', 'high_water_order', 'failed_digests', 'transaction'}
    if not isinstance(state, dict) or set(state) != fields:
        raise StateRejected('Unexpected state schema.')
    if (type(state['schema']) is not int or state['schema'] != 1 or not _hex(state['contract_sha256'], 64) or
            not _release_set(state['active']) or not _order(state['high_water_order']) or
            tuple(state['high_water_order']) < tuple(state['active']['order'])):
        raise StateRejected('Invalid deployment state identity.')
    failed = state['failed_digests']
    if (not isinstance(failed, list) or len(failed) > 4096 or
            any(not _hex(digest, 64, 'sha256:') for digest in failed) or len(set(failed)) != len(failed)):
        raise StateRejected('Invalid failed release fence.')
    transaction = state['transaction']
    if transaction is None:
        return
    fields = {'candidate_digest', 'candidate', 'prior', 'phase', 'recovery', 'accepted_at', 'failure_phase'}
    phases = {'accepted', 'preflighted', 'preflight_failed', 'backup_started', 'backup_verified',
              'switch_started', 'backend_healthy', 'dependents_changed', 'verified', 'committed',
              'rollback_started', 'rolled_back'}
    if (not isinstance(transaction, dict) or set(transaction) != fields or
            not _release_set(transaction['candidate']) or not _release_set(transaction['prior']) or
            not _hex(transaction['candidate_digest'], 64, 'sha256:') or
            transaction['candidate_digest'] != transaction['candidate']['artifact_digest'] or
            type(transaction['accepted_at']) is not int or not 0 < transaction['accepted_at'] <= time.time() + 30 or
            not isinstance(transaction['phase'], str) or transaction['phase'] not in phases or
            (transaction['failure_phase'] is not None and
             (not isinstance(transaction['failure_phase'], str) or transaction['failure_phase'] not in phases)) or
            state['high_water_order'] != transaction['candidate']['order'] or
            tuple(transaction['prior']['order']) >= tuple(transaction['candidate']['order'])):
        raise StateRejected('Invalid deployment transaction.')
    if transaction['recovery'] is not None and not _recovery(transaction['recovery'], transaction['accepted_at']):
        raise StateRejected('Invalid recovery evidence.')
    if transaction['phase'] in ['backup_verified', 'switch_started', 'backend_healthy', 'dependents_changed', 'verified', 'committed'] and transaction['recovery'] is None:
        raise StateRejected('Required recovery evidence is absent.')
    expected_active = transaction['candidate'] if transaction['phase'] == 'committed' else transaction['prior']
    if state['active'] != expected_active:
        raise StateRejected('Active release and transaction disagree.')


def _private_directory(path):
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise StateRejected('Deployment directory is not private and owned.')


def _private_descriptor(descriptor):
    metadata = os.fstat(descriptor)
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or
            metadata.st_mode & 0o077 or metadata.st_nlink != 1):
        raise StateRejected('Deployment file is not private and owned.')


class Deployment:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _private_directory(root)
        self.state_path = root / 'state.json'

    def _save(self, state):
        _validate_state(state)
        self._write(self.state_path, state)

    def _write(self, path, value):
        _private_directory(path.parent)
        descriptor, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(value, stream, sort_keys=True, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(name).unlink(missing_ok=True)

    @contextmanager
    def _lock(self):
        descriptor = os.open(self.root / 'deployment.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            _private_descriptor(descriptor)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise _Busy() from None
            yield
        finally:
            os.close(descriptor)

    def bootstrap(self, active, contract_sha256):
        with self._lock():
            if not _release_set(active) or not _hex(contract_sha256, 64):
                raise StateRejected('Invalid bootstrap state.')
            if self.state_path.exists() or self.state_path.is_symlink():
                raise StateRejected('Deployment state already exists.')
            self._save({'schema': 1, 'contract_sha256': contract_sha256, 'active': active,
                        'high_water_order': active['order'], 'failed_digests': [], 'transaction': None})

    def status(self):
        _private_directory(self.root)
        try:
            descriptor = os.open(self.state_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as stream:
                _private_descriptor(stream.fileno())
                raw = stream.read(2 * 1024**2 + 1)
            if len(raw) > 2 * 1024**2:
                raise StateRejected('Deployment state exceeds its bound.')
            state = json.loads(raw, object_pairs_hook=_unique)
            _validate_state(state)
            return state
        except (OSError, ValueError, RecursionError):
            raise StateRejected('Deployment state is unavailable or invalid.') from None

    def attempt(self, digest):
        if not _hex(digest, 64, 'sha256:'):
            raise StateRejected('Invalid attempt identity.')
        workspace = self.root / digest.removeprefix('sha256:')
        _private_directory(workspace)
        try:
            descriptor = os.open(workspace / 'result.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as stream:
                _private_descriptor(stream.fileno())
                raw = stream.read(2 * 1024**2 + 1)
            if len(raw) > 2 * 1024**2:
                raise StateRejected('Attempt evidence exceeds its bound.')
            report = json.loads(raw, object_pairs_hook=_unique)
            if not isinstance(report, dict) or set(report) != {'outcome', 'state'} or report['outcome'] not in ['deployed', 'rolled_back', 'preflight_failed']:
                raise StateRejected('Unexpected attempt schema.')
            _validate_state(report['state'])
            if report['state']['transaction']['candidate_digest'] != digest:
                raise StateRejected('Attempt identity mismatch.')
            return report
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            raise StateRejected('Attempt evidence is unavailable or invalid.') from None

    def _finish(self, state, runtime, workspace, outcome):
        try:
            runtime.cleanup(workspace)
        except Exception:
            return 'cleanup_required'
        report = {'outcome': outcome, 'state': state}
        result_path = workspace / 'result.json'
        if result_path.exists() or result_path.is_symlink():
            if self.attempt(state['transaction']['candidate_digest']) != report:
                raise StateRejected('Existing attempt evidence differs.')
        else:
            self._write(result_path, report)
        state['transaction'] = None
        self._save(state)
        return outcome

    def _abandon(self, state, runtime, workspace):
        transaction = state['transaction']
        if transaction['candidate_digest'] not in state['failed_digests']:
            state['failed_digests'].append(transaction['candidate_digest'])
        if transaction['failure_phase'] is None:
            transaction['failure_phase'] = transaction['phase']
        transaction['phase'] = 'preflight_failed'
        self._save(state)
        return self._finish(state, runtime, workspace, 'preflight_failed')

    def _recover(self, state, runtime, workspace):
        transaction = state['transaction']
        if transaction['candidate_digest'] not in state['failed_digests']:
            state['failed_digests'].append(transaction['candidate_digest'])
        if transaction['failure_phase'] is None:
            transaction['failure_phase'] = transaction['phase']
        transaction['phase'] = 'rollback_started'
        self._save(state)
        try:
            runtime.cleanup(workspace)
            runtime.rollback(transaction['prior'], workspace)
            runtime.verify(transaction['prior']['images'], workspace)
        except Exception:
            return 'manual_recovery'
        transaction['phase'] = 'rolled_back'
        self._save(state)
        return self._finish(state, runtime, workspace, 'rolled_back')

    def run(self, release, runtime):
        try:
            with self._lock():
                return self._run_locked(release, runtime)
        except _Busy:
            return 'busy'

    def _run_locked(self, release, runtime):
        state = self.status()
        if state['transaction'] is not None:
            release = None
        if release is not None and (not isinstance(release, ReleaseRecord) or release.contract_sha256 != state['contract_sha256']):
            raise StateRejected('Unreviewed deployment contract.')
        target = None if release is None else {'source_sha': release.source_sha, 'images': dict(release.images),
                                               'order': list(release.order), 'artifact_digest': release.artifact_digest}
        if target is not None and (not _release_set(target) or not _hex(target['artifact_digest'], 64, 'sha256:')):
            raise StateRejected('Invalid deployment candidate.')
        decision = decide_deployment(state, target)
        if decision in ['recover_prior', 'finalize_commit', 'finalize_rollback', 'abandon_preswitch']:
            workspace = self.root / state['transaction']['candidate_digest'].removeprefix('sha256:')
            _private_directory(workspace)
            if decision == 'abandon_preswitch':
                return self._abandon(state, runtime, workspace)
            if decision == 'recover_prior':
                return self._recover(state, runtime, workspace)
            return self._finish(state, runtime, workspace, 'deployed' if decision == 'finalize_commit' else 'rolled_back')
        if decision != 'deploy':
            return decision
        if len(state['failed_digests']) >= 4096:
            return 'manual_recovery'
        workspace = self.root / release.artifact_digest.removeprefix('sha256:')
        workspace.mkdir(mode=0o700)
        transaction = {'candidate_digest': release.artifact_digest, 'candidate': target,
                       'prior': state['active'], 'phase': 'accepted', 'recovery': None,
                       'accepted_at': int(time.time()), 'failure_phase': None}
        state['transaction'] = transaction
        state['high_water_order'] = target['order']
        self._save(state)
        try:
            runtime.preflight(release, transaction['prior'], workspace)
        except Exception:
            return self._abandon(state, runtime, workspace)
        try:
            transaction['phase'] = 'backup_started'
            self._save(state)
            recovery = runtime.backup(workspace)
            if (not _recovery(recovery, transaction['accepted_at']) or
                    time.time() - datetime.fromisoformat(recovery['snapshot_time']).timestamp() > 300):
                raise StateRejected('Fresh verified recovery evidence is required.')
            transaction['recovery'] = recovery
            transaction['phase'] = 'backup_verified'
            self._save(state)
            runtime.cleanup(workspace)
            if time.time() - datetime.fromisoformat(recovery['snapshot_time']).timestamp() > 300:
                raise StateRejected('Recovery evidence expired before image mutation.')
            transaction['phase'] = 'switch_started'
            self._save(state)
            runtime.switch_backend(release, workspace)
            transaction['phase'] = 'backend_healthy'
            self._save(state)
            runtime.switch_dependents(release, workspace)
            transaction['phase'] = 'dependents_changed'
            self._save(state)
            runtime.verify(target['images'], workspace)
            transaction['phase'] = 'verified'
            self._save(state)
        except Exception:
            return self._recover(state, runtime, workspace)
        state['active'] = target
        transaction['phase'] = 'committed'
        self._save(state)
        return self._finish(state, runtime, workspace, 'deployed')
