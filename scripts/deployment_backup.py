import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

INPUT_LIMIT = 256 * 1024**2
SCRATCH_LIMIT = 1024**3
REMOTE_LIMIT = 512 * 1024**2
HOST = 'a2dd27ff56de48a73e384881d22e60e2.r2.cloudflarestorage.com'
BUCKET = 'ignite-for-spotify-db-backups'
REPOSITORY = 's3:https://' + HOST + '/' + BUCKET


class Stop(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def inventory_page(raw):
    root = ET.fromstring(raw)
    if root.tag != '{http://s3.amazonaws.com/doc/2006-03-01/}ListBucketResult':
        raise Stop('Unexpected storage inventory format.')
    ns = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}
    entries = root.findall('s:Contents', ns)
    sizes = [int(item.findtext('s:Size', namespaces=ns)) for item in entries]
    if any(value < 0 for value in sizes):
        raise Stop('Invalid storage inventory.')
    more = root.findtext('s:IsTruncated', default='false', namespaces=ns) == 'true'
    token = root.findtext('s:NextContinuationToken', namespaces=ns) if more else None
    if more and not token:
        raise Stop('Incomplete storage inventory.')
    return sum(sizes), len(entries), token


def bucket_inventory(env):
    if env['RESTIC_REPOSITORY'].rstrip('/') != REPOSITORY:
        raise Stop('Unexpected existing backup repository.')
    access, secret = env['AWS_ACCESS_KEY_ID'], env['AWS_SECRET_ACCESS_KEY']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    total = count = 0
    token = None
    seen = set()
    for _ in range(100):
        parameters = {'list-type': '2', 'max-keys': '1000'}
        if token:
            parameters['continuation-token'] = token
        query = urllib.parse.urlencode(sorted(parameters.items()), quote_via=urllib.parse.quote, safe='-_.~')
        now = datetime.datetime.now(datetime.timezone.utc)
        date, stamp = now.strftime('%Y%m%d'), now.strftime('%Y%m%dT%H%M%SZ')
        payload_hash = hashlib.sha256(b'').hexdigest()
        headers = {'host': HOST, 'x-amz-content-sha256': payload_hash, 'x-amz-date': stamp}
        signed = ';'.join(sorted(headers))
        canonical_headers = ''.join(key + ':' + headers[key] + '\n' for key in sorted(headers))
        canonical = '\n'.join(['GET', '/' + BUCKET, query, canonical_headers, signed, payload_hash])
        scope = date + '/auto/s3/aws4_request'
        to_sign = '\n'.join(['AWS4-HMAC-SHA256', stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        key = ('AWS4' + secret).encode()
        for part in [date, 'auto', 's3', 'aws4_request']:
            key = hmac.new(key, part.encode(), hashlib.sha256).digest()
        signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
        headers['Authorization'] = 'AWS4-HMAC-SHA256 Credential=' + access + '/' + scope + ', SignedHeaders=' + signed + ', Signature=' + signature
        request = urllib.request.Request('https://' + HOST + '/' + BUCKET + '?' + query, headers=headers)
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(4 * 1024**2 + 1)
        except Exception:
            raise Stop('Backup object-size inventory unavailable.') from None
        if len(raw) > 4 * 1024**2:
            raise Stop('Storage inventory response exceeds bound.')
        size, objects, token = inventory_page(raw)
        total += size
        count += objects
        if not token:
            return {'bytes': total, 'objects': count}
        if token in seen:
            raise Stop('Storage inventory repeated a page.')
        seen.add(token)
    raise Stop('Storage inventory exceeded pagination bound.')


class BackupTool:
    def __init__(self, docker, image, scratch, env, operation, source_mount, state_mount=None, network='host', extra_mounts=()):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}', operation):
            raise Stop('Invalid backup operation identity.')
        self.docker, self.image, self.scratch = docker, image, Path(scratch)
        allowed = {'PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONFIG', 'XDG_RUNTIME_DIR',
                   'RESTIC_REPOSITORY', 'RESTIC_PASSWORD', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION'}
        self.env = {key: value for key, value in env.items() if key in allowed}
        self.operation, self.source_mount, self.state_mount = operation, source_mount, state_mount
        self.network, self.extra_mounts = network, extra_mounts
        self.container = None

    def command(self, args, timeout=300, input=None):
        result = subprocess.run([*self.docker, *args], input=input, env=self.env,
                                capture_output=True, text=True, check=False, timeout=timeout)
        if result.returncode:
            raise Stop('Backup tooling command failed: ' + args[0])
        return result.stdout

    def start(self):
        args = ['create', '--pull', 'never', '--read-only', '--network', self.network,
                '--memory', '512m', '--memory-swap', '512m', '--cpus', '1',
                '--ulimit', f'fsize={INPUT_LIMIT}:{INPUT_LIMIT}',
                '--label', 'ignite.deployer-tool=' + self.operation,
                '--mount', self.source_mount,
                '--mount', 'type=bind,src=' + str(self.scratch) + ',dst=/scratch',
                '--entrypoint', 'sleep']
        if self.network == 'host':
            args += ['--dns', '127.0.0.53']
        if self.state_mount:
            args += ['--mount', self.state_mount]
        for mount in self.extra_mounts:
            args += ['--mount', mount]
        for name in ['RESTIC_REPOSITORY', 'RESTIC_PASSWORD', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION']:
            if name in self.env:
                args += ['--env', name]
        args += ['--env', 'TMPDIR=/scratch/tmp', '--env', 'RESTIC_CACHE_DIR=/scratch/cache', self.image, '3600']
        self.container = self.command(args).strip()
        if not re.fullmatch(r'[a-f0-9]{64}', self.container):
            raise Stop('Unexpected backup tool identity.')
        self.command(['start', self.container])
        self.exec(['sh', '-ec', 'umask 077; mkdir /scratch/tmp /scratch/cache /scratch/snapshot /scratch/restore'])

    def exec(self, args, timeout=300, input=None):
        return self.command(['exec', *(['-i'] if input is not None else []), self.container, *args], timeout, input)

    def restic(self, args, timeout=300):
        return self.exec(['restic', '--no-cache', *args], timeout)

    def snapshot_restore(self):
        configuration = json.loads(self.restic(['--no-lock', 'cat', 'config']))
        if not re.fullmatch(r'[a-f0-9]{64}', configuration.get('id', '')):
            raise Stop('Existing repository identity unavailable.')
        pages = self.exec(['sqlite3', '-readonly', '/data/ignite.db', 'PRAGMA page_count; PRAGMA page_size;']).splitlines()
        if len(pages) != 2 or not all(p.isdigit() for p in pages) or int(pages[0]) * int(pages[1]) > INPUT_LIMIT:
            raise Stop('Database exceeds snapshot input budget.')
        self.exec(['sh', '-ec', 'umask 077; sqlite3 -readonly -cmd ".timeout 60000" /data/ignite.db ".backup /scratch/snapshot/ignite.db"'])
        size = int(self.exec(['stat', '-c', '%s', '/scratch/snapshot/ignite.db']).strip())
        if size <= 0 or size > INPUT_LIMIT:
            raise Stop('Snapshot exceeds input budget.')
        if self.exec(['sqlite3', '-readonly', '/scratch/snapshot/ignite.db', 'PRAGMA quick_check;']).strip() != 'ok':
            raise Stop('Snapshot integrity failed.')
        uploaded = self.exec(['sh', '-ec', 'restic --no-cache backup --json --host ignite-production --tag ignite-database --stdin --stdin-filename ignite.db < /scratch/snapshot/ignite.db'], timeout=600)
        summaries = [json.loads(line) for line in uploaded.splitlines() if line.startswith('{')]
        snapshot_ids = [x.get('snapshot_id') for x in summaries if x.get('message_type') == 'summary' and x.get('snapshot_id')]
        if len(snapshot_ids) != 1 or not re.fullmatch(r'[a-f0-9]{8,64}', snapshot_ids[0]):
            raise Stop('New snapshot receipt unavailable; do not repeat backup.')
        snapshots = json.loads(self.restic(['--no-lock', 'snapshots', '--json', snapshot_ids[0]]))
        if len(snapshots) != 1:
            raise Stop('New snapshot identity ambiguous.')
        snap = snapshots[0]
        if (not re.fullmatch(r'[a-f0-9]{64}', snap['id']) or snap.get('hostname') != 'ignite-production' or
                'ignite-database' not in snap.get('tags', []) or snap.get('paths') != ['/ignite.db']):
            raise Stop('Snapshot identity differs from approved database backup.')
        self.restic(['restore', snap['id'], '--verify', '--include', '/ignite.db', '--target', '/scratch/restore'], timeout=600)
        if self.exec(['sqlite3', '-readonly', '/scratch/restore/ignite.db', 'PRAGMA integrity_check;']).strip() != 'ok':
            raise Stop('Restored snapshot integrity failed.')
        scratch_bytes = int(self.exec(['du', '-sk', '/scratch']).split()[0]) * 1024
        if scratch_bytes > SCRATCH_LIMIT:
            raise Stop('Scratch storage budget exceeded.')
        return {'repository_id': configuration['id'], 'snapshot_id': snap['id'], 'snapshot_time': snap['time'],
                'snapshot_bytes': size, 'restore_verified': True, 'integrity_ok': True, 'scratch_bytes': scratch_bytes}

    def marker(self):
        if not self.state_mount:
            raise Stop('Backup state mount missing.')
        filename = '/state/.deployment-success-' + self.operation
        self.exec(['sh', '-ec', 'umask 077; test ! -e "$1"; date -u +%Y-%m-%dT%H:%M:%SZ > "$1"; mv "$1" /state/last-success', 'sh', filename])

    def close(self):
        owned = self.command(['ps', '--all', '--no-trunc', '--filter', 'label=ignite.deployer-tool=' + self.operation,
                              '--format', '{{.ID}}']).splitlines()
        if (len(owned) > 1 or any(not re.fullmatch(r'[a-f0-9]{64}', identity) for identity in owned) or
                (owned and self.container and owned[0] != self.container)):
            raise Stop('Backup tool ownership is ambiguous; nothing removed.')
        self.container = owned[0] if owned else None
        if not self.container:
            if self.scratch.exists():
                self.scratch.rmdir()
            return
        identity = self.command(['inspect', '--format', '{{index .Config.Labels "ignite.deployer-tool"}}', self.container]).strip()
        if identity != self.operation:
            raise Stop('Backup tool ownership changed; not removed.')
        mounts = json.loads(self.command(['inspect', '--format', '{{json .Mounts}}', self.container]))
        scratch_mounts = [mount for mount in mounts if mount.get('Destination') == '/scratch']
        if (len(scratch_mounts) != 1 or scratch_mounts[0].get('Type') != 'bind' or
                scratch_mounts[0].get('Source') != str(self.scratch.resolve()) or
                scratch_mounts[0].get('RW') is not True):
            raise Stop('Backup scratch ownership changed; nothing removed.')
        running = self.command(['inspect', '--format', '{{json .State.Running}}', self.container]).strip()
        if running == 'true':
            self.exec(['sh', '-ec', 'rm -rf /scratch/snapshot /scratch/restore /scratch/tmp /scratch/cache'])
            self.command(['stop', '--time', '10', self.container])
        else:
            self.command(['run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                          '--label', 'ignite.deployer-tool=' + self.operation + '-cleanup',
                          '--mount', 'type=bind,src=' + str(self.scratch) + ',dst=/scratch',
                          '--entrypoint', 'sh', self.image, '-ec',
                          'rm -rf /scratch/snapshot /scratch/restore /scratch/tmp /scratch/cache'])
        self.command(['rm', '--volumes', self.container])
        self.container = None
        self.scratch.rmdir()
