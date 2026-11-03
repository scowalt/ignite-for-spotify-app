import io
import json
import os
from pathlib import PurePosixPath
import re
import tarfile
import zlib
import urllib.request

from deployment_process import run
from release_record import REPOSITORY, ReleaseRejected, validate_release
from release_signature import RELEASE_IMAGE


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def public_workflow(identifier):
    request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + '/actions/runs/' + str(identifier),
                                     headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'ignite-release-reader'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=30) as response:
        raw = response.read(2 * 1024**2 + 1)
    if len(raw) > 2 * 1024**2:
        raise ReleaseRejected('Workflow response exceeds its bound.')
    return json.loads(raw)


def _bounded_manifest(docker, reference, env, depth=0):
    manifest = json.loads(run([*docker, 'buildx', 'imagetools', 'inspect', reference, '--raw'], env=env, limit=32768))
    if 'manifests' in manifest:
        choices = manifest['manifests']
        if depth or not isinstance(choices, list) or len(choices) != 1:
            raise ReleaseRejected('Unexpected artifact platform set.')
        choice = choices[0]
        digest = choice.get('digest', '')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest) or choice.get('platform') != {'os': 'linux', 'architecture': 'amd64'}:
            raise ReleaseRejected('Unexpected artifact platform identity.')
        return _bounded_manifest(docker, RELEASE_IMAGE + '@' + digest, env, depth + 1)
    layers = manifest.get('layers')
    size = manifest.get('config', {}).get('size')
    if (type(size) is not int or not 0 < size <= 65536 or not isinstance(layers, list) or not 1 <= len(layers) <= 4 or
            any(type(layer.get('size')) is not int or layer['size'] < 0 for layer in layers) or
            sum(layer['size'] for layer in layers) > 256 * 1024):
        raise ReleaseRejected('Artifact download exceeds its bound.')


def load_release(expected_contract, *, docker, verifier, workflow_reader=public_workflow):
    env = {key: os.environ[key] for key in ['PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONFIG', 'XDG_RUNTIME_DIR'] if key in os.environ}
    descriptor = json.loads(run([*docker, 'buildx', 'imagetools', 'inspect', RELEASE_IMAGE + ':latest',
                                 '--format', '{{json .Manifest}}'], env=env, limit=32768))
    digest = descriptor.get('digest', '')
    if not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ReleaseRejected('Artifact digest unavailable.')
    reference = RELEASE_IMAGE + '@' + digest
    verifier.authorize(digest)
    _bounded_manifest(docker, reference, env)
    run([*docker, 'image', 'pull', reference], env=env, timeout=180)
    receipts = json.loads(run([*docker, 'image', 'inspect', reference, '--format', '{{json .RepoDigests}}'], env=env))
    if not isinstance(receipts, list) or reference not in receipts:
        raise ReleaseRejected('Local artifact receipt does not match verification.')
    payload = record_from_image_archive(run([*docker, 'image', 'save', reference], env=env, timeout=90, limit=8 * 1024**2))
    identity = json.loads(payload)
    source = identity.get('source_sha')
    identifier = identity.get('run_id')
    if type(identifier) is not int or not 0 < identifier < 2**63:
        raise ReleaseRejected('Invalid workflow identity.')
    proof = verifier.verify(digest, source)
    return validate_release(payload, proof, workflow_reader(identifier), expected_contract)


def _tar_members(raw, bound):
    if len(raw) > bound:
        raise ReleaseRejected('Artifact archive exceeds its bound.')
    if raw.startswith(b'\x1f\x8b'):
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(raw, bound + 1)
        if len(raw) > bound or not decoder.eof or decoder.unused_data:
            raise ReleaseRejected('Compressed artifact layer exceeds its bound.')
    result = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as source:
        for member in source:
            name = member.name.removeprefix('./')
            path = PurePosixPath(name)
            if (len(result) >= 128 or path.is_absolute() or '..' in path.parts or name in result or
                    not (member.isfile() or member.isdir()) or member.size > bound):
                raise ReleaseRejected('Unsafe or ambiguous artifact member.')
            if member.isfile():
                result[name] = source.extractfile(member).read(bound + 1)
    return result


def record_from_image_archive(raw: bytes) -> bytes:
    try:
        image = _tar_members(raw, 8 * 1024**2)
        manifest = json.loads(image['manifest.json'])
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise ReleaseRejected('Artifact archive is not one image.')
        layers = manifest[0]['Layers']
        if not isinstance(layers, list) or not 1 <= len(layers) <= 4 or len(set(layers)) != len(layers):
            raise ReleaseRejected('Unexpected artifact layer set.')
        records = []
        for name in layers:
            members = _tar_members(image[name], 1024**2)
            if any(PurePosixPath(path).name.startswith('.wh.') for path in members):
                raise ReleaseRejected('Artifact contains filesystem replacement entries.')
            if 'release.json' in members:
                records.append(members['release.json'])
        if len(records) != 1 or len(records[0]) > 32768:
            raise ReleaseRejected('Artifact must contain one bounded release record.')
        return records[0]
    except (KeyError, ValueError, TypeError, tarfile.TarError, zlib.error, RecursionError):
        raise ReleaseRejected('Artifact archive is unavailable or invalid.') from None
