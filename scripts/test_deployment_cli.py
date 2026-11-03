from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from deployment_transaction import Deployment
from release_record import CONTRACT_PATHS, deployment_contract
from test_deployment_transaction import RuntimeFixture, InterruptedProcess, candidate, image_set

ROOT = Path(__file__).resolve().parents[1]


class DeploymentCliTests(unittest.TestCase):
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
