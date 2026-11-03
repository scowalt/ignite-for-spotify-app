import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release_record import ReleaseRejected

from release_signature import SignatureVerifier


class ReleaseSignatureTests(unittest.TestCase):
    def test_pinned_verifier_binds_the_immutable_artifact_to_the_exact_publisher_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'cosign-fixture'
            arguments = [
                'verify', 'ghcr.io/scowalt/ignite-for-spotify-app/release@sha256:' + 'a' * 64,
                '--certificate-identity', 'https://github.com/scowalt/ignite-for-spotify-app/.github/workflows/deploy.yml@refs/heads/main',
                '--certificate-oidc-issuer', 'https://token.actions.githubusercontent.com',
                '--certificate-github-workflow-repository', 'scowalt/ignite-for-spotify-app',
                '--certificate-github-workflow-ref', 'refs/heads/main',
                '--certificate-github-workflow-sha', 'b' * 40,
            ]
            content = '#!/usr/bin/env python3\nimport sys\nraise SystemExit(0 if sys.argv[1:] == ' + repr(arguments) + ' else 1)\n'
            executable.write_text(content)
            executable.chmod(0o700)
            verifier = SignatureVerifier(executable, hashlib.sha256(content.encode()).hexdigest())
            proof = verifier.verify('sha256:' + 'a' * 64, 'b' * 40)
            self.assertEqual(proof.artifact_digest, 'sha256:' + 'a' * 64)
            self.assertEqual(proof.source_sha, 'b' * 40)

    def test_runtime_secrets_and_verification_overrides_are_not_inherited(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'cosign-fixture'
            content = '#!/usr/bin/env python3\nimport os\nraise SystemExit(1 if any(k in os.environ for k in ["SENTRY_AUTH_TOKEN", "RESTIC_PASSWORD", "COSIGN_TUF_ROOT"]) else 0)\n'
            executable.write_text(content)
            executable.chmod(0o700)
            verifier = SignatureVerifier(executable, hashlib.sha256(content.encode()).hexdigest())
            with patch.dict(os.environ, {'SENTRY_AUTH_TOKEN': 'fixture-private', 'RESTIC_PASSWORD': 'fixture-private', 'COSIGN_TUF_ROOT': '/unreviewed'}):
                self.assertEqual(verifier.verify('sha256:' + 'a' * 64, 'b' * 40).source_sha, 'b' * 40)

    def test_modified_verifier_and_rejected_signature_never_return_proof_or_raw_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'cosign-fixture'
            content = '#!/usr/bin/env python3\nimport sys\nprint("fixture-private-error", file=sys.stderr)\nraise SystemExit(1)\n'
            executable.write_text(content)
            executable.chmod(0o700)
            verifier = SignatureVerifier(executable, hashlib.sha256(content.encode()).hexdigest())
            with self.assertRaises(ReleaseRejected) as failure:
                verifier.verify('sha256:' + 'a' * 64, 'b' * 40)
            self.assertNotIn('fixture-private-error', str(failure.exception))
            executable.write_text('#!/usr/bin/env python3\nraise SystemExit(0)\n')
            with self.assertRaises(ReleaseRejected):
                verifier.verify('sha256:' + 'a' * 64, 'b' * 40)

    def test_publisher_authorization_without_source_binding_does_not_issue_deployment_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'cosign-fixture'
            content = '#!/usr/bin/env python3\nimport sys\nassert "--certificate-identity" in sys.argv\nassert "--certificate-github-workflow-sha" not in sys.argv\n'
            executable.write_text(content)
            executable.chmod(0o700)
            verifier = SignatureVerifier(executable, hashlib.sha256(content.encode()).hexdigest())
            self.assertIsNone(verifier.authorize('sha256:' + 'a' * 64))


if __name__ == '__main__':
    unittest.main()
