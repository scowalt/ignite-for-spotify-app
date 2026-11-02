import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GlitchTipRoutingTests(unittest.TestCase):
    def invoke(self, organization=None, project="2"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            output = path / "request.json"
            curl = path / "curl"
            curl.write_text(
                f"#!{sys.executable}\n"
                "import json,os,sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['FIXTURE_REQUEST']).write_text(json.dumps({"
                "'method':sys.argv[sys.argv.index('-X')+1],'url':sys.argv[-1]}))\n"
                "print('[]')\n"
            )
            curl.chmod(0o700)
            env = {
                "PATH": directory + os.pathsep + os.environ["PATH"],
                "HOME": directory,
                "GLITCHTIP_API_TOKEN": "fixture-token",
                "FIXTURE_REQUEST": str(output),
            }
            if organization is not None:
                env["GLITCHTIP_ORG"] = organization
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/glitchtip"), "list", "--project", project],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            return result, json.loads(output.read_text()) if output.exists() else None

    def test_legacy_organization_remains_the_default(self):
        result, request = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            request,
            {
                "method": "GET",
                "url": "https://glitchtip.scowalt.com/api/0/organizations/scowalt/issues/?query=is:unresolved&project=2",
            },
        )

    def test_isolated_frontend_is_opt_in(self):
        result, request = self.invoke("ignite-for-spotify-app-frontend", "8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            request,
            {
                "method": "GET",
                "url": "https://glitchtip.scowalt.com/api/0/organizations/ignite-for-spotify-app-frontend/issues/?query=is:unresolved&project=8",
            },
        )

    def test_unreviewed_organizations_make_no_request(self):
        for organization in ["other", "../scowalt", "scowalt?extra=true"]:
            with self.subTest(organization=organization):
                result, request = self.invoke(organization)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(request)
                self.assertNotIn("fixture-token", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
