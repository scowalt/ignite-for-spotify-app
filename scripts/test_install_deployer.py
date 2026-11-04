import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from deployment_transaction import Deployment
from release_record import CONTRACT_PATHS, MIGRATION_CONTRACT_PATHS, deployment_contract, runtime_contract
from test_deployment_transaction import image_set
from test_migration_deployment import POLICY, state_hash


ROOT = Path(__file__).resolve().parents[1]
COSIGN = os.environ.get('IGNITE_COSIGN_FIXTURE')


@unittest.skipUnless(COSIGN, 'Requires the checksum-pinned Cosign binary, without credentials.')
class InstallerNativeTests(unittest.TestCase):
    def test_migration_install_requires_reviewed_pins_and_matching_ledger_without_enabling_units(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            checkout = home / 'Code/ignite-for-spotify-app'
            library = home / '.local/lib/ignite-deployer'
            bundle = library / ('e' * 40)
            for base, names in [(checkout, CONTRACT_PATHS), (bundle, CONTRACT_PATHS + MIGRATION_CONTRACT_PATHS)]:
                for name in names:
                    target = base / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / name, target)
            scripts = bundle / 'scripts'
            scripts.mkdir(exist_ok=True)
            for path in (ROOT / 'scripts').glob('*.py'):
                shutil.copyfile(path, scripts / path.name)
            for name in ['ignite-deployer.service', 'ignite-deployer.timer']:
                path = bundle / 'ops/deployer' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / 'ops/deployer' / name, path)
            library.chmod(0o700)
            signer = library / 'tools/cosign-v3.1.4'
            signer.parent.mkdir()
            shutil.copyfile(COSIGN, signer)
            deployment = Deployment(home / '.local/state/ignite-deployer')
            deployment.bootstrap({'source_sha': 'a' * 40, 'images': image_set('a'), 'order': [42, 1], 'artifact_digest': None}, deployment_contract(checkout))
            pins = POLICY | {'runtime_contract_sha256': runtime_contract(checkout)}
            input_path = home / 'reviewed-policy.json'
            input_path.write_text(json.dumps(pins))
            input_path.chmod(0o600)
            bin_path = home / 'bin'
            bin_path.mkdir()
            log = home / 'system-commands.jsonl'
            for name in ['systemctl', 'systemd-analyze']:
                executable = bin_path / name
                executable.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nargs=sys.argv[1:]\nassert "start" not in args and "enable" not in args\nwith Path(' + repr(str(log)) + ').open("a") as out: out.write(json.dumps(args)+"\\n")\n')
                executable.chmod(0o700)
            command = ['python3', str(scripts / 'install-deployer.py'), '--repository-id', 'f' * 64, '--migration-policy', str(input_path)]
            environment = {**os.environ, 'HOME': str(home), 'PATH': str(bin_path) + ':' + os.environ['PATH']}
            before = deployment.status()
            denied = subprocess.run(command, env=environment, capture_output=True, text=True)
            self.assertEqual(denied.returncode, 1)
            self.assertEqual(deployment.status(), before)
            self.assertFalse((deployment.root / 'policy.json').exists())
            self.assertFalse(log.exists())
            deployment.upgrade_migrations(deployment_contract(bundle, migration_protocol=True), pins, expected_state_sha256=state_hash(before))
            accepted = subprocess.run(command, env=environment, capture_output=True, text=True)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            self.assertEqual(json.loads(accepted.stdout)['outcome'], 'installed_not_enabled')
            policy = json.loads((deployment.root / 'policy.json').read_text())
            self.assertEqual(policy['schema'], 2)
            self.assertEqual(policy['migration_policy'], pins)
            self.assertEqual((library / 'current').resolve(), bundle)
            commands = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(commands[0], ['--user', 'daemon-reload'])
            changed = pins | {'engine_sha256': '9' * 64}
            input_path.write_text(json.dumps(changed))
            stopped = subprocess.run(command, env=environment, capture_output=True, text=True)
            self.assertEqual(stopped.returncode, 1)
            self.assertEqual(json.loads((deployment.root / 'policy.json').read_text()), policy)


if __name__ == '__main__':
    unittest.main()
