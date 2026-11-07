from contextlib import contextmanager
import base64
from dataclasses import replace
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
from migration_transition import MigrationTransition
from fixtures.migration_transition import recovery_receipt
from release_record import ReleaseRecord, deployment_contract, runtime_contract
from migration_record import descriptor_summary
from fixtures.migration_transition import catalogue
from test_migration_record import ENGINE_IDENTITY, HANGFIRE_IDENTITY, engine_dependencies
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
    def runtime_case(self, migration=False):
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
            policy = None
            if migration:
                policy = {'runtime_contract_sha256': runtime_contract(ROOT), 'engine_sha256': ENGINE_IDENTITY,
                          'hangfire_sha256': HANGFIRE_IDENTITY, 'legacy_schema_sha256': catalogue(1)['baseline_schema_sha256']}
                names = ['Hangfire.AspNetCore', 'Hangfire.Core', 'Hangfire.NetCore', 'Hangfire.Storage.SQLite', 'sqlite-net-pcl']
                api_deps = {'libraries': {name + '/1.0.0': {'type': 'package', 'sha512': 'sha512-' + base64.b64encode(b'a' * 64).decode()} for name in names}}
                state['metadata'] = {'migration-catalogue.json': catalogue(1), 'Ignite.Api.deps.json': api_deps,
                                     'Ignite.Migrations.deps.json': engine_dependencies()}
                state['database_inspection'] = {'schema': 1, 'schema_sha256': catalogue(1)['baseline_schema_sha256'], 'history': None}
            (root / 'compose.json').write_text(json.dumps(config))
            state_path = root / 'docker-state.json'
            state_path.write_text(json.dumps(state))
            curl = root / 'curl'
            curl.write_text('#!/bin/sh\nprintf 200\n')
            curl.chmod(0o700)
            environment = {**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'], 'RESTIC_PASSWORD': 'fixture', 'RESTIC_REPOSITORY': 'fixture',
                           'R2_ACCESS_KEY_ID': 'fixture', 'R2_SECRET_ACCESS_KEY': 'fixture'}
            docker = [sys.executable, str(ROOT / 'scripts/fixtures/deployment_docker.py'), str(root)]
            contract = deployment_contract(ROOT, migration_protocol=migration)
            runtime = DockerRuntime(ROOT, anchor, contract, 'f' * 64, docker=docker, environment=environment, migration_policy=policy)
            release = ReleaseRecord('e' * 40, 2, 1, 2, contract, tuple(next_images.items()), 'sha256:' + 'd' * 64)
            if migration:
                release = replace(release, migrations=descriptor_summary(catalogue(1)), migration_engine_sha256=ENGINE_IDENTITY, hangfire_sha256=HANGFIRE_IDENTITY)
            prior = {'images': prior_images, 'source_sha': 'c' * 40, 'order': [1, 1], 'artifact_digest': None}
            yield runtime, release, prior, workspace, state_path, docker

    def test_migration_preflight_binds_metadata_and_quiesces_only_owned_writers(self):
        with self.runtime_case(migration=True) as (runtime, release, prior, workspace, state_path, docker):
            plan = runtime.preflight(release, prior, workspace)
            self.assertEqual(plan['mode'], 'adopt')
            before = json.loads(state_path.read_text())
            self.assertTrue(before['containers']['backend']['running'])
            self.assertTrue(before['containers']['backup']['running'])
            with self.assertRaises(OperationFailed):
                runtime.inspect_stopped_database(workspace)
            commands = json.loads(state_path.read_text())['commands']
            self.assertFalse(any('inspect-stopped' in row for row in commands))
            runtime.quiesce(workspace)
            runtime.require_quiesced(workspace)
            self.assertEqual(runtime.inspect_stopped_database(workspace), plan['before'])
            after = json.loads(state_path.read_text())
            self.assertFalse(after['containers']['backend']['running'])
            self.assertFalse(after['containers']['backup']['running'])
            for name in ['frontend', 'caddy', 'alloy', 'watchtower']:
                self.assertEqual(after['containers'][name], before['containers'][name])
            runtime.cleanup(workspace)

    def test_migration_runtime_admits_verified_target_but_refuses_incompatible_rollback(self):
        with self.runtime_case(migration=True) as (runtime, release, prior, workspace, state_path, docker):
            plan = runtime.preflight(release, prior, workspace)
            transition = MigrationTransition(workspace)
            transition.prepare(release, plan)
            runtime.quiesce(workspace)
            self.assertEqual(transition.migrate(runtime, recovery_receipt()), 'verified')
            runtime.switch_backend(release, workspace)
            runtime.switch_dependents(release, workspace)
            runtime.verify(dict(release.images), workspace)
            self.assertEqual(transition.recover(runtime), 'committed')
            before = json.loads(state_path.read_text())['updated']
            with self.assertRaises(OperationFailed):
                runtime.rollback(prior, workspace)
            self.assertEqual(json.loads(state_path.read_text())['updated'], before)
            runtime.cleanup(workspace)

    def test_unexpected_stopped_writable_consumer_blocks_quiescence(self):
        with self.runtime_case(migration=True) as (runtime, release, prior, workspace, state_path, docker):
            runtime.preflight(release, prior, workspace)
            state = json.loads(state_path.read_text())
            state['containers']['foreign'] = {**state['containers']['frontend'], 'id': 'foreign', 'running': False,
                'mounts': [{'Type': 'bind', 'Source': '/volumes/ignite-for-spotify_ignite-data/nested', 'Destination': '/foreign', 'RW': True}]}
            state_path.write_text(json.dumps(state))
            with self.assertRaises(OperationFailed):
                runtime.quiesce(workspace)
            after = json.loads(state_path.read_text())
            self.assertTrue(after['containers']['backend']['running'] and after['containers']['backup']['running'])
            self.assertEqual(after['updated'], [])
            alias = workspace.parent / 'data-alias'
            alias.symlink_to('/volumes/ignite-for-spotify_ignite-data')
            after['containers']['foreign']['mounts'][0]['Source'] = str(alias)
            state_path.write_text(json.dumps(after))
            with self.assertRaises(OperationFailed):
                runtime.quiesce(workspace)
            self.assertTrue(json.loads(state_path.read_text())['containers']['backend']['running'])
            runtime.cleanup(workspace)

    def test_actual_image_dependency_mismatch_is_rejected_before_downtime(self):
        with self.runtime_case(migration=True) as (runtime, release, prior, workspace, state_path, docker):
            state = json.loads(state_path.read_text())
            state['metadata']['Ignite.Migrations.deps.json']['libraries']['dbup-core/1.0.0']['sha512'] = 'sha512-' + base64.b64encode(b'b' * 64).decode()
            state_path.write_text(json.dumps(state))
            with self.assertRaises(OperationFailed):
                runtime.preflight(release, prior, workspace)
            after = json.loads(state_path.read_text())
            self.assertTrue(after['containers']['backend']['running'] and after['containers']['backup']['running'])
            self.assertEqual(after['updated'], [])
            runtime.cleanup(workspace)

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

    def test_alloy_positions_volume_is_admitted_but_unlisted_volumes_are_refused(self):
        with self.runtime_case() as (runtime, release, prior, workspace, state_path, docker):
            state = json.loads(state_path.read_text())
            self.assertIn('ignite-for-spotify_alloy-data', {m['Name'] for m in state['containers']['alloy']['mounts']})
            runtime.preflight(release, prior, workspace)
            runtime.cleanup(workspace)
            state['containers']['alloy']['mounts'].append({'Type': 'volume', 'Name': 'ignite-for-spotify_unlisted', 'RW': True,
                                                           'Source': '/volumes/ignite-for-spotify_unlisted', 'Destination': '/unlisted'})
            state_path.write_text(json.dumps(state))
            with self.assertRaisesRegex(OperationFailed, 'physical_volume_mount_mismatch'):
                runtime.preflight(release, prior, workspace)
            self.assertEqual(json.loads(state_path.read_text())['updated'], [])
            runtime.cleanup(workspace)

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
