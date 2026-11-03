import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest
import uuid

from deployment_process import run

from release_transport import load_release, record_from_image_archive
from release_signature import SignatureVerifier
from release_record import ReleaseRejected


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as output:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            output.addfile(member, io.BytesIO(content))
    return stream.getvalue()


class ReleaseTransportTests(unittest.TestCase):
    def test_record_is_read_without_extracting_or_executing_image_files(self):
        image = archive({'manifest.json': json.dumps([{'Layers': ['layer.tar']}]).encode(),
                         'layer.tar': archive({'release.json': b'{"schema":1}'})})
        self.assertEqual(record_from_image_archive(image), b'{"schema":1}')

    def test_unsafe_ambiguous_and_oversized_records_are_rejected(self):
        good = archive({'release.json': b'{}'})
        bad_layers = [archive({'../release.json': b'{}'}), archive({'release.json': b'x' * 32769})]
        bad_images = [b'not a tar', b'x' * (8 * 1024**2 + 1),
                      archive({'manifest.json': json.dumps([{'Layers': ['a.tar', 'b.tar']}]).encode(), 'a.tar': good, 'b.tar': good})]
        bad_images += [archive({'manifest.json': json.dumps([{'Layers': ['layer.tar']}]).encode(), 'layer.tar': layer}) for layer in bad_layers]
        link_stream = io.BytesIO()
        with tarfile.open(fileobj=link_stream, mode='w') as output:
            member = tarfile.TarInfo('release.json')
            member.type = tarfile.SYMTYPE
            member.linkname = '/etc/passwd'
            output.addfile(member)
        bad_images.append(archive({'manifest.json': json.dumps([{'Layers': ['layer.tar']}]).encode(), 'layer.tar': link_stream.getvalue()}))
        for image in bad_images:
            with self.subTest(size=len(image)), self.assertRaises(ReleaseRejected):
                record_from_image_archive(image)

    def test_loader_uses_one_verified_digest_and_never_starts_artifact_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = {name: 'ghcr.io/scowalt/ignite-for-spotify-app/' + name + '@sha256:' + 'c' * 64 for name in ['backend', 'backup', 'frontend']}
            record = {'schema': 1, 'repository': 'scowalt/ignite-for-spotify-app', 'source_sha': 'b' * 40,
                      'run_id': 123, 'run_attempt': 1, 'run_number': 42, 'contract_sha256': 'd' * 64, 'images': images}
            (root / 'image.tar').write_bytes(archive({'manifest.json': json.dumps([{'Layers': ['layer.tar']}]).encode(),
                                                     'layer.tar': archive({'release.json': json.dumps(record).encode()})}))
            reference = 'ghcr.io/scowalt/ignite-for-spotify-app/release@sha256:' + 'a' * 64
            docker = root / 'docker.py'
            docker.write_text('import json,sys\nfrom pathlib import Path\na=sys.argv[1:]\nref=' + repr(reference) + '\nroot=Path(__file__).parent\n'
                              'if a[:3]==["buildx","imagetools","inspect"]:\n'
                              ' print(json.dumps({"schemaVersion":2,"config":{"size":100},"layers":[{"size":100}]} if "--raw" in a else {"digest":"sha256:"+"a"*64}))\n'
                              'elif a[:2]==["image","pull"]:\n assert a[2]==ref and (root/"authorized").exists()\n'
                              'elif a[:2]==["image","inspect"]:\n assert a[2]==ref\n print(json.dumps([ref]))\n'
                              'elif a[:2]==["image","save"]:\n assert a[2]==ref\n sys.stdout.buffer.write((root/"image.tar").read_bytes())\n'
                              'else:\n raise SystemExit(9)\n')
            signer = root / 'cosign'
            content = '#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nassert sys.argv[2]==' + repr(reference) + '\n'
            content += 'if "--certificate-github-workflow-sha" not in sys.argv:\n Path(__file__).with_name("authorized").touch()\nelse:\n assert sys.argv[-1]=="b"*40\n'
            signer.write_text(content)
            signer.chmod(0o700)
            run = {'id': 123, 'run_attempt': 1, 'run_number': 42, 'head_sha': 'b' * 40, 'head_branch': 'main',
                   'status': 'completed', 'conclusion': 'success', 'workflow_id': 403197563, 'path': '.github/workflows/ci.yml',
                   'event': 'push', 'repository': {'id': 1441388195}, 'head_repository': {'id': 1441388195}}
            loaded = load_release('d' * 64, docker=[sys.executable, str(docker)],
                                  verifier=SignatureVerifier(signer, hashlib.sha256(content.encode()).hexdigest()),
                                  workflow_reader=lambda identifier: run if identifier == 123 else None)
            self.assertEqual(dict(loaded.images), images)
            self.assertEqual(loaded.artifact_digest, 'sha256:' + 'a' * 64)

    @unittest.skipUnless(os.environ.get('IGNITE_BACKUP_FIXTURE_IMAGE'), 'Requires the isolated Docker fixture environment.')
    def test_actual_docker_export_is_read_without_creating_a_container(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'release.json').write_bytes(b'{"fixture":"export"}')
            (root / 'LICENSE').write_text('fixture')
            image = 'ignite-release-fixture:' + uuid.uuid4().hex
            dockerfile = Path(__file__).resolve().parents[1] / 'ops/deployer/Dockerfile.release'
            try:
                run(['docker', 'buildx', 'build', '--load', '--platform', 'linux/amd64', '--provenance=false', '--sbom=false',
                     '-f', str(dockerfile), '-t', image, str(root)], timeout=90)
                raw = run(['docker', 'image', 'save', image], limit=8 * 1024**2)
                self.assertEqual(record_from_image_archive(raw), b'{"fixture":"export"}')
            finally:
                run(['docker', 'image', 'rm', image])


if __name__ == '__main__':
    unittest.main()
