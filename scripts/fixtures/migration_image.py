import io
import json
import os
from pathlib import Path
import sys
import tarfile

root = Path(os.environ['FIXTURE_ROOT'])
args = sys.argv[1:]
with (root / 'commands.jsonl').open('a') as stream:
    stream.write(json.dumps(args) + '\n')
container = 'c' * 64
image_id = 'sha256:' + 'd' * 64
reference = 'ghcr.io/scowalt/ignite-for-spotify-app/backend@sha256:' + 'e' * 64
if args[:3] == ['buildx', 'imagetools', 'inspect']:
    name = args[3].split('/')[-1].split(':')[0]
    print(json.dumps({'digest': 'sha256:' + {'backend': 'e', 'backup': 'f', 'frontend': '1'}[name] * 64}))
elif args[0] == 'pull':
    assert args[-1] == reference
elif args[:2] == ['image', 'inspect']:
    print(json.dumps({'id': image_id, 'digests': [reference], 'user': 'ignite', 'os': 'linux', 'arch': 'amd64',
                      'volumes': None, 'revision': 'a' * 40, 'source': 'https://github.com/scowalt/ignite-for-spotify-app'}))
elif args[0] == 'create':
    assert args[args.index('--entrypoint') + 1] == '/not-executed'
    assert '--mount' not in args and '--env' not in args
    assert args[-1] == image_id
    (root / 'container').write_text(args[args.index('--label') + 1].split('=', 1)[1])
    print(container)
elif args[0] == 'cp':
    if os.environ.get('FIXTURE_MODE') == 'bad-copy':
        sys.stdout.buffer.write(b'fixture-private-invalid-archive')
        raise SystemExit(0)
    name = args[1].split('/')[-1]
    content = (root / name).read_bytes() if (root / name).exists() else b'{}'
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        entry = tarfile.TarInfo(name)
        entry.size = len(content)
        archive.addfile(entry, io.BytesIO(content))
    sys.stdout.buffer.write(output.getvalue())
elif args[0] == 'ps':
    if (root / 'container').exists():
        print(container)
elif args[0] == 'inspect':
    print(json.dumps({'owner': (root / 'container').read_text(), 'running': os.environ.get('FIXTURE_MODE') == 'ownership-drift', 'mounts': [], 'image_id': image_id}))
elif args[0] == 'rm':
    assert args == ['rm', container]
    (root / 'container').unlink()
else:
    raise SystemExit('Unexpected operation')
