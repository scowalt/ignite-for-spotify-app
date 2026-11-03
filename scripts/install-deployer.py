import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from deployment_runtime import save_metadata
from release_record import deployment_contract
from release_signature import COSIGN_SHA256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-id', required=True)
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
        policy = {'schema': 1, 'operator_sha': bundle.name, 'repository_id': args.repository_id,
                  'contract_sha256': deployment_contract(home / 'Code/ignite-for-spotify-app')}
        policy_path = state / 'policy.json'
        if policy_path.is_symlink() or (policy_path.exists() and json.loads(policy_path.read_text()) != policy):
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
