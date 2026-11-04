import json
from pathlib import Path
import re

from deployment_process import OperationFailed, run
from migration_record import HISTORY_LIMIT, decode, parse_inspection


class MigrationTool:
    def __init__(self, docker, image_id, operation, source, *, environment, timeout=90):
        if (not isinstance(image_id, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id) or
                not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}', operation) or not Path(source).is_absolute() or
                any(character in source for character in ',\x00\n\r') or not 0 < timeout <= 120):
            raise OperationFailed('migration_tool_identity_invalid')
        self.docker, self.image_id, self.operation, self.source = docker, image_id, operation, source
        self.environment = {key: environment[key] for key in ['PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONFIG', 'XDG_RUNTIME_DIR'] if key in environment}
        self.timeout, self.identifier = timeout, None

    def _docker(self, args, *, input=None, timeout=45, limit=65536):
        return run([*self.docker, *args], env=self.environment, input=input, timeout=timeout, limit=limit)

    def _owned(self):
        identifiers = self._docker(['ps', '-a', '--no-trunc', '--filter', 'label=ignite.deployer-migration=' + self.operation,
                                   '--format', '{{.ID}}']).decode().splitlines()
        if len(identifiers) > 1 or any(not re.fullmatch(r'[a-f0-9]{64}', identifier) for identifier in identifiers):
            raise OperationFailed('migration_tool_ownership_ambiguous')
        return identifiers

    def _inspect(self, identifier):
        template = '{"owner":{{json (index .Config.Labels "ignite.deployer-migration")}},"action":{{json (index .Config.Labels "ignite.migration-action")}},"image_id":{{json .Image}},"running":{{json .State.Running}},"exit_code":{{json .State.ExitCode}},"mounts":{{json .Mounts}},"entrypoint":{{json .Config.Entrypoint}},"command":{{json .Config.Cmd}},"user":{{json .Config.User}},"network":{{json .HostConfig.NetworkMode}},"root_readonly":{{json .HostConfig.ReadonlyRootfs}},"privileged":{{json .HostConfig.Privileged}}}'
        value = json.loads(self._docker(['inspect', '--format', template, identifier]))
        action = value.get('action')
        if action not in ['inspect', 'apply', 'adopt', 'settle']:
            raise OperationFailed('migration_tool_ownership_changed')
        expected_command = ['/app/migrations/Ignite.Migrations.dll', action]
        if action in ['apply', 'adopt']:
            expected_command.append('/app/migration-catalogue.json')
        if (value.get('owner') != self.operation or value.get('image_id') != self.image_id or
                value.get('entrypoint') != ['/usr/share/dotnet/dotnet'] or value.get('command') != expected_command or
                value.get('user') != '999:999' or value.get('network') != 'none' or
                value.get('root_readonly') is not True or value.get('privileged') is not False or
                type(value.get('running')) is not bool or type(value.get('exit_code')) is not int):
            raise OperationFailed('migration_tool_ownership_changed')
        mounts = value.get('mounts')
        if not isinstance(mounts, list):
            raise OperationFailed('migration_tool_ownership_changed')
        data = [mount for mount in mounts if mount.get('Destination') == '/data']
        other = [mount for mount in mounts if mount.get('Destination') != '/data']
        if (len(data) != 1 or data[0].get('Type') != 'bind' or data[0].get('Source') != self.source or
                data[0].get('RW') is not (action != 'inspect') or
                any(mount.get('Type') != 'tmpfs' or mount.get('Destination') != '/tmp' for mount in other) or len(other) > 1):
            raise OperationFailed('migration_tool_ownership_changed')
        if self.identifier is not None and identifier != self.identifier:
            raise OperationFailed('migration_tool_ownership_changed')
        return value

    def close(self):
        for identifier in self._owned():
            observed = self._inspect(identifier)
            if observed['running']:
                self._docker(['stop', '--time', '0', identifier])
            if self._inspect(identifier)['running']:
                raise OperationFailed('migration_writer_not_stopped')
            self._docker(['rm', identifier])
        if self._owned():
            raise OperationFailed('migration_tool_cleanup_incomplete')
        self.identifier = None

    def invoke(self, action, request):
        if action not in ['inspect', 'apply', 'adopt', 'settle'] or not isinstance(request, dict) or request.get('database_path') != '/data/ignite.db':
            raise OperationFailed('migration_request_invalid')
        payload = json.dumps(request, sort_keys=True, separators=(',', ':')).encode()
        if len(payload) > HISTORY_LIMIT:
            raise OperationFailed('migration_request_too_large')
        if self._owned():
            raise OperationFailed('migration_tool_already_exists')
        if json.loads(self._docker(['image', 'inspect', self.image_id, '--format', '{{json .Config.Volumes}}'])):
            raise OperationFailed('migration_image_declares_volumes')
        mount = 'type=bind,src=' + self.source + ',dst=/data' + (',readonly' if action == 'inspect' else '')
        args = ['create', '--pull', 'never', '--interactive', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', '999:999', '--memory', '512m', '--memory-swap', '512m',
                '--cpus', '1', '--pids-limit', '64', '--ulimit', 'fsize=268435456:268435456',
                '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777', '--mount', mount,
                '--env', 'DOTNET_EnableDiagnostics=0', '--env', 'DOTNET_CLI_TELEMETRY_OPTOUT=1', '--env', 'TMPDIR=/tmp',
                '--label', 'ignite.deployer-migration=' + self.operation, '--label', 'ignite.migration-action=' + action,
                '--entrypoint', '/usr/share/dotnet/dotnet', self.image_id, '/app/migrations/Ignite.Migrations.dll', action]
        if action in ['apply', 'adopt']:
            args.append('/app/migration-catalogue.json')
        try:
            self.identifier = self._docker(args).decode().strip()
            if not re.fullmatch(r'[a-f0-9]{64}', self.identifier):
                raise OperationFailed('migration_tool_identity_invalid')
            self._inspect(self.identifier)
            output = self._docker(['start', '--attach', '--interactive', self.identifier], input=payload, timeout=self.timeout, limit=HISTORY_LIMIT)
            completed = self._inspect(self.identifier)
            if completed['running'] or completed['exit_code'] != 0:
                raise OperationFailed('migration_command_not_finished')
            if action == 'inspect':
                return parse_inspection(output)
            value = decode(output, HISTORY_LIMIT)
            outcomes = {'apply': ['migrated', 'unchanged'], 'adopt': ['adopted'], 'settle': ['settled']}
            if (not isinstance(value, dict) or set(value) != {'schema', 'outcome', 'inspection'} or
                    type(value['schema']) is not int or value['schema'] != 1 or value['outcome'] not in outcomes[action]):
                raise OperationFailed('migration_receipt_invalid')
            value['inspection'] = parse_inspection(json.dumps(value['inspection']).encode())
            return value
        finally:
            self.close()
