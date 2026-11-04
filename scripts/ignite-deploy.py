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

from deployment_runtime import DockerRuntime
from deployment_transaction import Deployment, validate_migration_policy
from release_record import MigrationDependencyPolicy, ReleasePending, ReleaseRecord, deployment_contract, runtime_contract
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


def unique_fields(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate operator field.')
        value[key] = item
    return value


def private_json(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077 or metadata.st_size > 65536 or metadata.st_nlink != 1:
            raise ValueError('Invalid operator file.')
        return json.loads(stream.read(65537), object_pairs_hook=unique_fields)


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
        fields = {'schema', 'contract_sha256', 'repository_id', 'operator_sha'}
        if policy.get('schema') == 2:
            fields.add('migration_policy')
        if (set(policy) != fields or type(policy['schema']) is not int or policy['schema'] not in [1, 2] or
                any(not isinstance(policy[key], str) or not re.fullmatch(r'[a-f0-9]{64}', policy[key]) for key in ['contract_sha256', 'repository_id']) or
                not re.fullmatch(r'[a-f0-9]{40}', policy['operator_sha'])):
            raise ValueError('Invalid deployment policy.')
        bundle = Path(__file__).resolve().parents[1]
        if bundle.name != policy['operator_sha']:
            raise ValueError('Operator bundle version differs from policy.')
        checkout = Path.home() / 'Code/ignite-for-spotify-app'
        anchor = Path.home() / 'Code/ignite-for-spotify-2/docker'
        migration_policy = None
        dependencies = None
        if policy['schema'] == 2:
            migration_policy = validate_migration_policy(policy['migration_policy'])
            if (deployment_contract(bundle, migration_protocol=True) != policy['contract_sha256'] or
                    runtime_contract(checkout) != migration_policy['runtime_contract_sha256'] or args.action == 'bootstrap'):
                raise ValueError('Reviewed migration operator/configuration differs.')
            dependencies = MigrationDependencyPolicy(migration_policy['engine_sha256'], migration_policy['hangfire_sha256'])
        elif deployment_contract(checkout) != policy['contract_sha256']:
            raise ValueError('Installed contract differs from policy.')
        if args.action != 'bootstrap':
            state = deployment.status()
            if (state['schema'] != policy['schema'] or state['contract_sha256'] != policy['contract_sha256'] or
                    (migration_policy is not None and state['migration_policy'] != migration_policy)):
                raise ValueError('Ledger and operator policy differ; no automatic conversion.')
        runtime = DockerRuntime(checkout, anchor, policy['contract_sha256'], policy['repository_id'], migration_policy=migration_policy)
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
                outcome = 'waiting' if args.action == 'check' else deployment.run(None, runtime)
                if outcome != 'waiting':
                    print(json.dumps({'outcome': outcome}))
                    return 0 if outcome in ['deployed', 'unchanged'] else 1
                verifier = SignatureVerifier(Path.home() / '.local/lib/ignite-deployer/tools/cosign-v3.1.4')
                known_artifact = deployment.status()['active']['artifact_digest'] if args.action == 'once' else None
                release = load_release(policy['contract_sha256'], docker=runtime.docker, verifier=verifier, known_artifact=known_artifact,
                                       migration_dependencies=dependencies)
                if release is None:
                    print(json.dumps({'outcome': 'unchanged'}))
                    return 0
                if args.action == 'check':
                    outcome = deployment.check(release, runtime)
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
