from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

REPOSITORY = 'scowalt/ignite-for-spotify-app'
REPOSITORY_ID = 1441388195
WORKFLOW_ID = 403197563
PUBLISHER_IDENTITY = 'https://github.com/' + REPOSITORY + '/.github/workflows/deploy.yml@refs/heads/main'
OIDC_ISSUER = 'https://token.actions.githubusercontent.com'
CONTRACT_PATHS = (
    'docker/docker-compose.prod.yml',
    'docker/backup/backup.sh',
    'docker/backup/restore.sh',
    'docker/backup/entrypoint.sh',
    'docker/backup/healthcheck.sh',
    'docker/backup/crontab',
    'backend/src/Ignite.Api/Program.fs',
    'backend/src/Ignite.Api/DatabaseReadiness.fs',
    'backend/src/Ignite.Infrastructure/DependencyInjection.fs',
    'backend/src/Ignite.Infrastructure/Data/DatabaseConfiguration.fs',
    'scripts/verify-production-config.py',
)


class ReleaseRejected(ValueError):
    pass


class ReleasePending(ReleaseRejected):
    pass


@dataclass(frozen=True)
class SignatureProof:
    artifact_digest: str
    source_sha: str
    identity: str
    issuer: str


@dataclass(frozen=True)
class ReleaseRecord:
    source_sha: str
    run_id: int
    run_attempt: int
    run_number: int
    contract_sha256: str
    images: tuple[tuple[str, str], ...]
    artifact_digest: str

    @property
    def order(self) -> tuple[int, int]:
        return self.run_number, self.run_attempt


def deployment_contract(root: Path) -> str:
    root = root.resolve()
    rows = []
    for name in CONTRACT_PATHS:
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ReleaseRejected('Reviewed runtime contract input is unavailable.')
        with path.open('rb') as stream:
            content = stream.read(2 * 1024**2 + 1)
        if len(content) > 2 * 1024**2:
            raise ReleaseRejected('Runtime contract input exceeds its bound.')
        rows.append((name, hashlib.sha256(content).hexdigest()))
    return hashlib.sha256(json.dumps(sorted(rows), separators=(',', ':')).encode()).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseRejected('Duplicate release field.')
        result[key] = value
    return result


def _decode_record(payload: bytes, expected_contract: str) -> dict:
    if not isinstance(payload, bytes) or len(payload) > 32768:
        raise ReleaseRejected('Release record exceeds its input bound.')
    try:
        record = json.loads(payload, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ReleaseRejected('Malformed release record.') from None
    fields = {'schema', 'repository', 'source_sha', 'run_id', 'run_attempt', 'run_number', 'contract_sha256', 'images'}
    if not isinstance(record, dict) or set(record) != fields:
        raise ReleaseRejected('Unexpected release schema.')
    if type(record['schema']) is not int or record['schema'] != 1 or record['repository'] != REPOSITORY:
        raise ReleaseRejected('Unsupported release identity or schema.')
    if not isinstance(record['source_sha'], str) or not re.fullmatch(r'[a-f0-9]{40}', record['source_sha']):
        raise ReleaseRejected('Invalid source revision.')
    if any(type(record[field]) is not int or not 0 < record[field] < 2**63 for field in ['run_id', 'run_attempt', 'run_number']):
        raise ReleaseRejected('Invalid workflow identity.')
    if (not isinstance(expected_contract, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_contract) or
            record['contract_sha256'] != expected_contract):
        raise ReleaseRejected('Deployment or schema contract requires manual review.')
    images = record.get('images')
    if not isinstance(images, dict) or set(images) != {'backend', 'backup', 'frontend'}:
        raise ReleaseRejected('A complete three-image release is required.')
    for name, image in images.items():
        prefix = 'ghcr.io/' + REPOSITORY + '/' + name
        if not isinstance(image, str) or not re.fullmatch(re.escape(prefix) + r'@sha256:[a-f0-9]{64}', image):
            raise ReleaseRejected('Release images must use exact digests in their own fresh namespace.')
    return record


def create_release_record(root: Path, environment: dict[str, str], images: dict[str, str]) -> bytes:
    if (environment.get('GITHUB_REPOSITORY') != REPOSITORY or
            environment.get('GITHUB_REF') != 'refs/heads/main' or
            environment.get('GITHUB_EVENT_NAME') not in ['push', 'workflow_dispatch']):
        raise ReleaseRejected('Only the trusted main publisher can create a release record.')
    contract = deployment_contract(root)
    try:
        record = {'schema': 1, 'repository': REPOSITORY, 'source_sha': environment['GITHUB_SHA'],
                  'run_id': int(environment['GITHUB_RUN_ID']), 'run_attempt': int(environment['GITHUB_RUN_ATTEMPT']),
                  'run_number': int(environment['GITHUB_RUN_NUMBER']), 'contract_sha256': contract, 'images': images}
    except (KeyError, ValueError, TypeError):
        raise ReleaseRejected('Required publisher identity is unavailable.') from None
    encoded = json.dumps(record, sort_keys=True, separators=(',', ':')).encode()
    _decode_record(encoded, contract)
    return encoded


def validate_release(
    payload: bytes,
    proof: SignatureProof | None,
    run: object,
    expected_contract: str,
) -> ReleaseRecord:
    if proof is None:
        raise ReleaseRejected('Signature verification is required.')
    record = _decode_record(payload, expected_contract)
    if (not isinstance(proof, SignatureProof) or proof.identity != PUBLISHER_IDENTITY or
            proof.issuer != OIDC_ISSUER or proof.source_sha != record['source_sha'] or
            not isinstance(proof.artifact_digest, str) or
            not re.fullmatch(r'sha256:[a-f0-9]{64}', proof.artifact_digest)):
        raise ReleaseRejected('Publisher signature identity does not match this release.')
    if not isinstance(run, dict):
        raise ReleaseRejected('Workflow evidence is unavailable.')
    required_run = {'id': record['run_id'], 'run_attempt': record['run_attempt'],
                    'run_number': record['run_number'], 'head_sha': record['source_sha'],
                    'head_branch': 'main',
                    'workflow_id': WORKFLOW_ID, 'path': '.github/workflows/ci.yml'}
    if any(type(run.get(key)) is not type(value) or run.get(key) != value for key, value in required_run.items()):
        raise ReleaseRejected('Workflow evidence does not match the completed release.')
    if run.get('event') not in ['push', 'workflow_dispatch']:
        raise ReleaseRejected('Only trusted main release events are accepted.')
    for key in ['repository', 'head_repository']:
        repository = run.get(key)
        if not isinstance(repository, dict) or type(repository.get('id')) is not int or repository['id'] != REPOSITORY_ID:
            raise ReleaseRejected('Workflow repository identity changed.')
    if run.get('status') in ['queued', 'in_progress', 'waiting', 'pending', 'requested']:
        raise ReleasePending('Trusted workflow has not completed yet.')
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        raise ReleaseRejected('Only a successfully completed workflow is deployable.')
    return ReleaseRecord(record['source_sha'], record['run_id'], record['run_attempt'],
                         record['run_number'], record['contract_sha256'],
                         tuple(sorted(record['images'].items())), proof.artifact_digest)
