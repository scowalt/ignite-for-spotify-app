import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import time

from deployment_backup import BackupTool, bucket_inventory, INPUT_LIMIT, REMOTE_LIMIT
from deployment_process import OperationFailed, run
from release_record import deployment_contract, REPOSITORY

SERVICES = ('backend', 'backup', 'frontend')
ALL = (*SERVICES, 'caddy', 'alloy', 'watchtower')
FORMAT = '''{"id":{{json .Id}},"image_id":{{json .Image}},"image":{{json .Config.Image}},"running":{{json .State.Running}},"started":{{json .State.StartedAt}},"health":{{with index .State "Health"}}{{json .Status}}{{else}}null{{end}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"network":{{json .HostConfig.NetworkMode}},"dns":{{json .HostConfig.Dns}},"restart":{{json .HostConfig.RestartPolicy.Name}},"ports":{{json .HostConfig.PortBindings}},"logging":{{json (index .Config.Labels "logging")}},"mounts":{{json .Mounts}}}'''
IMAGE_FORMAT = '''{"id":{{json .Id}},"digests":{{json .RepoDigests}},"user":{{json (index .Config "User")}},"os":{{json .Os}},"arch":{{json .Architecture}},"volumes":{{json (index .Config "Volumes")}},"revision":{{with index .Config "Labels"}}{{json (index . "org.opencontainers.image.revision")}}{{else}}null{{end}},"source":{{with index .Config "Labels"}}{{json (index . "org.opencontainers.image.source")}}{{else}}null{{end}}}'''


def invariant(value):
    result = {key: value[key] for key in ['project', 'network', 'dns', 'restart', 'ports', 'logging', 'mounts']}
    result['mounts'] = sorted(result['mounts'], key=lambda mount: json.dumps(mount, sort_keys=True))
    return result


