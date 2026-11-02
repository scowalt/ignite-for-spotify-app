import os
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_configuration_step():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
    return workflow.split("      - name: Verify release configuration\n", 1)[1].split(
        "\n      - name:", 1
    )[0]


class ReleaseCredentialTests(unittest.TestCase):
    def test_caller_passes_only_the_required_upload_secret(self):
        caller = (ROOT / ".github/workflows/ci.yml").read_text()
        publisher = caller.split("  publish:\n", 1)[1].split("\n  backend:", 1)[0]
        self.assertIn("    secrets:\n", publisher)
        self.assertEqual(
            publisher.split("    secrets:\n", 1)[1].strip(),
            "GLITCHTIP_AUTH_TOKEN: ${{ secrets.GLITCHTIP_AUTH_TOKEN }}",
        )
        callee = (ROOT / ".github/workflows/deploy.yml").read_text()
        contract = callee.split("  workflow_call:\n", 1)[1].split("\nenv:", 1)[0]
        self.assertEqual(
            textwrap.dedent(contract).strip(),
            "secrets:\n  GLITCHTIP_AUTH_TOKEN:\n    required: true",
        )
        self.assertNotIn("secrets: inherit", caller + callee)

    def test_real_configuration_step_rejects_missing_enabled_upload_credential(self):
        step = release_configuration_step()
        command = textwrap.dedent(step.split("        run: |\n", 1)[1])
        cases = [("true", "", 1), ("true", "fixture-private-value", 0), ("false", "", 0)]
        for enabled, credential, expected in cases:
            with self.subTest(enabled=enabled, present=bool(credential)):
                result = subprocess.run(
                    ["bash", "-e", "-c", command],
                    env={
                        "PATH": os.environ["PATH"],
                        "CUTOVER_COMPLETE": "true",
                        "VITE_POSTHOG_KEY": "fixture-browser-key",
                        "VITE_SENTRY_DSN": "fixture-browser-dsn",
                        "SOURCEMAPS_ENABLED": enabled,
                        "SENTRY_AUTH_TOKEN": credential,
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, expected)
                self.assertNotIn("fixture-private-value", result.stdout + result.stderr)

    def test_guard_binds_the_protected_secret_before_building_or_uploading(self):
        step = release_configuration_step()
        self.assertIn("SOURCEMAPS_ENABLED: ${{ vars.GLITCHTIP_SOURCEMAPS_ENABLED }}", step)
        self.assertIn("SENTRY_AUTH_TOKEN: ${{ secrets.GLITCHTIP_AUTH_TOKEN }}", step)
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        self.assertLess(workflow.index("Verify release configuration"), workflow.index("Build frontend"))
        self.assertLess(workflow.index("Verify release configuration"), workflow.index("Upload source maps"))


if __name__ == "__main__":
    unittest.main()
