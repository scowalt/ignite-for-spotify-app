import io
import json
import re
import tarfile

from deployment_process import OperationFailed, run


def read_image_metadata(reference, revision, operation, *, docker, env, legacy=False):
    if (not isinstance(reference, str) or not re.fullmatch(r'(?:ghcr\.io/scowalt/ignite-for-spotify-app/backend@)?sha256:[a-f0-9]{64}', reference) or
            not re.fullmatch(r'[a-f0-9]{40}', revision) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}', operation)):
        raise OperationFailed('migration_image_identity_invalid')
    image_format = '{"id":{{json .Id}},"digests":{{json .RepoDigests}},"user":{{json (index .Config "User")}},"os":{{json .Os}},"arch":{{json .Architecture}},"volumes":{{json (index .Config "Volumes")}},"revision":{{with index .Config "Labels"}}{{json (index . "org.opencontainers.image.revision")}}{{else}}null{{end}},"source":{{with index .Config "Labels"}}{{json (index . "org.opencontainers.image.source")}}{{else}}null{{end}}}'
    label = 'ignite.deployer-inspect=' + operation

    def execute(args, maximum=65536):
        return run([*docker, *args], env=env, timeout=90, limit=maximum)

    def owned():
        values = execute(['ps', '-a', '--no-trunc', '--filter', 'label=' + label, '--format', '{{.ID}}']).decode().splitlines()
        if len(values) > 1 or any(not re.fullmatch(r'[a-f0-9]{64}', value) for value in values):
            raise OperationFailed('inspection_ownership_ambiguous')
        return values

    image = json.loads(execute(['image', 'inspect', reference, '--format', image_format]))
    if (not re.fullmatch(r'sha256:[a-f0-9]{64}', image.get('id', '')) or
            (reference.startswith('sha256:') and image['id'] != reference) or
            (not reference.startswith('sha256:') and reference not in (image.get('digests') or [])) or
            image.get('user') != 'ignite' or image.get('os') != 'linux' or image.get('arch') != 'amd64' or
            image.get('volumes') or image.get('revision') != revision or
            image.get('source') != 'https://github.com/scowalt/ignite-for-spotify-app'):
        raise OperationFailed('migration_image_identity_invalid')
    if owned():
        raise OperationFailed('inspection_already_exists')
    identifier = None
    try:
        identifier = execute(['create', '--pull', 'never', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                              '--label', label, '--entrypoint', '/not-executed', image['id']]).decode().strip()
        if not re.fullmatch(r'[a-f0-9]{64}', identifier):
            raise OperationFailed('inspection_identity_invalid')
        values = []
        for name, directory, maximum in [('migration-catalogue.json', '/app/', 1024**2),
                                          ('Ignite.Api.deps.json', '/app/', 2 * 1024**2),
                                          ('Ignite.Migrations.deps.json', '/app/migrations/', 2 * 1024**2)]:
            if legacy and name != 'Ignite.Api.deps.json':
                values.append(None)
                continue
            payload = execute(['cp', identifier + ':' + directory + name, '-'], maximum + 65536)
            values.append(metadata_file(payload, name, maximum))
        return tuple(values)
    finally:
        for found in owned():
            if identifier is not None and found != identifier:
                raise OperationFailed('inspection_ownership_changed')
            template = '{"owner":{{json (index .Config.Labels "ignite.deployer-inspect")}},"running":{{json .State.Running}},"mounts":{{json .Mounts}},"image_id":{{json .Image}}}'
            observed = json.loads(execute(['inspect', '--format', template, found]))
            if observed != {'owner': operation, 'running': False, 'mounts': [], 'image_id': image['id']}:
                raise OperationFailed('inspection_ownership_changed')
            execute(['rm', found])


def metadata_file(payload, name, maximum):
    if name not in ['migration-catalogue.json', 'Ignite.Api.deps.json', 'Ignite.Migrations.deps.json'] or len(payload) > maximum + 65536:
        raise OperationFailed('migration_image_metadata_invalid')
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
            entries = iter(archive)
            entry = next(entries, None)
            if (entry is None or not entry.isfile() or entry.name.removeprefix('./') != name or
                    entry.size < 0 or entry.size > maximum or next(entries, None) is not None):
                raise ValueError()
            content = archive.extractfile(entry).read(maximum + 1)
            if len(content) != entry.size:
                raise ValueError()
            return content
    except (OSError, ValueError, tarfile.TarError):
        raise OperationFailed('migration_image_metadata_invalid') from None
