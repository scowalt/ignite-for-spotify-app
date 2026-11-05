import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

from deployment_runtime import save_metadata
from deployment_transaction import Deployment, validate_migration_policy
from release_record import deployment_contract, runtime_contract
from release_signature import COSIGN_SHA256

_installer = importlib.util.spec_from_file_location('install_deployer', Path(__file__).with_name('install-deployer.py'))
install_deployer = importlib.util.module_from_spec(_installer)
_installer.loader.exec_module(install_deployer)


def fingerprint(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def replace_link(link, target):
    temporary = link.with_name('.current-' + target.name)
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, link)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-state-sha256', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        os.umask(0o077)
        bundle = Path(__file__).resolve().parents[1]
        if not re.fullmatch(r'[a-f0-9]{40}', bundle.name) or not re.fullmatch(r'[a-f0-9]{64}', args.expected_state_sha256):
            raise ValueError('Invalid bundle or state identity.')
        home = Path.home()
        library = home / '.local/lib/ignite-deployer'
        state_root = home / '.local/state/ignite-deployer'
        checkout = home / 'Code/ignite-for-spotify-app'
        if bundle.parent != library.resolve():
            raise ValueError('Bundle is not in the operator library.')
        policy_path = state_root / 'policy.json'
        policy = install_deployer.private_policy(policy_path)
        if policy.get('schema') != 2 or set(policy) != {'schema', 'contract_sha256', 'repository_id', 'operator_sha', 'migration_policy'}:
            raise ValueError('Policy is not a reviewed schema-v2 policy.')
        pins = validate_migration_policy(policy['migration_policy'])
        previous = library / policy['operator_sha']
        current = library / 'current'
        if not current.is_symlink() or current.resolve() != previous.resolve() or previous == bundle:
            raise ValueError('Installed operator is not the expected previous bundle.')
        if runtime_contract(checkout) != pins['runtime_contract_sha256'] or runtime_contract(bundle) != pins['runtime_contract_sha256']:
            raise ValueError('Host or bundle runtime configuration differs from the reviewed pin.')
        for name in ['ignite-deployer.service', 'ignite-deployer.timer']:
            if (bundle / 'ops/deployer' / name).read_bytes() != (previous / 'ops/deployer' / name).read_bytes():
                raise ValueError('Unit definitions differ; no automatic replacement.')
        signer = library / 'tools/cosign-v3.1.4'
        with signer.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != COSIGN_SHA256:
                raise ValueError('Signer integrity differs.')
        contract = deployment_contract(bundle, migration_protocol=True)
        deployment = Deployment(state_root)
        state = deployment.status()
        report = {'previous_operator': previous.name, 'new_operator': bundle.name, 'previous_contract': policy['contract_sha256'],
                  'new_contract': contract, 'state_fingerprint': fingerprint(state), 'applied': False}
        if state['migration_policy'] != pins or state['contract_sha256'] != policy['contract_sha256'] or state['transaction'] is not None:
            raise ValueError('Ledger and policy are not an idle matching pair.')
        if report['state_fingerprint'] != args.expected_state_sha256:
            raise ValueError('Ledger differs from the reviewed state.')
        if contract == policy['contract_sha256']:
            raise ValueError('Contract is unchanged.')
        if args.apply:
            lock = os.open(state_root / 'poll.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                evidence = state_root / ('operator-transition-' + bundle.name[:7])
                evidence.mkdir(mode=0o700)
                save_metadata(evidence / 'before-state.json', state)
                save_metadata(evidence / 'before-policy.json', policy)
                deployment.upgrade_contract(contract, expected_state_sha256=args.expected_state_sha256)
                save_metadata(policy_path, policy | {'contract_sha256': contract, 'operator_sha': bundle.name})
                replace_link(current, bundle)
            finally:
                os.close(lock)
            report['applied'] = True
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({'outcome': 'operator_transition_stopped', 'details': 'withheld'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
