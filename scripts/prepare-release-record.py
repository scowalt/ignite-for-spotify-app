import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from release_record import REPOSITORY, ReleaseRejected, create_release_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
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
        payload = create_release_record(args.root, dict(os.environ), images)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as target:
            target.write(payload + b'\n')
        print('Coherent release record created from the three published immutable receipts.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        print('Release record creation failed; no untrusted values printed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
