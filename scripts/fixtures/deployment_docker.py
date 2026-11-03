import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

root = Path(sys.argv[1])
state_path = root / 'docker-state.json'
state = json.loads(state_path.read_text())
args = sys.argv[2:]


def output(value):
    print(json.dumps(value))


def image(reference):
    revision = state['candidate_source'] if reference in state['candidate'].values() else state['prior_source']
    return {'id': 'sha256:' + hashlib.sha256(reference.encode()).hexdigest(), 'digests': [reference],
            'user': 'ignite' if '/backend@' in reference else '', 'os': 'linux', 'arch': 'amd64',
            'volumes': None, 'revision': revision, 'source': 'https://github.com/scowalt/ignite-for-spotify-app'}


if args[0] == 'inspect':
    name = args[-1]
    template = args[args.index('--format') + 1]
    if name == (state.get('inspector') or {}).get('id'):
        output({'owner': state['inspector']['owner'], 'running': False, 'mounts': []})
    elif 'Config.Env' in template:
        output([key + '=' + str(value) for key, value in state['environments'][name.removeprefix('ignite-')].items()])
    else:
        output(state['containers'][name.removeprefix('ignite-')])
elif args[:2] == ['image', 'inspect']:
    if 'Config.Env' in args[args.index('--format') + 1]:
        output([])
    else:
        output(image(args[-1]))
elif args[:2] == ['volume', 'inspect']:
    name = args[-1]
    output({'name': name, 'mountpoint': '/volumes/' + name, 'driver': 'local', 'options': None})
elif args[0] == 'run':
    assert '--read-only' in args and 'none' in args and '--entrypoint' in args
    print('999 999 770 100 4096\n999 999 600 101 8192')
elif args[:3] == ['buildx', 'imagetools', 'inspect']:
    output({'layers': [{'size': 100}]})
elif args[0] == 'pull':
    state['pulled'].append(args[1])
elif args[0] == 'exec':
    if args[2] == 'stat':
        print('999 999 770 100 4096\n999 999 600 101 8192')
    elif args[2] == 'timeout':
        output({'id': 'f' * 64})
    else:
        assert args[1] == 'ignite-backup' and args[2] == 'sh'
elif args[0] == 'create':
    assert '--network' in args and args[args.index('--network') + 1] == 'none'
    assert '--read-only' in args and '--entrypoint' in args
    state['inspector'] = {'id': 'f' * 64, 'owner': args[args.index('--label') + 1].split('=', 1)[1]}
    print(state['inspector']['id'])
elif args[0] == 'cp':
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        data = b'ignite:x:999:999::/nonexistent:/bin/false\n'
        member = tarfile.TarInfo('passwd')
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    sys.stdout.buffer.write(stream.getvalue())
elif args[0] == 'ps':
    if state.get('inspector') and 'ignite.deployer-inspect=' in ' '.join(args):
        print(state['inspector']['id'])
    elif 'name=^/ignite-' in ' '.join(args):
        name = args[args.index('--filter') + 1].removeprefix('name=^/ignite-').removesuffix('$')
        if name in state['containers']:
            print(state['containers'][name]['id'])
elif args[0] == 'rm':
    assert args[1] == state['inspector']['id']
    state['inspector'] = None
elif args[0] in ['start', 'stop']:
    name = args[-1].removeprefix('ignite-')
    assert name == 'backup'
    state['containers'][name]['running'] = args[0] == 'start'
elif args[0] == 'compose':
    config = json.loads((root / 'compose.json').read_text())
    overrides = json.loads(Path(args[max(index for index, value in enumerate(args) if value == '-f') + 1]).read_text())
    for name, value in overrides['services'].items():
        config['services'][name]['image'] = value['image']
    if 'config' in args:
        output(config)
    elif 'up' in args:
        assert all(flag in args for flag in ['--no-build', '--no-deps', '--wait'])
        assert args[args.index('--pull') + 1] == 'never'
        names = args[args.index('--wait-timeout') + 2:]
        assert set(names) <= {'backend', 'backup', 'frontend'}
        for name in names:
            if name not in state['containers']:
                state['containers'][name] = dict(state['templates'][name])
            reference = config['services'][name]['image']
            state['containers'][name].update({'image': reference, 'image_id': image(reference)['id'],
                                             'id': image(reference)['id'], 'running': True, 'health': 'healthy'})
        state['updated'].extend(names)
    else:
        raise SystemExit(8)
else:
    raise SystemExit(9)
state_path.write_text(json.dumps(state))
