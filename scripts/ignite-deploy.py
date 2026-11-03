import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from deployment_runtime import DockerRuntime
from deployment_transaction import Deployment
from release_record import ReleasePending, ReleaseRecord, deployment_contract
from release_signature import SignatureVerifier
from release_transport import load_release


@contextmanager
def poll_lock(root):
    descriptor = os.open(root / 'poll.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise ValueError('Invalid poll lock.')
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def private_json(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077 or metadata.st_size > 65536:
            raise ValueError('Invalid operator file.')
        return json.loads(stream.read(65537))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, default=Path.home() / '.local/state/ignite-deployer')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('action', choices=['bootstrap', 'status', 'check', 'once'])
    args = parser.parse_args()
    try:
        root = args.state
        deployment = Deployment(root)
        policy = private_json(root / 'policy.json')
        if (set(policy) != {'schema', 'contract_sha256', 'repository_id', 'operator_sha'} or type(policy['schema']) is not int or policy['schema'] != 1 or
                any(not isinstance(policy[key], str) or not re.fullmatch(r'[a-f0-9]{64}', policy[key]) for key in ['contract_sha256', 'repository_id']) or
                not re.fullmatch(r'[a-f0-9]{40}', policy['operator_sha'])):
            raise ValueError('Invalid deployment policy.')
        if Path(__file__).resolve().parents[1].name != policy['operator_sha']:
            raise ValueError('Operator bundle version differs from policy.')
        checkout = Path.home() / 'Code/ignite-for-spotify-app'
        anchor = Path.home() / 'Code/ignite-for-spotify-2/docker'
        if deployment_contract(checkout) != policy['contract_sha256']:
            raise ValueError('Installed contract differs from policy.')
        runtime = DockerRuntime(checkout, anchor, policy['contract_sha256'], policy['repository_id'])
        if args.action == 'status':
            print(json.dumps(deployment.status(), sort_keys=True))
            return 0
        with poll_lock(root):
            if args.action == 'bootstrap':
                if args.baseline is None or (root / 'state.json').exists():
                    raise ValueError('Bootstrap requires a new ledger and an explicit baseline.')
                baseline = private_json(args.baseline)
                operation = hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
                checks = root / 'bootstrap-checks'
                checks.mkdir(mode=0o700, exist_ok=True)
                workspace = checks / operation
                workspace.mkdir(mode=0o700)
                release = ReleaseRecord(baseline['source_sha'], 1, baseline['order'][1], baseline['order'][0],
                                        policy['contract_sha256'], tuple(sorted(baseline['images'].items())), 'sha256:' + operation)
                try:
                    runtime.preflight(release, baseline, workspace)
                finally:
                    runtime.cleanup(workspace)
                deployment.bootstrap(baseline, policy['contract_sha256'])
                outcome = 'bootstrapped'
            else:
                if args.action == 'check' and deployment.status()['transaction'] is not None:
                    raise ValueError('Read-only preflight is unavailable during recovery.')
                outcome = deployment.run(None, runtime)
                if outcome != 'waiting':
                    print(json.dumps({'outcome': outcome}))
                    return 0 if outcome in ['deployed', 'unchanged'] else 1
                verifier = SignatureVerifier(Path.home() / '.local/lib/ignite-deployer/tools/cosign-v3.1.4')
                release = load_release(policy['contract_sha256'], docker=runtime.docker, verifier=verifier)
                if args.action == 'check':
                    checks = root / 'checks'
                    checks.mkdir(mode=0o700, exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=checks) as temporary:
                        workspace = Path(temporary) / release.artifact_digest.removeprefix('sha256:')
                        workspace.mkdir(mode=0o700)
                        try:
                            runtime.preflight(release, deployment.status()['active'], workspace)
                        finally:
                            runtime.cleanup(workspace)
                    outcome = 'verified_without_deployment'
                else:
                    outcome = deployment.run(release, runtime)
            print(json.dumps({'outcome': outcome}))
            return 0 if outcome in ['deployed', 'unchanged', 'waiting', 'stale_release', 'bootstrapped', 'verified_without_deployment'] else 1
    except ReleasePending:
        print(json.dumps({'outcome': 'waiting_for_successful_ci'}))
        return 0
    except BlockingIOError:
        print(json.dumps({'outcome': 'busy'}))
        return 0
    except Exception:
        print(json.dumps({'outcome': 'verification_or_operation_failed', 'details': 'withheld'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
