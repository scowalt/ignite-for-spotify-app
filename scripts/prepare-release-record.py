import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from deployment_process import OperationFailed, run
from migration_image import read_image_metadata
from release_record import REPOSITORY, ReleaseRejected, create_release_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--migration-protocol', action='store_true')
    args = parser.parse_args()
    try:
        revision = os.environ.get('GITHUB_SHA', '')
        if (not re.fullmatch(r'[a-f0-9]{40}', revision) or os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or
                os.environ.get('GITHUB_REF') != 'refs/heads/main' or
                os.environ.get('GITHUB_EVENT_NAME') not in ['push', 'workflow_dispatch']):
            raise ReleaseRejected('Trusted publisher identity required.')
        images = {}
        for name in ['backend', 'backup', 'frontend']:
            image = 'ghcr.io/' + REPOSITORY + '/' + name
            result = subprocess.run(['docker', 'buildx', 'imagetools', 'inspect', image + ':' + revision[:7],
                                     '--format', '{{json .Manifest}}'], capture_output=True, text=True,
                                    check=False, timeout=60)
            if result.returncode or len(result.stdout) > 32768:
                raise ReleaseRejected('Published image receipt unavailable.')
            digest = json.loads(result.stdout).get('digest')
            if not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                raise ReleaseRejected('Published image receipt malformed.')
            images[name] = image + '@' + digest
        metadata = {}
        if args.migration_protocol:
            client_env = {key: os.environ[key] for key in ['PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONFIG', 'XDG_RUNTIME_DIR'] if key in os.environ}
            run(['docker', 'pull', '--platform', 'linux/amd64', images['backend']], env=client_env, timeout=180)
            operation = 'publisher-' + os.environ.get('GITHUB_RUN_ID', '') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '')
            descriptor, dependencies = read_image_metadata(images['backend'], revision, operation, docker=['docker'], env=client_env)
            metadata = {'migration_descriptor': descriptor, 'backend_deps': dependencies}
        payload = create_release_record(args.root, dict(os.environ), images, **metadata)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as target:
            target.write(payload + b'\n')
        print('Coherent release record created from the three published immutable receipts.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError, OperationFailed):
        print('Release record creation failed; no untrusted values printed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
