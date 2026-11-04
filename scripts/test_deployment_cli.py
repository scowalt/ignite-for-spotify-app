from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from deployment_transaction import Deployment
from release_record import CONTRACT_PATHS, MIGRATION_CONTRACT_PATHS, deployment_contract, runtime_contract
from test_migration_deployment import POLICY, state_hash
from test_deployment_transaction import RuntimeFixture, InterruptedProcess, candidate, image_set

ROOT = Path(__file__).resolve().parents[1]


class DeploymentCliTests(unittest.TestCase):
    def test_migration_policy_status_requires_matching_explicitly_upgraded_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            checkout = home / 'Code/ignite-for-spotify-app'
            bundle = home / '.local/lib/ignite-deployer' / ('e' * 40)
            for base, names in [(checkout, CONTRACT_PATHS), (bundle, CONTRACT_PATHS + MIGRATION_CONTRACT_PATHS)]:
                for name in names:
                    target = base / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / name, target)
            scripts = bundle / 'scripts'
            scripts.mkdir(exist_ok=True)
            for path in (ROOT / 'scripts').glob('*.py'):
                shutil.copyfile(path, scripts / path.name)
            root = home / '.local/state/ignite-deployer'
            deployment = Deployment(root)
            deployment.bootstrap({'source_sha': 'a' * 40, 'images': image_set('a'), 'order': [42, 1], 'artifact_digest': None}, deployment_contract(checkout))
            contract = deployment_contract(bundle, migration_protocol=True)
            pins = POLICY | {'runtime_contract_sha256': runtime_contract(checkout)}
            policy = {'schema': 2, 'operator_sha': bundle.name, 'repository_id': 'f' * 64, 'contract_sha256': contract, 'migration_policy': pins}
            path = root / 'policy.json'
            path.write_text(json.dumps(policy))
            path.chmod(0o600)
            command = ['python3', str(scripts / 'ignite-deploy.py'), 'status']
            env = {**os.environ, 'HOME': str(home)}
            before = deployment.status()
            denied = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(denied.returncode, 1)
            self.assertEqual(deployment.status(), before)
            deployment.upgrade_migrations(contract, pins, expected_state_sha256=state_hash(before))
            accepted = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            self.assertEqual(json.loads(accepted.stdout), deployment.status())


    def test_status_and_check_do_not_mutate_an_interrupted_runtime_or_disclose_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            checkout = home / 'Code/ignite-for-spotify-app'
            for name in CONTRACT_PATHS:
                target = checkout / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            operator_sha = 'e' * 40
            scripts = home / '.local/lib/ignite-deployer' / operator_sha / 'scripts'
            scripts.mkdir(parents=True)
            for path in (ROOT / 'scripts').glob('*.py'):
                shutil.copyfile(path, scripts / path.name)
            state = home / '.local/state/ignite-deployer'
            deployment = Deployment(state)
            contract = deployment_contract(checkout)
            policy = state / 'policy.json'
            policy.write_text(json.dumps({'schema': 1, 'operator_sha': operator_sha, 'contract_sha256': contract, 'repository_id': 'f' * 64}))
            policy.chmod(0o600)
            active = {'source_sha': 'a' * 40, 'images': image_set('a'), 'order': [42, 1], 'artifact_digest': None}
            deployment.bootstrap(active, contract)
            release = candidate()
            release = type(release)(release.source_sha, release.run_id, release.run_attempt, release.run_number, contract, release.images, release.artifact_digest)
            runtime = RuntimeFixture()
            runtime.interrupt_dependents = True
            with self.assertRaises(InterruptedProcess):
                deployment.run(release, runtime)
            before = deployment.status()
            environment = {**os.environ, 'HOME': str(home), 'RESTIC_PASSWORD': 'fixture-private'}
            command = ['python3', str(scripts / 'ignite-deploy.py')]
            status = subprocess.run([*command, 'status'], env=environment, capture_output=True, text=True, check=False)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout), before)
            check = subprocess.run([*command, 'check'], env=environment, capture_output=True, text=True, check=False)
            self.assertEqual(check.returncode, 1)
            self.assertNotIn('fixture-private', status.stdout + status.stderr + check.stdout + check.stderr)
            self.assertEqual(deployment.status(), before)


if __name__ == '__main__':
    unittest.main()
