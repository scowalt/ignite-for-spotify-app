import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from deployment_runtime import save_metadata
from deployment_transaction import Deployment, validate_migration_policy
from release_record import deployment_contract, runtime_contract
from release_signature import COSIGN_SHA256


def private_policy(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate policy field.')
            value[key] = item
        return value
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077 or
                metadata.st_nlink != 1 or metadata.st_size > 65536):
            raise ValueError('Policy is not private and bounded.')
        return json.loads(stream.read(65537), object_pairs_hook=unique)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-id', required=True)
    parser.add_argument('--migration-policy', type=Path)
    args = parser.parse_args()
    try:
        os.umask(0o077)
        bundle = Path(__file__).resolve().parents[1]
        if not re.fullmatch(r'[a-f0-9]{40}', bundle.name) or not re.fullmatch(r'[a-f0-9]{64}', args.repository_id):
            raise ValueError('Invalid reviewed bundle identity.')
        home = Path.home()
        library = home / '.local/lib/ignite-deployer'
        state = home / '.local/state/ignite-deployer'
        units = home / '.config/systemd/user'
        for path in [library, state]:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
                raise ValueError('Operator directory ownership differs.')
        units.mkdir(parents=True, exist_ok=True)
        signer = library / 'tools/cosign-v3.1.4'
        with signer.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != COSIGN_SHA256:
                raise ValueError('Signer integrity differs.')
        checkout = home / 'Code/ignite-for-spotify-app'
        policy = {'schema': 1, 'operator_sha': bundle.name, 'repository_id': args.repository_id,
                  'contract_sha256': deployment_contract(checkout)}
        if args.migration_policy is not None:
            pins = validate_migration_policy(private_policy(args.migration_policy))
            if runtime_contract(checkout) != pins['runtime_contract_sha256']:
                raise ValueError('Reviewed host configuration differs.')
            policy.update(schema=2, contract_sha256=deployment_contract(bundle, migration_protocol=True), migration_policy=pins)
        if (state / 'state.json').exists() or (state / 'state.json').is_symlink() or args.migration_policy is not None:
            ledger = Deployment(state).status()
            if (ledger['schema'] != policy['schema'] or ledger['contract_sha256'] != policy['contract_sha256'] or
                    (policy['schema'] == 2 and ledger['migration_policy'] != policy['migration_policy'])):
                raise ValueError('Reviewed ledger transition required; no automatic upgrade.')
        policy_path = state / 'policy.json'
        if policy_path.is_symlink() or (policy_path.exists() and private_policy(policy_path) != policy):
            raise ValueError('Existing policy differs; no automatic replacement.')
        current = library / 'current'
        if current.exists() or current.is_symlink():
            if not current.is_symlink() or current.resolve() != bundle:
                raise ValueError('Existing operator differs; no automatic replacement.')
        for name in ['ignite-deployer.service', 'ignite-deployer.timer']:
            target = units / name
            source = bundle / 'ops/deployer' / name
            if target.is_symlink() or (target.exists() and target.read_bytes() != source.read_bytes()):
                raise ValueError('Existing user unit differs; no automatic replacement.')
        if not policy_path.exists():
            save_metadata(policy_path, policy)
        if not current.is_symlink():
            current.symlink_to(bundle)
        for name in ['ignite-deployer.service', 'ignite-deployer.timer']:
            target = units / name
            if not target.exists():
                with target.open('xb') as stream:
                    stream.write((bundle / 'ops/deployer' / name).read_bytes())
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        subprocess.run(['systemd-analyze', '--user', 'verify', str(units / 'ignite-deployer.service'), str(units / 'ignite-deployer.timer')],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        print(json.dumps({'outcome': 'installed_not_enabled', 'operator_sha': bundle.name}))
        return 0
    except Exception:
        print(json.dumps({'outcome': 'installation_stopped', 'details': 'withheld'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
