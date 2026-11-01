from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glitchtip_paseo_controller.config import ConfigurationError, load_config

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "config" / "controller.example.toml"
CAPABILITIES = {"glitchtip_api_token", "github_automation_token"}


class ConfigurationTests(unittest.TestCase):
    def test_example_configuration_is_complete_and_has_stable_fingerprint(self) -> None:
        config = load_config(
            EXAMPLE, available_capabilities=CAPABILITIES, environ={"XDG_STATE_HOME": "/var/state"}
        )

        self.assertEqual(config.glitchtip.organization, "scowalt")
        self.assertEqual(config.glitchtip.project_ids, (1, 2))
        self.assertEqual(config.github.repository, "scowalt/ignite-for-spotify-app")
        self.assertEqual(config.github.credential_capability, "github_automation_token")
        self.assertEqual(config.paseo.required_version, "0.3.1")
        self.assertEqual(config.pi.model, "gpt-5.6-terra")
        self.assertFalse(config.legacy_cleanup.enabled)
        self.assertEqual(config.legacy_cleanup.artifacts, ())
        self.assertEqual(
            config.legacy_cleanup.local_root,
            Path("/var/state/ignite-legacy-glitchtip-remediator"),
        )
        self.assertEqual(
            config.state_directory, Path("/var/state/ignite-glitchtip-paseo-controller")
        )
        self.assertEqual(
            config.workspace_root,
            Path("/var/state/ignite-glitchtip-paseo-controller-workspace"),
        )
        self.assertFalse(config.dispatch_enabled)
        self.assertEqual(
            config.fingerprint,
            load_config(
                EXAMPLE,
                available_capabilities={"github_automation_token", "glitchtip_api_token"},
                environ={"XDG_STATE_HOME": "/var/state"},
            ).fingerprint,
        )

    def test_only_the_new_repository_can_receive_controller_actions(self) -> None:
        for repository in ("scowalt/ignite-for-spotify-2", "other/ignite-for-spotify-app"):
            with self.subTest(repository=repository), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "controller.toml"
                path.write_text(
                    EXAMPLE.read_text().replace("scowalt/ignite-for-spotify-app", repository)
                )
                with self.assertRaisesRegex(ConfigurationError, "UNSUPPORTED_REPOSITORY"):
                    load_config(path, available_capabilities=CAPABILITIES)

    def test_missing_named_capability_is_a_typed_configuration_failure(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "MISSING_CAPABILITY"):
            load_config(EXAMPLE, available_capabilities={"github_automation_token"})

    def test_credential_capabilities_must_be_strings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "controller.toml"
            path.write_text(
                EXAMPLE.read_text().replace(
                    'credential_capability = "github_automation_token"',
                    "credential_capability = 42",
                )
            )
            with self.assertRaisesRegex(ConfigurationError, "INVALID_CONFIGURATION"):
                load_config(path, available_capabilities=CAPABILITIES)

    def test_unknown_static_secret_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "controller.toml"
            path.write_text(
                EXAMPLE.read_text().replace(
                    'credential_capability = "github_automation_token"', 'token = "sentinel-secret"'
                )
            )
            with self.assertRaisesRegex(ConfigurationError, "UNKNOWN_CONFIGURATION_FIELD"):
                load_config(path, available_capabilities=CAPABILITIES)

    def test_legacy_cleanup_requires_opt_in_exact_targets_and_relative_local_paths(self) -> None:
        base = EXAMPLE.read_text()
        enabled = base.replace(
            'enabled = false\nmarker = ""\nlocal_root = "${XDG_STATE_HOME:-~/.local/state}/ignite-legacy-glitchtip-remediator"\nrepositories = []\nartifacts = []',
            "\n".join(
                (
                    "enabled = true",
                    'marker = "<!-- legacy:one -->"',
                    'local_root = "/tmp/legacy"',
                    'repositories = ["scowalt/legacy-remediator"]',
                    'artifacts = [{ repository = "scowalt/legacy-remediator", pull_request = 17, branch = "automation/legacy-17", registration_path = "registrations/17.json", workspace_path = "workspaces/17" }]',
                )
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "controller.toml"
            path.write_text(enabled)
            config = load_config(path, available_capabilities=CAPABILITIES)
            artifact = config.legacy_cleanup.artifacts[0]
            self.assertEqual(artifact.registration_path, Path("/tmp/legacy/registrations/17.json"))
            self.assertEqual(artifact.workspace_path, Path("/tmp/legacy/workspaces/17"))

            path.write_text(
                enabled.replace(
                    'registration_path = "registrations/17.json"',
                    'registration_path = "../outside.json"',
                )
            )
            with self.assertRaisesRegex(ConfigurationError, "INVALID_LEGACY_LOCAL_PATH"):
                load_config(path, available_capabilities=CAPABILITIES)

            path.write_text(
                enabled.replace('repositories = ["scowalt/legacy-remediator"]', "repositories = []")
            )
            with self.assertRaisesRegex(ConfigurationError, "INCOMPLETE_LEGACY_CLEANUP"):
                load_config(path, available_capabilities=CAPABILITIES)

    def test_glitchtip_base_url_is_pinned_before_a_bearer_token_can_be_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "controller.toml"
            path.write_text(
                EXAMPLE.read_text().replace("https://glitchtip.scowalt.com", "https://evil.example")
            )
            with self.assertRaisesRegex(ConfigurationError, "UNSUPPORTED_GLITCHTIP_URL"):
                load_config(path, available_capabilities=CAPABILITIES)

    def test_workspace_root_and_dispatch_policy_are_explicit_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "controller.toml"
            path.write_text(
                EXAMPLE.read_text().replace(
                    'workspace_root = "${XDG_STATE_HOME:-~/.local/state}/ignite-glitchtip-paseo-controller-workspace"',
                    'workspace_root = "/tmp/workspace"',
                )
            )
            with self.assertRaisesRegex(ConfigurationError, "INVALID_WORKSPACE_ROOT"):
                load_config(
                    path,
                    available_capabilities=CAPABILITIES,
                    environ={"XDG_STATE_HOME": "/state"},
                )

            path.write_text(
                EXAMPLE.read_text().replace("dispatch_enabled = false", "dispatch_enabled = 1")
            )
            with self.assertRaisesRegex(ConfigurationError, "INVALID_CONFIGURATION"):
                load_config(
                    path,
                    available_capabilities=CAPABILITIES,
                    environ={"XDG_STATE_HOME": "/state"},
                )

    def test_legacy_controller_config_without_dispatch_fields_stays_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "controller.toml"
            path.write_text(
                EXAMPLE.read_text()
                .replace(
                    'workspace_root = "${XDG_STATE_HOME:-~/.local/state}/ignite-glitchtip-paseo-controller-workspace"\n',
                    "",
                )
                .replace(
                    "# Both this policy and `dispatch --once --enable-dispatch` are required.\n", ""
                )
                .replace("dispatch_enabled = false\n", "")
            )
            config = load_config(
                path, available_capabilities=CAPABILITIES, environ={"XDG_STATE_HOME": "/state"}
            )

            self.assertFalse(config.dispatch_enabled)
            self.assertIsNone(config.workspace_root)

            path.write_text(
                path.read_text().replace("[glitchtip]", "dispatch_enabled = true\n\n[glitchtip]")
            )
            with self.assertRaisesRegex(ConfigurationError, "DISPATCH_WORKSPACE_ROOT_REQUIRED"):
                load_config(
                    path,
                    available_capabilities=CAPABILITIES,
                    environ={"XDG_STATE_HOME": "/state"},
                )

    def test_state_directory_must_stay_within_effective_xdg_state_home(self) -> None:
        cases = {
            'state_directory = "/var/controller"': "INVALID_STATE_DIRECTORY",
            'state_directory = "relative/controller"': "INVALID_STATE_DIRECTORY",
            'state_directory = "${XDG_STATE_HOME:-~/.local/state}/../escape"': "INVALID_STATE_DIRECTORY",
        }
        for replacement, code in cases.items():
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "controller.toml"
                path.write_text(
                    EXAMPLE.read_text().replace(
                        'state_directory = "${XDG_STATE_HOME:-~/.local/state}/ignite-glitchtip-paseo-controller"',
                        replacement,
                    )
                )
                with self.assertRaisesRegex(ConfigurationError, code):
                    load_config(
                        path,
                        available_capabilities=CAPABILITIES,
                        environ={"XDG_STATE_HOME": "/state"},
                    )

    def test_empty_xdg_home_falls_back_and_relative_home_is_rejected(self) -> None:
        fallback = load_config(
            EXAMPLE, available_capabilities=CAPABILITIES, environ={"XDG_STATE_HOME": ""}
        )
        self.assertEqual(
            fallback.state_directory,
            Path("~/.local/state").expanduser() / "ignite-glitchtip-paseo-controller",
        )
        with self.assertRaisesRegex(ConfigurationError, "INVALID_XDG_STATE_HOME"):
            load_config(
                EXAMPLE,
                available_capabilities=CAPABILITIES,
                environ={"XDG_STATE_HOME": "relative-state"},
            )


if __name__ == "__main__":
    unittest.main()
