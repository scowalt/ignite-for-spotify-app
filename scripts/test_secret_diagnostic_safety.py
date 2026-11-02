import os
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES = [
    "diagnose-upload-secret.yml",
    "diagnose-upload-secret-reusable.yml",
    "diagnose-upload-secret-declared.yml",
]


class SecretDiagnosticSafetyTests(unittest.TestCase):
    def test_checks_disclose_only_presence_and_fail_when_missing(self):
        for name in PROBES:
            with self.subTest(workflow=name):
                source = (ROOT / ".github/workflows" / name).read_text()
                self.assertIn("permissions: {}", source)
                self.assertIn("environment: production", source)
                self.assertIn("github.ref == 'refs/heads/main'", source)
                self.assertNotIn("secrets: inherit", source)
                self.assertNotIn("packages: write", source)
                self.assertNotIn("actions/checkout", source)
                lines = []
                for line in source.split("        run: |\n", 1)[1].splitlines():
                    if line.strip() and not line.startswith("          "):
                        break
                    lines.append(line)
                if not lines:
                    self.fail("Missing diagnostic shell body")
                command = textwrap.dedent("\n".join(lines))
                for value in ["", "fixture-private-value"]:
                    result = subprocess.run(
                        ["bash", "-e", "-c", command],
                        env={"PATH": os.environ["PATH"], "SENTRY_AUTH_TOKEN": value},
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0 if value else 1)
                    self.assertIn("present" if value else "absent", result.stdout)
                    self.assertNotIn("fixture-private-value", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
