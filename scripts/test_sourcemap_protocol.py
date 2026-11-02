import json
import os
import shlex
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def workflow_commands():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
    step = workflow.split("      - name: Upload source maps to GlitchTip\n", 1)[
        1
    ].split("\n      - name:", 1)[0]
    commands = step.split("        run: |\n", 1)[1].split("        env:\n", 1)[0]
    return [shlex.split(line.strip()) for line in commands.splitlines() if line.strip()]


class SourceMapWorkflowTests(unittest.TestCase):
    def test_upload_targets_only_the_isolated_frontend_organization(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        step = workflow.split("      - name: Upload source maps to GlitchTip\n", 1)[
            1
        ].split("\n      - name:", 1)[0]
        self.assertIn("SENTRY_ORG: ignite-for-spotify-app-frontend", step)
        self.assertIn("SENTRY_PROJECT: ignite-for-spotify-frontend", step)
        self.assertIn("SENTRY_AUTH_TOKEN: ${{ secrets.GLITCHTIP_AUTH_TOKEN }}", step)
        self.assertNotIn("SENTRY_ORG: scowalt", step)
        self.assertNotIn("continue-on-error", step)

    def test_upload_step_is_pinned_and_has_no_release_commands(self):
        self.assertEqual(
            workflow_commands(),
            [
                [
                    "npx",
                    "--yes",
                    "@sentry/cli@3.8.2",
                    "sourcemaps",
                    "inject",
                    "frontend/dist",
                ],
                [
                    "npx",
                    "--yes",
                    "@sentry/cli@3.8.2",
                    "sourcemaps",
                    "upload",
                    "frontend/dist",
                ],
            ],
        )


class SourceMapApi(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, value):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.server.requests.append(("GET", self.path))
        if self.path != "/api/0/organizations/fixture/chunk-upload/":
            self.respond(405, {})
            return
        self.respond(
            200,
            {
                "url": f"http://127.0.0.1:{self.server.server_port}/chunks/",
                "chunkSize": 8388608,
                "chunksPerRequest": 64,
                "maxRequestSize": 33554432,
                "maxFileSize": 2147483648,
                "concurrency": 1,
                "hashAlgorithm": "sha1",
                "compression": ["gzip"],
                "accept": ["artifact_bundles"],
            },
        )

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.requests.append(("POST", self.path))
        if self.path == "/chunks/":
            self.server.uploaded_bytes += len(body)
            self.respond(200, [])
        elif self.path == "/api/0/organizations/fixture/artifactbundle/assemble/":
            request = json.loads(body)
            self.server.assemblies.append(request)
            if self.server.uploaded_bytes:
                self.respond(200, {"state": "ok", "missingChunks": []})
            else:
                self.respond(
                    200, {"state": "not_found", "missingChunks": request["chunks"]}
                )
        else:
            self.respond(405, {})

    def do_PUT(self):
        self.server.requests.append(("PUT", self.path))
        self.respond(405, {})


@unittest.skipUnless(
    os.environ.get("SENTRY_CLI_EXECUTABLE"), "Pinned CLI required for protocol test"
)
class SourceMapProtocolTests(unittest.TestCase):
    def test_pinned_debug_id_upload_never_creates_or_finalizes_a_release(self):
        executable = str(Path(os.environ["SENTRY_CLI_EXECUTABLE"]).resolve())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            dist.mkdir()
            (dist / "fixture.js").write_text("console.log(42);\n")
            source_map = dist / "fixture.js.map"
            source_map.write_text(
                json.dumps(
                    {
                        "version": 3,
                        "file": "fixture.js",
                        "sources": ["fixture.ts"],
                        "sourcesContent": ["console.log(42);\n"],
                        "names": [],
                        "mappings": "AAAA",
                    }
                )
            )
            with ThreadingHTTPServer(("127.0.0.1", 0), SourceMapApi) as server:
                server.requests = []
                server.assemblies = []
                server.uploaded_bytes = 0
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                env = {
                    "PATH": os.environ["PATH"],
                    "HOME": directory,
                    "SENTRY_URL": f"http://127.0.0.1:{server.server_port}",
                    "SENTRY_AUTH_TOKEN": "fixture-token",
                    "SENTRY_ORG": "fixture",
                    "SENTRY_PROJECT": "fixture",
                    "SENTRY_DISABLE_UPDATE_CHECK": "1",
                    "SENTRY_HTTP_MAX_RETRIES": "0",
                    "GITHUB_SHA": "a" * 40,
                    "GITHUB_REPOSITORY": "fixture/fixture",
                    "CI": "true",
                }
                try:
                    version = subprocess.run(
                        [executable, "--version"],
                        env=env,
                        cwd=root,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=30,
                    )
                    self.assertEqual(version.stdout.strip(), "sentry-cli 3.8.2")
                    for command in workflow_commands():
                        result = subprocess.run(
                            [executable, *command[3:-1], str(dist)],
                            env=env,
                            cwd=root,
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=False,
                        )
                        self.assertEqual(
                            result.returncode, 0, result.stdout + result.stderr
                        )
                    injected_map = json.loads(source_map.read_text())
                    self.assertTrue(
                        injected_map.get("debugId") or injected_map.get("debug_id")
                    )
                    self.assertGreater(server.uploaded_bytes, 0)
                    self.assertTrue(server.assemblies)
                    self.assertTrue(
                        all(not value.get("release") for value in server.assemblies)
                    )
                    self.assertEqual(
                        set(server.requests),
                        {
                            ("GET", "/api/0/organizations/fixture/chunk-upload/"),
                            (
                                "POST",
                                "/api/0/organizations/fixture/artifactbundle/assemble/",
                            ),
                            ("POST", "/chunks/"),
                        },
                    )
                finally:
                    server.shutdown()
                    worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
