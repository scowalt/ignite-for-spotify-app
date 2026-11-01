import copy
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_production_config", ROOT / "scripts/verify-production-config.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def render(extra=None):
    with tempfile.TemporaryDirectory() as directory:
        env = {"PATH": os.environ["PATH"], "HOME": directory}
        env.update(
            {
                name: "fixture"
                for name in (
                    "SPOTIFY_CLIENT_ID",
                    "SPOTIFY_CLIENT_SECRET",
                    "SPOTIFY_REDIRECT_URI",
                    "RESTIC_REPOSITORY",
                    "RESTIC_PASSWORD",
                    "R2_ACCESS_KEY_ID",
                    "R2_SECRET_ACCESS_KEY",
                    "DOMAIN",
                    "LOKI_URL",
                    "LOKI_USERNAME",
                    "LOKI_API_KEY",
                    "PROMETHEUS_URL",
                    "PROMETHEUS_USERNAME",
                    "PROMETHEUS_API_KEY",
                )
            }
        )
        env.update(extra or {})
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                "/dev/null",
                "--project-directory",
                directory,
                "-f",
                str(ROOT / "docker/docker-compose.prod.yml"),
                "config",
                "--format",
                "json",
            ],
            env=env,
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)


class ProductionConfigurationTests(unittest.TestCase):
    def test_new_image_names_preserve_existing_project_and_volumes(self):
        config = render()
        self.assertEqual(config["name"], "ignite-for-spotify")
        self.assertEqual(MODULE.validate(config), [])
        self.assertEqual(
            config["services"]["backup"]["environment"]["BACKUP_ON_START"], "false"
        )

    def test_all_three_services_support_explicit_digest_pinning(self):
        env = {
            f"{name.upper()}_IMAGE": f"{MODULE.IMAGE_PREFIX}{name}@sha256:{'a' * 64}"
            for name in ("backend", "frontend", "backup")
        }
        self.assertEqual(MODULE.validate(render(env), require_digests=True), [])

    def test_legacy_rollback_requires_explicit_mode_and_immutable_digests(self):
        env = {
            f"{name.upper()}_IMAGE": f"{MODULE.LEGACY_PREFIX}{name}@sha256:{'b' * 64}"
            for name in ("backend", "frontend", "backup")
        }
        config = render(env)
        self.assertTrue(MODULE.validate(config, require_digests=True))
        self.assertEqual(MODULE.validate(config, rollback=True), [])
        env["BACKEND_IMAGE"] = MODULE.LEGACY_PREFIX + "backend:latest"
        self.assertTrue(MODULE.validate(render(env), rollback=True))

    def test_rejects_project_override_and_new_data_volumes(self):
        self.assertTrue(
            MODULE.validate(render({"COMPOSE_PROJECT_NAME": "wrong-project"}))
        )
        config = render()
        config["volumes"]["ignite-data"]["name"] = "new-empty-data"
        self.assertTrue(MODULE.validate(config))

    def test_rejects_changed_data_mount_or_empty_database_policy(self):
        original = render()
        changed_mount = copy.deepcopy(original)
        changed_mount["services"]["backend"]["volumes"][0]["target"] = "/different-data"
        self.assertTrue(MODULE.validate(changed_mount))
        original["services"]["backend"]["environment"]["Database__RequireExisting"] = (
            "false"
        )
        self.assertTrue(MODULE.validate(original))

    def test_first_release_rejects_mutable_latest(self):
        self.assertTrue(MODULE.validate(render(), require_digests=True))


if __name__ == "__main__":
    unittest.main()
