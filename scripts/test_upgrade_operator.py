import hashlib
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from deployment_transaction import Deployment
from release_record import CONTRACT_PATHS, MIGRATION_CONTRACT_PATHS, deployment_contract, runtime_contract
from test_deployment_transaction import image_set
from test_migration_deployment import POLICY, state_hash


ROOT = Path(__file__).resolve().parents[1]
OLD, NEW = 'a' * 40, 'b' * 40


def populate(bundle, checkout=None):
    for base, names in [(bundle, CONTRACT_PATHS + MIGRATION_CONTRACT_PATHS)] + ([(checkout, CONTRACT_PATHS)] if checkout else []):
        for name in names:
            target = base / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
    (bundle / 'scripts').mkdir(exist_ok=True)
    for path in (ROOT / 'scripts').glob('*.py'):
        shutil.copyfile(path, bundle / 'scripts' / path.name)
    for name in ['ignite-deployer.service', 'ignite-deployer.timer']:
        target = bundle / 'ops/deployer' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'ops/deployer' / name, target)


class OperatorUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.library = self.home / '.local/lib/ignite-deployer'
        self.state_root = self.home / '.local/state/ignite-deployer'
        self.checkout = self.home / 'Code/ignite-for-spotify-app'
        populate(self.library / OLD, self.checkout)
        populate(self.library / NEW)
        (self.library / NEW / CONTRACT_PATHS[-2]).write_text('reviewed change')
        self.library.chmod(0o700)
        (self.library / 'tools').mkdir()
        self.signer = self.library / 'tools/cosign-v3.1.4'
        self.signer.write_bytes(b'fixture signer')
        (self.library / 'current').symlink_to(self.library / OLD)
        deployment = Deployment(self.state_root)
        deployment.bootstrap({'source_sha': 'c' * 40, 'images': image_set('c'), 'order': [42, 1], 'artifact_digest': None}, deployment_contract(self.checkout))
        pins = POLICY | {'runtime_contract_sha256': runtime_contract(self.checkout)}
        deployment.upgrade_migrations(deployment_contract(self.library / OLD, migration_protocol=True), pins, expected_state_sha256=state_hash(deployment.status()))
        self.pins = pins
        self.policy = {'schema': 2, 'operator_sha': OLD, 'repository_id': 'f' * 64, 'migration_policy': pins,
                       'contract_sha256': deployment_contract(self.library / OLD, migration_protocol=True)}
        (self.state_root / 'policy.json').write_text(json.dumps(self.policy))
        (self.state_root / 'policy.json').chmod(0o600)
        self.deployment = deployment

    def run_upgrade(self, *arguments, state_sha=None):
        path = self.library / NEW / 'scripts/upgrade-operator.py'
        spec = importlib.util.spec_from_file_location('upgrade_operator_under_test', path)
        module = importlib.util.module_from_spec(spec)
        import sys
        sys.path.insert(0, str(path.parent))
        try:
            with mock.patch.dict(os.environ, {'HOME': str(self.home)}), mock.patch('pathlib.Path.home', return_value=self.home):
                spec.loader.exec_module(module)
                module.COSIGN_SHA256 = hashlib.sha256(b'fixture signer').hexdigest()
                sha = state_sha or state_hash(self.deployment.status())
                output = io.StringIO()
                with redirect_stdout(output), mock.patch('sys.argv', ['x', '--expected-state-sha256', sha, *arguments]):
                    code = module.main()
        finally:
            sys.path.remove(str(path.parent))
        return code, json.loads(output.getvalue())

    def test_report_mode_changes_nothing(self):
        before = self.deployment.status()
        code, report = self.run_upgrade()
        self.assertEqual(0, code)
        self.assertFalse(report['applied'])
        self.assertEqual(before, self.deployment.status())
        self.assertEqual(self.library / OLD, (self.library / 'current').resolve())
        self.assertEqual(OLD, json.loads((self.state_root / 'policy.json').read_text())['operator_sha'])

    def test_apply_moves_ledger_policy_and_operator_together_and_status_works_from_the_new_bundle(self):
        before = self.deployment.status()
        code, report = self.run_upgrade('--apply')
        self.assertEqual(0, code)
        self.assertTrue(report['applied'])
        contract = deployment_contract(self.library / NEW, migration_protocol=True)
        after = self.deployment.status()
        self.assertEqual(contract, after['contract_sha256'])
        self.assertEqual(before | {'contract_sha256': contract}, after)
        policy = json.loads((self.state_root / 'policy.json').read_text())
        self.assertEqual((NEW, contract), (policy['operator_sha'], policy['contract_sha256']))
        self.assertEqual(self.library / NEW, (self.library / 'current').resolve())
        evidence = self.state_root / ('operator-transition-' + NEW[:7])
        self.assertEqual(before, json.loads((evidence / 'before-state.json').read_text()))
        result = subprocess.run(['python3', str(self.library / NEW / 'scripts/ignite-deploy.py'), 'status'],
                                env={'PATH': os.environ['PATH'], 'HOME': str(self.home)}, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(after, json.loads(result.stdout))

    def test_apply_moves_the_runtime_pin_to_the_host_configuration_matching_the_bundle(self):
        for base in [self.library / NEW, self.checkout]:
            (base / 'docker/docker-compose.prod.yml').write_text('reviewed host configuration')
        before = self.deployment.status()
        code, report = self.run_upgrade('--apply')
        self.assertEqual(0, code)
        pins = self.pins | {'runtime_contract_sha256': runtime_contract(self.checkout)}
        self.assertEqual((self.pins['runtime_contract_sha256'], pins['runtime_contract_sha256']),
                         (report['previous_runtime_contract'], report['new_runtime_contract']))
        self.assertNotEqual(report['previous_runtime_contract'], report['new_runtime_contract'])
        after = self.deployment.status()
        self.assertEqual(before | {'contract_sha256': report['new_contract'], 'migration_policy': pins}, after)
        self.assertEqual(pins, json.loads((self.state_root / 'policy.json').read_text())['migration_policy'])
        result = subprocess.run(['python3', str(self.library / NEW / 'scripts/ignite-deploy.py'), 'status'],
                                env={'PATH': os.environ['PATH'], 'HOME': str(self.home)}, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(after, json.loads(result.stdout))

    def test_runtime_change_without_the_matching_host_configuration_is_refused_without_mutation(self):
        (self.library / NEW / 'docker/docker-compose.prod.yml').write_text('reviewed host configuration')
        before = self.deployment.status()
        code, _ = self.run_upgrade('--apply')
        self.assertEqual(1, code)
        self.assertEqual(before, self.deployment.status())
        self.assertEqual(self.policy, json.loads((self.state_root / 'policy.json').read_text()))
        self.assertEqual(self.library / OLD, (self.library / 'current').resolve())

    def test_stale_fingerprint_unchanged_contract_and_unexpected_operator_are_refused_without_mutation(self):
        before = self.deployment.status()
        code, _ = self.run_upgrade('--apply', state_sha='0' * 64)
        self.assertEqual(1, code)
        (self.library / 'current').unlink()
        (self.library / 'current').symlink_to(self.library / NEW)
        code, _ = self.run_upgrade('--apply')
        self.assertEqual(1, code)
        self.assertEqual(before, self.deployment.status())
        self.assertEqual(OLD, json.loads((self.state_root / 'policy.json').read_text())['operator_sha'])

    def test_unchanged_contract_is_refused(self):
        shutil.copyfile(ROOT / CONTRACT_PATHS[-2], self.library / NEW / CONTRACT_PATHS[-2])
        code, _ = self.run_upgrade('--apply')
        self.assertEqual(1, code)
        self.assertEqual(OLD, json.loads((self.state_root / 'policy.json').read_text())['operator_sha'])


if __name__ == '__main__':
    unittest.main()
