import hashlib
import os
from pathlib import Path
import re
import subprocess

from release_record import OIDC_ISSUER, PUBLISHER_IDENTITY, REPOSITORY, ReleaseRejected, SignatureProof

COSIGN_SHA256 = '424e2c97d0b45fd7a6b608a87f090f35633f4c23ece5f092d48bba11aaf4bbfa'
RELEASE_IMAGE = 'ghcr.io/' + REPOSITORY + '/release'


class SignatureVerifier:
    def __init__(self, executable: Path, checksum: str = COSIGN_SHA256):
        self.executable = executable
        self.checksum = checksum

    def authorize(self, artifact_digest: str) -> None:
        self._execute(artifact_digest, None)

    def verify(self, artifact_digest: str, source_sha: str) -> SignatureProof:
        if not isinstance(source_sha, str) or not re.fullmatch(r'[a-f0-9]{40}', source_sha):
            raise ReleaseRejected('Invalid signature source.')
        self._execute(artifact_digest, source_sha)
        return SignatureProof(artifact_digest, source_sha, PUBLISHER_IDENTITY, OIDC_ISSUER)

    def _execute(self, artifact_digest, source_sha):
        if not isinstance(artifact_digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', artifact_digest):
            raise ReleaseRejected('Invalid signature subject.')
        try:
            with self.executable.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != self.checksum:
                raise ReleaseRejected('Pinned verifier integrity check failed.')
            result = subprocess.run([
                str(self.executable), 'verify', RELEASE_IMAGE + '@' + artifact_digest,
                '--certificate-identity', PUBLISHER_IDENTITY,
                '--certificate-oidc-issuer', OIDC_ISSUER,
                '--certificate-github-workflow-repository', REPOSITORY,
                '--certificate-github-workflow-ref', 'refs/heads/main',
            ] + (['--certificate-github-workflow-sha', source_sha] if source_sha is not None else []), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={key: os.environ[key] for key in ['PATH', 'HOME', 'DOCKER_CONFIG', 'XDG_CACHE_HOME'] if key in os.environ},
                timeout=180, check=False)
        except (OSError, subprocess.SubprocessError):
            raise ReleaseRejected('Signature verifier unavailable; output withheld.') from None
        if result.returncode:
            raise ReleaseRejected('Release signature verification failed; output withheld.')