def save_metadata(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix='.runtime-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as output:
            json.dump(value, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)


class DockerRuntime:
    def __init__(self, checkout, anchor, contract, repository_id, *, docker=None, environment=None):
        self.checkout, self.anchor = Path(checkout), Path(anchor)
        self.contract, self.repository_id = contract, repository_id
        self.docker = docker or ['docker', '-H', 'unix:///var/run/docker.sock']
        self.environment = dict(os.environ if environment is None else environment)
        self.client_env = {key: self.environment[key] for key in ['PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONFIG', 'XDG_RUNTIME_DIR'] if key in self.environment}

    def _docker(self, args, timeout=90, limit=2 * 1024**2):
        return run([*self.docker, *args], env=self.client_env, timeout=timeout, limit=limit).decode()

    def _snapshot(self, names=ALL):
        result = {}
        for name in names:
            value = json.loads(self._docker(['inspect', '--format', FORMAT, 'ignite-' + name]))
            if value.get('project') != 'ignite-for-spotify':
                raise OperationFailed('runtime_project_mismatch')
            value['mounts'] = sorted(value['mounts'], key=lambda mount: json.dumps(mount, sort_keys=True))
            result[name] = value
        return result

    def _image(self, reference, revision=None):
        value = json.loads(self._docker(['image', 'inspect', '--format', IMAGE_FORMAT, reference]))
        if (reference not in (value['digests'] or []) or value['os'] != 'linux' or value['arch'] != 'amd64' or
                value['volumes'] or (revision is not None and
                (value['revision'] != revision or value['source'] != 'https://github.com/' + REPOSITORY))):
            raise OperationFailed('image_identity_mismatch')
        return value

    def _wire_size(self, reference, depth=0):
        manifest = json.loads(self._docker(['buildx', 'imagetools', 'inspect', reference, '--raw'], limit=256 * 1024))
        if 'manifests' in manifest:
            choices = [item for item in manifest['manifests'] if item.get('platform', {}).get('os') == 'linux' and item.get('platform', {}).get('architecture') == 'amd64']
            if depth or len(choices) != 1 or not re.fullmatch(r'sha256:[a-f0-9]{64}', choices[0].get('digest', '')):
                raise OperationFailed('candidate_manifest_platform_mismatch')
            return self._wire_size(reference.split('@')[0] + '@' + choices[0]['digest'], depth + 1)
        layers = manifest.get('layers')
        if not isinstance(layers, list) or not 1 <= len(layers) <= 128 or any(type(item.get('size')) is not int or item['size'] < 0 for item in layers):
            raise OperationFailed('candidate_image_size_unavailable')
        return sum(item['size'] for item in layers)

    def _environment(self, reference, image=False):
        args = ['image', 'inspect'] if image else ['inspect']
        values = json.loads(self._docker([*args, '--format', '{{json .Config.Env}}', reference])) or []
        return dict(value.split('=', 1) for value in values if '=' in value)

    def _compose(self, workspace, rollback=False):
        filename = 'prior.compose.json' if rollback else 'candidate.compose.json'
        return [*self.docker, 'compose', '-p', 'ignite-for-spotify', '--project-directory', str(self.anchor),
                '--env-file', '/dev/null', '-f', str(self.checkout / 'docker/docker-compose.prod.yml'),
                '-f', str(workspace / filename)]

    def _configuration(self, workspace, *, rollback=False, compare_live=True):
        config = json.loads(run([*self._compose(workspace, rollback), 'config', '--format', 'json'], env=self.environment))
        spec = importlib.util.spec_from_file_location('production_validator', self.checkout / 'scripts/verify-production-config.py')
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        if validator.validate(config, require_digests=True):
            raise OperationFailed('configuration_invariants_failed')
        expected_images = None
        if (workspace / 'runtime.json').exists():
            data = self._load(workspace)
            expected_images = data['prior']['images'] if rollback else data['candidate_images']
        for name in SERVICES:
            desired = config['services'][name]
            if expected_images is not None and desired['image'] != expected_images[name]:
                raise OperationFailed('image_override_changed')
            if compare_live:
                actual = self._environment('ignite-' + name)
                metadata = json.loads(self._docker(['inspect', '--format', FORMAT, 'ignite-' + name]))
                inherited = self._environment(metadata['image_id'], image=True)
                expected = desired.get('environment', {})
                if (any(actual.get(key) != str(value) for key, value in expected.items()) or
                        any(key not in expected and inherited.get(key) != value for key, value in actual.items())):
                    raise OperationFailed('runtime_environment_drift')
                network = desired.get('network_mode') or config['networks']['default']['name']
                ports = {str(p['target']) + '/' + p.get('protocol', 'tcp'): [{'HostIp': p.get('host_ip', ''), 'HostPort': str(p['published'])}] for p in desired.get('ports', [])}
                if (metadata['network'] != network or (metadata['dns'] or []) != desired.get('dns', []) or
                        metadata['restart'] != desired.get('restart') or (metadata['ports'] or {}) != ports or
                        metadata['logging'] != desired.get('labels', {}).get('logging')):
                    raise OperationFailed('runtime_settings_drift')
                actual_mounts = {(m['Name'], m['Destination'], m['RW']) for m in metadata['mounts'] if m['Type'] == 'volume'}
                expected_mounts = {(config['volumes'][m['source']]['name'], m['target'], not m.get('read_only', False)) for m in desired.get('volumes', [])}
                if actual_mounts != expected_mounts or len(metadata['mounts']) != len(expected_mounts):
                    raise OperationFailed('runtime_mount_drift')
            desired.pop('image')
        expected_binds = {'caddy': {'/etc/caddy/Caddyfile': str(self.anchor.parent / 'Caddyfile')},
                          'alloy': {'/etc/alloy/config.alloy': str(self.anchor / 'alloy/config.alloy'), '/var/run/docker.sock': '/var/run/docker.sock'},
                          'watchtower': {'/var/run/docker.sock': '/var/run/docker.sock', '/config.json': '/home/scowalt/.docker/config.json'}}
        for name, expected in expected_binds.items():
            binds = {m['target']: m['source'] for m in config['services'][name]['volumes'] if m['type'] == 'bind'}
            if binds != expected:
                raise OperationFailed('retained_bind_anchor_changed')
        key = self.environment.get('RESTIC_PASSWORD')
        if not key:
            raise OperationFailed('backup_configuration_missing')
        return hmac.new(key.encode(), b'ignite-deployer/config/v1\x00' + json.dumps(config, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()

    def _volumes(self):
        result = {}
        template = '{"name":{{json .Name}},"mountpoint":{{json .Mountpoint}},"driver":{{json .Driver}},"options":{{json .Options}}}'
        for name in ['ignite-data', 'backup-state', 'caddy-data', 'caddy-config']:
            physical = 'ignite-for-spotify_' + name
            value = json.loads(self._docker(['volume', 'inspect', '--format', template, physical]))
            if value['name'] != physical or value['driver'] != 'local' or value['options'] or not value['mountpoint']:
                raise OperationFailed('physical_volume_changed')
            result[physical] = value
        return result

    def _database(self, fallback_image=None):
        args = ['exec', 'ignite-backend', 'stat', '-c', '%u %g %a %i %s', '/app/data', '/app/data/ignite.db']
        if fallback_image:
            args = ['run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                    '--mount', 'type=volume,src=ignite-for-spotify_ignite-data,dst=/data,readonly',
                    '--entrypoint', 'stat', fallback_image, '-c', '%u %g %a %i %s', '/data', '/data/ignite.db']
        rows = self._docker(args).splitlines()
        if len(rows) != 2 or any(not re.fullmatch(r'\d+ \d+ \d+ \d+ \d+', row) for row in rows):
            raise OperationFailed('database_metadata_unavailable')
        values = {name: dict(zip(['uid', 'gid', 'mode', 'inode', 'bytes'], map(int, row.split()))) for name, row in zip(['directory', 'database'], rows)}
        if any(value['uid'] != 999 or value['gid'] != 999 for value in values.values()) or not 0 < values['database']['bytes'] <= INPUT_LIMIT:
            raise OperationFailed('database_identity_or_budget_changed')
        return values

    def _health(self, backend_only=False):
        urls = ['http://127.0.0.1:5050/health/ready'] + ([] if backend_only else ['http://127.0.0.1:3000/'])
        for url in urls:
            if run(['curl', '--silent', '--max-time', '10', '--output', '/dev/null', '--write-out', '%{http_code}', url], env=self.client_env) != b'200':
                raise OperationFailed('runtime_readiness_failed')

    def _backup_environment(self):
        env = {**self.environment, 'AWS_ACCESS_KEY_ID': self.environment['R2_ACCESS_KEY_ID'],
               'AWS_SECRET_ACCESS_KEY': self.environment['R2_SECRET_ACCESS_KEY'], 'AWS_DEFAULT_REGION': 'auto'}
        live = self._environment('ignite-backup')
        for key in ['RESTIC_REPOSITORY', 'RESTIC_PASSWORD', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION']:
            if not env.get(key) or env[key] != live.get(key):
                raise OperationFailed('backup_configuration_drift')
        if live.get('BACKUP_ON_START') != 'false' or live.get('BACKUP_HOST') != 'ignite-production' or live.get('BACKUP_TAG') != 'ignite-database':
            raise OperationFailed('backup_identity_drift')
        return env

    def _idle(self):
        script = 'for f in /proc/[0-9]*/comm; do IFS= read -r n < "$f" || continue; case "$n" in restic|sqlite3|backup|backup.sh|restore*) printf "%s\\n" "$n";; esac; done'
        if self._docker(['exec', 'ignite-backup', 'sh', '-c', script]).strip():
            raise OperationFailed('backup_or_restore_active')

    def _load(self, workspace):
        path = workspace / 'runtime.json'
        if path.is_symlink() or path.stat().st_size > 256 * 1024:
            raise OperationFailed('runtime_evidence_invalid')
        return json.loads(path.read_bytes())

    def _unchanged_auxiliary(self, current, baseline):
        if any(current[name] != baseline[name] for name in ['caddy', 'alloy', 'watchtower']) or current['watchtower']['running']:
            raise OperationFailed('unrelated_service_or_updater_changed')

    def _before_mutation(self, workspace, backup_stopped=False):
        data = self._load(workspace)
        current = self._snapshot()
        if self._volumes() != data['volumes']:
            raise OperationFailed('physical_volume_drift')
        self._unchanged_auxiliary(current, data['baseline'])
        for name in SERVICES:
            if current[name]['id'] != data['baseline'][name]['id'] or invariant(current[name]) != invariant(data['baseline'][name]):
                raise OperationFailed('pre_mutation_runtime_drift')
            if current[name]['running'] != (name != 'backup' or not backup_stopped):
                raise OperationFailed('pre_mutation_running_state_changed')
        if self._configuration(workspace) != data['configuration_digest']:
            raise OperationFailed('configuration_changed_after_preflight')
        self._same_database(data)
        return data

    def _same_database(self, data, fallback_image=None):
        current = self._database(fallback_image)
        for name in current:
            if any(current[name][key] != data['database'][name][key] for key in ['uid', 'gid', 'mode', 'inode']):
                raise OperationFailed('database_filesystem_identity_changed')

    def _account(self, reference, workspace):
        operation = workspace.name
        info = self._image(reference)
        if info['user'] != 'ignite':
            raise OperationFailed('backend_account_changed')
        identifier = self._docker(['create', '--pull', 'never', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                                   '--label', 'ignite.deployer-inspect=' + operation, '--entrypoint', '/not-executed', reference]).strip()
        if not re.fullmatch(r'[a-f0-9]{64}', identifier):
            raise OperationFailed('inspection_identity_invalid')
        try:
            raw = run([*self.docker, 'cp', identifier + ':/etc/passwd', '-'], env=self.client_env, limit=65536)
            with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
                members = archive.getmembers()
                if len(members) != 1 or not members[0].isfile() or members[0].size > 32768:
                    raise OperationFailed('account_archive_invalid')
                rows = archive.extractfile(members[0]).read().decode().splitlines()
            matches = [row.split(':') for row in rows if row.startswith('ignite:')]
            if len(matches) != 1 or matches[0][2:4] != ['999', '999']:
                raise OperationFailed('backend_account_incompatible')
        finally:
            self._cleanup_inspection(workspace)

    def _cleanup_inspection(self, workspace):
        operation = workspace.name
        ids = self._docker(['ps', '-a', '--no-trunc', '--filter', 'label=ignite.deployer-inspect=' + operation, '--format', '{{.ID}}']).splitlines()
        if len(ids) > 1:
            raise OperationFailed('inspection_ownership_ambiguous')
        for identifier in ids:
            value = json.loads(self._docker(['inspect', '--format', '{"owner":{{json (index .Config.Labels "ignite.deployer-inspect")}},"running":{{json .State.Running}},"mounts":{{json .Mounts}}}', identifier]))
            if value != {'owner': operation, 'running': False, 'mounts': []}:
                raise OperationFailed('inspection_ownership_changed')
            self._docker(['rm', identifier])

    def preflight(self, release, prior, workspace):
        baseline = self._snapshot()
        if baseline['watchtower']['running'] or any(not baseline[name]['running'] or baseline[name]['health'] not in [None, 'healthy'] for name in ALL if name != 'watchtower'):
            raise OperationFailed('baseline_not_healthy_or_updater_active')
        auxiliary_binds = {'caddy': {'/etc/caddy/Caddyfile': str(self.anchor.parent / 'Caddyfile')},
                           'alloy': {'/etc/alloy/config.alloy': str(self.anchor / 'alloy/config.alloy'), '/var/run/docker.sock': '/var/run/docker.sock'},
                           'watchtower': {'/var/run/docker.sock': '/var/run/docker.sock', '/config.json': '/home/scowalt/.docker/config.json'}}
        for name, expected in auxiliary_binds.items():
            actual = {mount['Destination']: mount['Source'] for mount in baseline[name]['mounts'] if mount['Type'] == 'bind'}
            if actual != expected:
                raise OperationFailed('live_retained_bind_anchor_changed')
        if deployment_contract(self.checkout) != self.contract or release.contract_sha256 != self.contract:
            raise OperationFailed('installed_contract_changed')
        if shutil.disk_usage(workspace).free < 5 * 1024**3:
            raise OperationFailed('pre_pull_storage_headroom_insufficient')
        for name, refs in [('candidate', dict(release.images)), ('prior', prior['images'])]:
            save_metadata(workspace / (name + '.compose.json'), {'services': {service: {'image': image} for service, image in refs.items()}})
        config = self._configuration(workspace)
        if config != self._configuration(workspace, rollback=True):
            raise OperationFailed('rollback_configuration_changed')
        for name in SERVICES:
            if baseline[name]['image'] != prior['images'][name] or baseline[name]['image_id'] != self._image(prior['images'][name], prior['source_sha'])['id']:
                raise OperationFailed('active_image_drift')
        volumes = self._volumes()
        for container in baseline.values():
            for mount in container['mounts']:
                if mount['Type'] == 'volume' and (mount['Name'] not in volumes or mount['Source'] != volumes[mount['Name']]['mountpoint']):
                    raise OperationFailed('physical_volume_mount_mismatch')
        data = {'baseline': baseline, 'database': self._database(), 'volumes': volumes, 'configuration_digest': config,
                'prior': prior, 'candidate_images': dict(release.images), 'candidate_source': release.source_sha}
        save_metadata(workspace / 'runtime.json', data)
        self._backup_environment()
        self._idle()
        self._health()
        wire_size = sum(self._wire_size(reference) for reference in dict(release.images).values())
        if wire_size > 1024**3 or shutil.disk_usage(workspace).free < 3 * 1024**3 + 4 * wire_size:
            raise OperationFailed('candidate_image_storage_budget_exceeded')
        for reference in dict(release.images).values():
            self._docker(['pull', reference], timeout=600)
            self._image(reference, release.source_sha)
            if shutil.disk_usage(workspace).free < 3 * 1024**3:
                raise OperationFailed('post_pull_storage_headroom_insufficient')
        self._account(dict(release.images)['backend'], workspace)
        self._before_mutation(workspace)

    def _tool(self, workspace):
        data = self._load(workspace)
        env = {**self.environment, 'AWS_ACCESS_KEY_ID': self.environment.get('R2_ACCESS_KEY_ID', ''),
               'AWS_SECRET_ACCESS_KEY': self.environment.get('R2_SECRET_ACCESS_KEY', ''), 'AWS_DEFAULT_REGION': 'auto'}
        return BackupTool(self.docker, data['prior']['images']['backup'], workspace / 'scratch',
                          env, 'deploy-' + workspace.name,
                          'type=volume,src=ignite-for-spotify_ignite-data,dst=/data,readonly',
                          'type=volume,src=ignite-for-spotify_backup-state,dst=/state')

    def backup(self, workspace):
        self._before_mutation(workspace)
        env = self._backup_environment()
        before = bucket_inventory(env)
        if not before['objects'] or not before['bytes']:
            raise OperationFailed('existing_backup_inventory_empty')
        self._idle()
        self._docker(['stop', '--time', '60', 'ignite-backup'])
        (workspace / 'scratch').mkdir(mode=0o700)
        tool = self._tool(workspace)
        try:
            tool.start()
            if json.loads(tool.restic(['--no-lock', 'cat', 'config']))['id'] != self.repository_id:
                raise OperationFailed('backup_repository_identity_changed')
            result = tool.snapshot_restore()
            after = bucket_inventory(env)
            additional = after['bytes'] - before['bytes']
            if not 0 <= additional <= REMOTE_LIMIT or shutil.disk_usage(workspace).free < 3 * 1024**3:
                raise OperationFailed('recovery_storage_budget_exceeded')
            tool.marker()
            return {key: result[key] for key in ['snapshot_id', 'repository_id', 'snapshot_time', 'snapshot_bytes', 'scratch_bytes', 'restore_verified']} | {'additional_remote_bytes': additional}
        finally:
            tool.close()

    def cleanup(self, workspace):
        self._cleanup_inspection(workspace)
        if (workspace / 'runtime.json').exists():
            self._tool(workspace).close()

    def _up(self, names, workspace, rollback=False):
        wait = 120 if names == ['backend'] else 180
        run([*self._compose(workspace, rollback), 'up', '-d', '--no-build', '--pull', 'never', '--no-deps',
             '--timeout', '60', '--wait', '--wait-timeout', str(wait), *names], env=self.environment, timeout=wait + 180)

    def _verify_app(self, name, reference, data):
        current = json.loads(self._docker(['inspect', '--format', FORMAT, 'ignite-' + name]))
        if (current['image'] != reference or current['image_id'] != self._image(reference)['id'] or
                not current['running'] or current['health'] != 'healthy' or invariant(current) != invariant(data['baseline'][name])):
            raise OperationFailed('application_identity_or_health_changed')

    def switch_backend(self, release, workspace):
        data = self._before_mutation(workspace, backup_stopped=True)
        self._up(['backend'], workspace)
        self._verify_app('backend', dict(release.images)['backend'], data)
        self._same_database(data)
        self._health(backend_only=True)

    def switch_dependents(self, release, workspace):
        self._up(['backup', 'frontend'], workspace)

    def verify(self, images, workspace):
        data = self._load(workspace)
        self._unchanged_auxiliary(self._snapshot(), data['baseline'])
        for name in SERVICES:
            self._verify_app(name, images[name], data)
        if self._configuration(workspace, rollback=images == data['prior']['images']) != data['configuration_digest']:
            raise OperationFailed('post_update_configuration_changed')
        self._same_database(data)
        self._health()
        self._backup_environment()
        configuration = json.loads(self._docker(['exec', 'ignite-backup', 'timeout', '60', 'restic', '--no-cache', '--no-lock', 'cat', 'config'], timeout=75))
        if configuration.get('id') != self.repository_id:
            raise OperationFailed('running_backup_repository_unavailable')

    def rollback(self, prior, workspace):
        data = self._load(workspace)
        if prior != data['prior'] or self._configuration(workspace, rollback=True, compare_live=False) != data['configuration_digest']:
            raise OperationFailed('rollback_configuration_changed')
        self._unchanged_auxiliary(self._snapshot(('caddy', 'alloy', 'watchtower')), data['baseline'])
        if self._volumes() != data['volumes']:
            raise OperationFailed('rollback_volume_drift')
        self._same_database(data, prior['images']['backup'])
        observed = {}
        for name in SERVICES:
            identifiers = self._docker(['ps', '-a', '--no-trunc', '--filter', 'name=^/ignite-' + name + '$', '--format', '{{.ID}}']).splitlines()
            if not identifiers:
                observed[name] = None
                continue
            if len(identifiers) != 1:
                raise OperationFailed('rollback_container_identity_ambiguous')
            current = json.loads(self._docker(['inspect', '--format', FORMAT, 'ignite-' + name]))
            if (invariant(current) != invariant(data['baseline'][name]) or
                    current['image'] not in [prior['images'][name], data['candidate_images'][name]] or
                    current['image_id'] != self._image(current['image'])['id']):
                raise OperationFailed('unrecognized_runtime_during_rollback')
            observed[name] = current
        for name, current in observed.items():
            if current is not None and current['id'] == data['baseline'][name]['id']:
                if not current['running']:
                    self._docker(['start', 'ignite-' + name])
            else:
                self._up([name], workspace, rollback=True)
            deadline = time.monotonic() + 180
            while True:
                try:
                    self._verify_app(name, prior['images'][name], data)
                    break
                except OperationFailed:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(3)
