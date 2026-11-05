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
state.setdefault('commands', []).append(args)


def output(value):
    print(json.dumps(value))


def image(reference):
    if reference.startswith('sha256:'):
        references = list(state['candidate'].values()) + [row['image'] for row in state['templates'].values()]
        reference = next(value for value in references if 'sha256:' + hashlib.sha256(value.encode()).hexdigest() == reference)
    revision = state['candidate_source'] if reference in state['candidate'].values() else state['prior_source']
    return {'id': 'sha256:' + hashlib.sha256(reference.encode()).hexdigest(), 'digests': [reference],
            'user': 'ignite' if '/backend@' in reference else '', 'os': 'linux', 'arch': 'amd64',
            'volumes': None, 'revision': revision, 'source': 'https://github.com/scowalt/ignite-for-spotify-app'}


def container(name):
    if name.removeprefix('ignite-') in state['containers']:
        return state['containers'][name.removeprefix('ignite-')]
    return next(row for row in state['containers'].values() if row['id'] == name)


if args[0] == 'inspect':
    name = args[-1]
    template = args[args.index('--format') + 1]
    if name == (state.get('inspector') or {}).get('id'):
        result = {'owner': state['inspector']['owner'], 'running': False, 'mounts': []}
        if 'image_id' in template:
            result['image_id'] = state['inspector']['image_id']
        output([] if template == '{{json .Mounts}}' else result)
    elif name == (state.get('tool') or {}).get('id'):
        value = state['tool']
        output(value['mounts'] if template == '{{json .Mounts}}' else {key: item for key, item in value.items() if key != 'id'})
    elif template == '{{json .Mounts}}':
        output(container(name)['mounts'])
    elif 'Config.Env' in template:
        output([key + '=' + str(value) for key, value in state['environments'][name.removeprefix('ignite-')].items()])
    else:
        output(container(name))
elif args[:2] == ['image', 'inspect']:
    template = args[args.index('--format') + 1]
    reference = args[-1] if args[2] == '--format' else args[2]
    if 'Config.Env' in template:
        output([])
    elif template == '{{json .Config.Volumes}}':
        output(None)
    else:
        output(image(reference))
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
        assert state['containers']['backend']['running']
        print('999 999 770 100 4096\n999 999 600 101 8192')
    elif args[2] == 'timeout':
        assert state['containers']['backup']['running']
        output({'id': 'f' * 64})
    else:
        assert args[1] == 'ignite-backup' and args[2] == 'sh' and state['containers']['backup']['running']
elif args[0] == 'create':
    assert '--network' in args and args[args.index('--network') + 1] == 'none'
    assert '--read-only' in args and '--entrypoint' in args
    entrypoint = args[args.index('--entrypoint') + 1]
    labels = dict(args[index + 1].split('=', 1) for index, value in enumerate(args[:-1]) if value == '--label')
    if entrypoint == '/not-executed':
        state['inspector'] = {'id': 'f' * 64, 'owner': labels['ignite.deployer-inspect'], 'image_id': image(args[-1])['id']}
        print(state['inspector']['id'])
    else:
        assert entrypoint == '/usr/share/dotnet/dotnet'
        command = args[args.index('--entrypoint') + 3:]
        mount = args[args.index('--mount') + 1]
        source = next(part[4:] for part in mount.split(',') if part.startswith('src='))
        state['tool'] = {'id': 'b' * 64, 'owner': labels['ignite.deployer-migration'], 'action': labels['ignite.migration-action'],
                         'image_id': args[args.index('--entrypoint') + 2], 'running': False, 'exit_code': 0,
                         'mounts': [{'Type': 'bind', 'Source': source, 'Destination': '/data', 'RW': 'readonly' not in mount}],
                         'entrypoint': [entrypoint], 'command': command, 'user': '999:999', 'network': 'none',
                         'root_readonly': True, 'privileged': False}
        print(state['tool']['id'])
elif args[0] == 'cp':
    stream = io.BytesIO()
    name = args[1].split('/')[-1]
    with tarfile.open(fileobj=stream, mode='w') as archive:
        data = b'ignite:x:999:999::/nonexistent:/bin/false\n' if name == 'passwd' else json.dumps(state['metadata'][name]).encode()
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    sys.stdout.buffer.write(stream.getvalue())
elif args[0] == 'ps':
    selected = args[args.index('--filter') + 1] if '--filter' in args else None
    if selected is None:
        for value in state['containers'].values():
            print(value['id'])
        for key in ['inspector', 'tool']:
            if state.get(key):
                print(state[key]['id'])
    elif selected.startswith('label=ignite.deployer-inspect='):
        if state.get('inspector') and state['inspector']['owner'] == selected.split('=', 2)[2]:
            print(state['inspector']['id'])
    elif selected.startswith('label=ignite.deployer-migration='):
        if state.get('tool') and state['tool']['owner'] == selected.split('=', 2)[2]:
            print(state['tool']['id'])
    elif selected.startswith('name=^/ignite-'):
        name = selected.removeprefix('name=^/ignite-').removesuffix('$')
        if name in state['containers']:
            print(state['containers'][name]['id'])
elif args[0] == 'rm':
    for key in ['inspector', 'tool']:
        if state.get(key) and state[key]['id'] == args[1]:
            state[key] = None
            break
    else:
        raise SystemExit(9)
elif args[0] == 'start' and '--attach' in args:
    request = json.load(sys.stdin)
    assert request['database_path'] == '/data/ignite.db'
    action = state['tool']['action']
    state['tool']['running'] = False
    if action in ['inspect', 'inspect-stopped']:
        output(state['database_inspection'])
    elif action == 'settle':
        output({'schema': 1, 'outcome': 'settled', 'inspection': state['database_inspection']})
    else:
        rows = state['metadata']['migration-catalogue.json']['migrations']
        state['database_inspection']['history'] = [{key: row[key] for key in ['id', 'sha256']} | {'applied_at': '2026-01-01T00:00:00.0000000+00:00'} for row in rows]
        output({'schema': 1, 'outcome': 'adopted' if action == 'adopt' else 'migrated', 'inspection': state['database_inspection']})
elif args[0] in ['start', 'stop']:
    name = args[-1].removeprefix('ignite-')
    assert name in ['backup', 'backend']
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
                                             'id': image(reference)['id'].removeprefix('sha256:'), 'running': True, 'health': 'healthy'})
        state['updated'].extend(names)
    else:
        raise SystemExit(8)
else:
    raise SystemExit(9)
state_path.write_text(json.dumps(state))
