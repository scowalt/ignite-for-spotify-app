from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from deployment_runtime import DockerRuntime, IMAGE_FORMAT
from deployment_process import OperationFailed
from release_record import ReleaseRecord, deployment_contract
from test_production_config import render

ROOT = Path(__file__).resolve().parents[1]


class RuntimeGuardTests(unittest.TestCase):
    def test_unrecognized_project_is_refused_before_backup_or_service_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / 'docker.py'
            docker.write_text('import json,sys\nassert sys.argv[1]=="inspect"\nprint(json.dumps({"project":"wrong"}))\n')
            runtime = DockerRuntime(ROOT, root, deployment_contract(ROOT), 'a' * 64,
                                    docker=[sys.executable, str(docker)], environment={'RESTIC_PASSWORD': 'fixture'})
            images = {name: 'ghcr.io/scowalt/ignite-for-spotify-app/' + name + '@sha256:' + 'b' * 64 for name in ['backend', 'backup', 'frontend']}
            release = ReleaseRecord('c' * 40, 1, 1, 2, deployment_contract(ROOT), tuple(images.items()), 'sha256:' + 'd' * 64)
            prior = {'images': images, 'source_sha': 'c' * 40, 'order': [1, 1], 'artifact_digest': None}
            with self.assertRaises(OperationFailed):
                runtime.preflight(release, prior, root)

    @contextmanager
    def runtime_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / ('d' * 64)
            workspace.mkdir(mode=0o700)
            anchor = root / 'docker'
            anchor.mkdir()
            prior_images = {name: 'ghcr.io/scowalt/ignite-for-spotify-app/' + name + '@sha256:' + 'a' * 64 for name in ['backend', 'backup', 'frontend']}
            next_images = {name: reference.replace('a' * 64, 'b' * 64) for name, reference in prior_images.items()}
            config = render({name.upper() + '_IMAGE': reference for name, reference in prior_images.items()})
            bindings = {'caddy': {'/etc/caddy/Caddyfile': str(root / 'Caddyfile')},
                        'alloy': {'/etc/alloy/config.alloy': str(anchor / 'alloy/config.alloy'), '/var/run/docker.sock': '/var/run/docker.sock'},
                        'watchtower': {'/var/run/docker.sock': '/var/run/docker.sock', '/config.json': '/home/scowalt/.docker/config.json'}}
            for name, paths in bindings.items():
                for mount in config['services'][name]['volumes']:
                    if mount['type'] == 'bind':
                        mount['source'] = paths[mount['target']]
            containers = {}
            for name, service in config['services'].items():
                mounts = []
                for mount in service.get('volumes', []):
                    physical = config['volumes'][mount['source']]['name'] if mount['type'] == 'volume' else None
                    mounts.append({'Type': mount['type'], 'Name': physical, 'Source': '/volumes/' + physical if physical else mount['source'],
                                   'Destination': mount['target'], 'RW': not mount.get('read_only', False)})
                reference = service['image']
                containers[name] = {'id': name, 'image_id': 'sha256:' + hashlib.sha256(reference.encode()).hexdigest(), 'image': reference,
                                    'running': name != 'watchtower', 'started': 'original', 'health': 'healthy', 'project': 'ignite-for-spotify',
                                    'network': service.get('network_mode') or config['networks']['default']['name'], 'dns': service.get('dns', []),
                                    'restart': service.get('restart'), 'ports': {str(p['target']) + '/' + p.get('protocol', 'tcp'): [{'HostIp': p.get('host_ip', ''), 'HostPort': str(p['published'])}] for p in service.get('ports', [])},
                                    'logging': service.get('labels', {}).get('logging'), 'mounts': mounts}
            state = {'containers': containers, 'templates': containers, 'environments': {name: service.get('environment', {}) for name, service in config['services'].items()},
                     'prior_source': 'c' * 40, 'candidate_source': 'e' * 40, 'candidate': next_images, 'pulled': [], 'updated': [], 'inspector': None}
            (root / 'compose.json').write_text(json.dumps(config))
            state_path = root / 'docker-state.json'
            state_path.write_text(json.dumps(state))
            curl = root / 'curl'
            curl.write_text('#!/bin/sh\nprintf 200\n')
            curl.chmod(0o700)
            environment = {**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'], 'RESTIC_PASSWORD': 'fixture', 'RESTIC_REPOSITORY': 'fixture',
                           'R2_ACCESS_KEY_ID': 'fixture', 'R2_SECRET_ACCESS_KEY': 'fixture'}
            docker = [sys.executable, str(ROOT / 'scripts/fixtures/deployment_docker.py'), str(root)]
            runtime = DockerRuntime(ROOT, anchor, deployment_contract(ROOT), 'f' * 64, docker=docker, environment=environment)
            release = ReleaseRecord('e' * 40, 2, 1, 2, deployment_contract(ROOT), tuple(next_images.items()), 'sha256:' + 'd' * 64)
            prior = {'images': prior_images, 'source_sha': 'c' * 40, 'order': [1, 1], 'artifact_digest': None}
            yield runtime, release, prior, workspace, state_path, docker

    def test_runtime_adapter_preserves_configuration_during_update_and_image_only_rollback(self):
        with self.runtime_case() as (runtime, release, prior, workspace, state_path, docker):
            runtime.preflight(release, prior, workspace)
            self.assertEqual(json.loads(state_path.read_text())['updated'], [])
            subprocess.run([*docker, 'stop', 'ignite-backup'], check=True)
            runtime.switch_backend(release, workspace)
            runtime.switch_dependents(release, workspace)
            runtime.verify(dict(release.images), workspace)
            runtime.rollback(prior, workspace)
            runtime.verify(prior['images'], workspace)
            runtime.cleanup(workspace)
            final = json.loads(state_path.read_text())
            self.assertEqual({name: final['containers'][name]['image'] for name in prior['images']}, prior['images'])
            self.assertEqual(final['containers']['caddy']['id'], 'caddy')
            self.assertIsNone(final['inspector'])
            self.assertNotIn('RESTIC_PASSWORD', (workspace / 'runtime.json').read_text())

    def test_changed_digest_override_is_refused_before_service_mutation(self):
        with self.runtime_case() as (runtime, release, prior, workspace, state_path, docker):
            runtime.preflight(release, prior, workspace)
            override = workspace / 'candidate.compose.json'
            value = json.loads(override.read_text())
            value['services']['backend']['image'] = prior['images']['backend']
            override.write_text(json.dumps(value))
            subprocess.run([*docker, 'stop', 'ignite-backup'], check=True)
            with self.assertRaises(OperationFailed):
                runtime.switch_backend(release, workspace)
            self.assertEqual(json.loads(state_path.read_text())['updated'], [])
            runtime.cleanup(workspace)

    def test_rollback_refuses_unrecognized_drift_before_touching_any_service(self):
        with self.runtime_case() as (runtime, release, prior, workspace, state_path, docker):
            runtime.preflight(release, prior, workspace)
            state = json.loads(state_path.read_text())
            state['containers']['frontend']['restart'] = 'changed'
            state_path.write_text(json.dumps(state))
            with self.assertRaises(OperationFailed):
                runtime.rollback(prior, workspace)
            self.assertEqual(json.loads(state_path.read_text())['updated'], [])
            runtime.cleanup(workspace)

    def test_expected_missing_container_can_be_recreated_without_recreating_volumes(self):
        with self.runtime_case() as (runtime, release, prior, workspace, state_path, docker):
            runtime.preflight(release, prior, workspace)
            state = json.loads(state_path.read_text())
            del state['containers']['backend']
            state_path.write_text(json.dumps(state))
            runtime.rollback(prior, workspace)
            runtime.verify(prior['images'], workspace)
            final = json.loads(state_path.read_text())
            self.assertEqual(final['updated'], ['backend'])
            self.assertEqual(final['containers']['backup']['id'], 'backup')
            runtime.cleanup(workspace)

    @unittest.skipUnless(os.environ.get('IGNITE_BACKUP_FIXTURE_IMAGE'), 'Requires the isolated Docker fixture image.')
    def test_actual_image_metadata_accepts_absent_optional_docker_fields(self):
        result = subprocess.run(['docker', 'image', 'inspect', '--format', IMAGE_FORMAT, os.environ['IGNITE_BACKUP_FIXTURE_IMAGE']],
                                capture_output=True, text=True, check=False, timeout=30)
        self.assertEqual(result.returncode, 0)
        value = json.loads(result.stdout)
        self.assertIn(value['volumes'], [None, {}])
        self.assertEqual(value['os'], 'linux')
        self.assertEqual(value['arch'], 'amd64')


if __name__ == '__main__':
    unittest.main()
