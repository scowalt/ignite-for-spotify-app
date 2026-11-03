import json
import os
from pathlib import Path
import sys
import time

root = Path(sys.argv[1])
state = root / 'container.json'
args = sys.argv[2:]
assert 'SHOULD_NOT_INHERIT' not in os.environ
with (root / 'commands.jsonl').open('a') as stream:
    stream.write(json.dumps(args) + '\n')
identifier = 'c' * 64
if args[:2] == ['image', 'inspect']:
    print('null')
elif args[0] == 'ps':
    if state.exists():
        print(identifier)
elif args[0] == 'create':
    labels = [args[index + 1] for index, value in enumerate(args[:-1]) if value == '--label']
    owner = next(label.split('=', 1)[1] for label in labels if label.startswith('ignite.deployer-migration='))
    action = next(label.split('=', 1)[1] for label in labels if label.startswith('ignite.migration-action='))
    mount = args[args.index('--mount') + 1]
    source = next(part[4:] for part in mount.split(',') if part.startswith('src='))
    command = args[args.index('--entrypoint') + 3:]
    value = {'owner': owner, 'action': action, 'image_id': 'sha256:' + 'a' * 64,
             'running': False, 'exit_code': 0, 'mounts': [{'Type': 'bind', 'Source': source, 'Destination': '/data', 'RW': 'readonly' not in mount}],
             'entrypoint': ['/usr/share/dotnet/dotnet'], 'command': command,
             'user': '999:999', 'network': 'none', 'root_readonly': True, 'privileged': False}
    state.write_text(json.dumps(value))
    (root / 'created.json').write_text(json.dumps(value))
    print(identifier)
elif args[0] == 'start':
    value = json.loads(state.read_text())
    value['running'] = True
    state.write_text(json.dumps(value))
    json.load(sys.stdin)
    if (root / 'mode').exists() and (root / 'mode').read_text() == 'hang':
        print('fixture-private', file=sys.stderr, flush=True)
        time.sleep(60)
    result = {'schema': 1, 'schema_sha256': 'b' * 64, 'history': None}
    value['running'] = False
    state.write_text(json.dumps(value))
    print(json.dumps(result))
elif args[0] == 'inspect':
    print(state.read_text())
elif args[0] == 'stop':
    value = json.loads(state.read_text())
    value['running'] = False
    state.write_text(json.dumps(value))
    (root / 'stopped').write_text('owned')
    print(identifier)
elif args[0] == 'rm':
    state.unlink()
    print(identifier)
else:
    raise SystemExit('Unexpected operation')
