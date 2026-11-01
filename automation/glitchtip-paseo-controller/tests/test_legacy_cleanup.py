from __future__ import annotations

import io
import json
import tempfile
import unittest
from collections.abc import Mapping
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from glitchtip_paseo_controller import legacy_cleanup
from glitchtip_paseo_controller.cli import main
from glitchtip_paseo_controller.clients.github import GitHubCredential
from glitchtip_paseo_controller.config import LegacyArtifactConfig, LegacyCleanupConfig
from glitchtip_paseo_controller.legacy_cleanup import (
    GitHubLegacyCleanupClient,
    LegacyGitHubResponse,
    LegacyPullRequest,
    apply_cleanup,
    confirmation_token,
    inventory,
)


class FakeLegacyRemote:
    def __init__(
        self,
        pull_requests: dict[tuple[str, int], LegacyPullRequest],
        branches: set[tuple[str, str]],
        *,
        fail_close: bool = False,
        fail_branch_delete: bool = False,
        missing_pull_request_after_branch_delete: bool = False,
    ) -> None:
        self.pull_requests = pull_requests
        self.branches = branches
        self.fail_close = fail_close
        self.fail_branch_delete = fail_branch_delete
        self.missing_pull_request_after_branch_delete = missing_pull_request_after_branch_delete
        self.calls: list[tuple[str, str, int | str]] = []

    def pull_request(self, *, repository: str, pull_request: int) -> LegacyPullRequest | None:
        self.calls.append(("pull_request", repository, pull_request))
        if self.missing_pull_request_after_branch_delete and not self.branches:
            return None
        return self.pull_requests.get((repository, pull_request))

    def close_pull_request(self, *, repository: str, pull_request: int) -> None:
        self.calls.append(("close_pull_request", repository, pull_request))
        if self.fail_close:
            raise RuntimeError("close failed")
        item = self.pull_requests[(repository, pull_request)]
        self.pull_requests[(repository, pull_request)] = LegacyPullRequest(
            repository=item.repository,
            number=item.number,
            state="closed",
            head_branch=item.head_branch,
            marker=item.marker,
        )

    def delete_branch(self, *, repository: str, branch: str) -> None:
        self.calls.append(("delete_branch", repository, branch))
        if self.fail_branch_delete:
            raise RuntimeError("branch delete failed")
        self.branches.remove((repository, branch))

    def branch_exists(self, *, repository: str, branch: str) -> bool:
        self.calls.append(("branch_exists", repository, branch))
        return (repository, branch) in self.branches


class LegacyCleanupTests(unittest.TestCase):
    repository = "scowalt/legacy-remediator"
    marker = "<!-- ignite-legacy-glitchtip-remediator:2026-07-22:17 -->"
    branch = "automation/legacy-glitchtip-17"

    def test_apply_removes_only_an_exact_registered_artifact_after_remote_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            remote = self._remote_for(artifact)

            dry_run = inventory(cleanup, remote)

            self.assertTrue(dry_run.ready)
            self.assertEqual(dry_run.eligible, (artifact,))
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertEqual(
                remote.calls,
                [
                    ("pull_request", self.repository, 17),
                    ("branch_exists", self.repository, self.branch),
                ],
            )

            result = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=True,
            )

            self.assertTrue(result.complete)
            self.assertTrue(result.cutover_enabled)
            self.assertFalse(registration.exists())
            self.assertFalse(workspace.exists())
            self.assertEqual(
                [
                    call
                    for call in remote.calls
                    if call[0] in {"close_pull_request", "delete_branch"}
                ],
                [
                    ("close_pull_request", self.repository, 17),
                    ("delete_branch", self.repository, self.branch),
                ],
            )
            self.assertGreaterEqual(sum(call[0] == "pull_request" for call in remote.calls), 3)
            self.assertGreaterEqual(sum(call[0] == "branch_exists" for call in remote.calls), 3)

    def test_inventory_skips_marker_or_repository_mismatches_without_remote_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            remote = FakeLegacyRemote(
                {
                    (self.repository, 17): LegacyPullRequest(
                        repository=self.repository,
                        number=17,
                        state="open",
                        head_branch=self.branch,
                        marker=f"{self.marker}-suffix",
                    )
                },
                {(self.repository, self.branch)},
            )

            report = inventory(cleanup, remote)

            self.assertFalse(report.ready)
            self.assertEqual(report.eligible, ())
            self.assertEqual(report.skipped[artifact], "MARKER_MISMATCH")
            self.assertEqual(remote.calls, [("pull_request", self.repository, 17)])
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())

    def test_github_client_requires_a_marker_line_equal_to_the_configured_marker(self) -> None:
        requests: list[tuple[str, str, bytes | None]] = []

        def request(
            method: str, url: str, body: bytes | None, _: Mapping[str, str]
        ) -> LegacyGitHubResponse:
            requests.append((method, url, body))
            return LegacyGitHubResponse(
                200,
                {
                    "number": 17,
                    "state": "open",
                    "head": {"ref": self.branch},
                    "base": {"repo": {"full_name": self.repository}},
                    "body": f"prefix {self.marker} suffix",
                },
            )

        client = GitHubLegacyCleanupClient(
            marker=self.marker,
            credential=GitHubCredential("sentinel"),
            request=request,
        )

        evidence = client.pull_request(repository=self.repository, pull_request=17)

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.marker, "")
        self.assertEqual(
            requests,
            [("GET", f"https://api.github.com/repos/{self.repository}/pulls/17", None)],
        )

    def test_remote_failure_keeps_every_associated_local_path_and_disables_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            remote = self._remote_for(artifact, fail_branch_delete=True)

            result = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=True,
            )

            self.assertFalse(result.complete)
            self.assertFalse(result.cutover_enabled)
            self.assertEqual(result.failed[artifact], "REMOTE_DELETE_FAILED")
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertTrue(any(call[0] == "close_pull_request" for call in remote.calls))
            self.assertGreaterEqual(sum(call[0] == "branch_exists" for call in remote.calls), 2)

    def test_partial_remote_cleanup_retries_only_branch_deletion_after_closed_pr_checkpoint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            remote = self._remote_for(artifact, fail_branch_delete=True)

            first = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=True,
            )

            self.assertFalse(first.complete)
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertEqual(remote.pull_requests[(self.repository, 17)].state, "closed")
            remote.fail_branch_delete = False
            resumed = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=True,
            )

            self.assertTrue(resumed.complete)
            self.assertEqual(sum(call[0] == "close_pull_request" for call in remote.calls), 1)
            self.assertEqual(sum(call[0] == "delete_branch" for call in remote.calls), 2)
            self.assertFalse(registration.exists())
            self.assertFalse(workspace.exists())

    def test_resumes_remote_cleaned_multiple_artifacts_after_partial_local_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            registration_two = cleanup.local_root / "registrations" / "legacy-18.json"
            workspace_two = cleanup.local_root / "workspaces" / "legacy-18"
            workspace_two.mkdir()
            artifact_two = LegacyArtifactConfig(
                repository=self.repository,
                pull_request=18,
                branch="automation/legacy-glitchtip-18",
                registration_path=registration_two,
                workspace_path=workspace_two,
            )
            registration_two.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "marker": self.marker,
                        "repository": artifact_two.repository,
                        "pull_request": artifact_two.pull_request,
                        "branch": artifact_two.branch,
                        "workspace_path": str(artifact_two.workspace_path),
                    }
                )
            )
            multiple = LegacyCleanupConfig(
                enabled=True,
                marker=self.marker,
                local_root=cleanup.local_root,
                repositories=(self.repository,),
                artifacts=(artifact, artifact_two),
            )
            remote = FakeLegacyRemote(
                {
                    (artifact.repository, artifact.pull_request): LegacyPullRequest(
                        artifact.repository,
                        artifact.pull_request,
                        "open",
                        artifact.branch,
                        self.marker,
                    ),
                    (artifact_two.repository, artifact_two.pull_request): LegacyPullRequest(
                        artifact_two.repository,
                        artifact_two.pull_request,
                        "open",
                        artifact_two.branch,
                        self.marker,
                    ),
                },
                {
                    (artifact.repository, artifact.branch),
                    (artifact_two.repository, artifact_two.branch),
                },
            )
            original_rmtree = legacy_cleanup.shutil.rmtree

            def interrupt_first_workspace(path: Path) -> None:
                if path == workspace:
                    raise OSError("interrupted local cleanup")
                original_rmtree(path)

            with patch.object(
                legacy_cleanup.shutil, "rmtree", side_effect=interrupt_first_workspace
            ):
                first = apply_cleanup(
                    multiple,
                    remote,
                    confirmation=confirmation_token(multiple),
                    legacy_service_stopped=True,
                )

            self.assertFalse(first.complete)
            self.assertEqual(first.failed[artifact], "LOCAL_DELETE_FAILED")
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertFalse(registration_two.exists())
            self.assertFalse(workspace_two.exists())
            registration.unlink()

            resumed = apply_cleanup(
                multiple,
                remote,
                confirmation=confirmation_token(multiple),
                legacy_service_stopped=True,
            )

            self.assertTrue(resumed.complete)
            self.assertFalse(workspace.exists())
            self.assertFalse(registration.exists())
            self.assertEqual(sum(call[0] == "close_pull_request" for call in remote.calls), 2)
            self.assertEqual(sum(call[0] == "delete_branch" for call in remote.calls), 2)
            for item in (artifact, artifact_two):
                checkpoint = item.registration_path.with_name(
                    f".{item.registration_path.name}.cleanup"
                )
                self.assertEqual(json.loads(checkpoint.read_text())["stage"], "local_clean")

    def test_remote_absence_resumes_from_a_registration_when_workspace_and_checkpoint_are_gone(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            legacy_cleanup._write_checkpoint(cleanup, artifact, "remote_absent")
            checkpoint = artifact.registration_path.with_name(
                f".{artifact.registration_path.name}.cleanup"
            )
            checkpoint.unlink()
            workspace.rmdir()
            remote = FakeLegacyRemote(
                {
                    (artifact.repository, artifact.pull_request): LegacyPullRequest(
                        artifact.repository,
                        artifact.pull_request,
                        "closed",
                        artifact.branch,
                        self.marker,
                    )
                },
                set(),
            )

            result = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=True,
            )

            self.assertTrue(result.complete)
            self.assertFalse(registration.exists())
            self.assertFalse(workspace.exists())
            self.assertEqual(
                [
                    call
                    for call in remote.calls
                    if call[0] in {"close_pull_request", "delete_branch"}
                ],
                [],
            )

    def test_atomic_checkpoint_failure_keeps_the_previous_resume_evidence_intact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, _, _ = self._configured_artifact(Path(directory))
            legacy_cleanup._write_checkpoint(cleanup, artifact, "close_requested")
            checkpoint = artifact.registration_path.with_name(
                f".{artifact.registration_path.name}.cleanup"
            )
            original = checkpoint.read_text()

            with patch.object(legacy_cleanup.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    legacy_cleanup._write_checkpoint(cleanup, artifact, "pull_request_closed")

            self.assertEqual(checkpoint.read_text(), original)
            self.assertEqual(
                list(checkpoint.parent.glob(f".{checkpoint.name}.*")),
                [],
            )

    def test_missing_or_ambiguous_post_delete_pull_request_never_deletes_local_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            remote = FakeLegacyRemote(
                {
                    (artifact.repository, artifact.pull_request): LegacyPullRequest(
                        repository=artifact.repository,
                        number=artifact.pull_request,
                        state="open",
                        head_branch=artifact.branch,
                        marker=self.marker,
                    )
                },
                {(artifact.repository, artifact.branch)},
                missing_pull_request_after_branch_delete=True,
            )

            result = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=True,
            )

            self.assertFalse(result.complete)
            self.assertEqual(result.failed[artifact], "REMOTE_ABSENCE_UNVERIFIED")
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())

    def test_one_invalid_artifact_prevents_mutating_any_registered_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            invalid_registration = cleanup.local_root / "registrations" / "legacy-18.json"
            invalid_workspace = cleanup.local_root / "workspaces" / "legacy-18"
            invalid_workspace.mkdir()
            invalid = LegacyArtifactConfig(
                repository=self.repository,
                pull_request=18,
                branch="automation/legacy-glitchtip-18",
                registration_path=invalid_registration,
                workspace_path=invalid_workspace,
            )
            invalid_registration.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "marker": self.marker,
                        "repository": invalid.repository,
                        "pull_request": invalid.pull_request,
                        "branch": invalid.branch,
                        "workspace_path": str(invalid.workspace_path),
                    }
                )
            )
            multiple = LegacyCleanupConfig(
                enabled=True,
                marker=self.marker,
                local_root=cleanup.local_root,
                repositories=(self.repository,),
                artifacts=(artifact, invalid),
            )
            remote = FakeLegacyRemote(
                {
                    (artifact.repository, artifact.pull_request): LegacyPullRequest(
                        artifact.repository,
                        artifact.pull_request,
                        "open",
                        artifact.branch,
                        self.marker,
                    ),
                    (invalid.repository, invalid.pull_request): LegacyPullRequest(
                        invalid.repository,
                        invalid.pull_request,
                        "open",
                        invalid.branch,
                        "different-marker",
                    ),
                },
                {(artifact.repository, artifact.branch), (invalid.repository, invalid.branch)},
            )

            result = apply_cleanup(
                multiple,
                remote,
                confirmation=confirmation_token(multiple),
                legacy_service_stopped=True,
            )

            self.assertFalse(result.complete)
            self.assertEqual(result.inventory.skipped[invalid], "MARKER_MISMATCH")
            self.assertFalse(
                any(call[0] in {"close_pull_request", "delete_branch"} for call in remote.calls)
            )
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertTrue(invalid_registration.exists())
            self.assertTrue(invalid_workspace.exists())

    def test_inventory_refuses_symlink_root_root_path_and_out_of_scope_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            cleanup, artifact, registration, workspace = self._configured_artifact(temp)
            remote = self._remote_for(artifact)
            outside = temp / "outside"
            outside.mkdir()
            symlink = cleanup.local_root / "registrations" / "linked.json"
            symlink.symlink_to(outside)
            symlink_artifact = LegacyArtifactConfig(
                repository=self.repository,
                pull_request=18,
                branch="automation/legacy-glitchtip-18",
                registration_path=symlink,
                workspace_path=workspace,
            )
            unsafe_cleanup = LegacyCleanupConfig(
                enabled=True,
                marker=self.marker,
                local_root=cleanup.local_root,
                repositories=(self.repository,),
                artifacts=(artifact, symlink_artifact),
            )

            report = inventory(unsafe_cleanup, remote)

            self.assertEqual(report.skipped[symlink_artifact], "SYMLINK_PATH")
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            outside_artifact = LegacyArtifactConfig(
                repository=self.repository,
                pull_request=19,
                branch="automation/legacy-glitchtip-19",
                registration_path=outside / "registration.json",
                workspace_path=workspace,
            )
            outside_report = inventory(
                LegacyCleanupConfig(
                    enabled=True,
                    marker=self.marker,
                    local_root=cleanup.local_root,
                    repositories=(self.repository,),
                    artifacts=(outside_artifact,),
                ),
                remote,
            )
            self.assertEqual(outside_report.skipped[outside_artifact], "OUT_OF_SCOPE_PATH")
            root_cleanup = LegacyCleanupConfig(
                enabled=True,
                marker=self.marker,
                local_root=Path("/"),
                repositories=(self.repository,),
                artifacts=(artifact,),
            )
            root_report = inventory(root_cleanup, remote)
            self.assertFalse(root_report.ready)
            self.assertEqual(root_report.skipped[artifact], "ROOT_PATH")

    def test_apply_requires_the_exact_explicit_confirmation_and_enabled_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cleanup, artifact, registration, workspace = self._configured_artifact(Path(directory))
            remote = self._remote_for(artifact)

            result = apply_cleanup(
                cleanup, remote, confirmation="DELETE", legacy_service_stopped=False
            )

            self.assertFalse(result.complete)
            self.assertFalse(result.cutover_enabled)
            self.assertEqual(result.failed[artifact], "CONFIRMATION_REQUIRED")
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertEqual(remote.calls, [])

            unfrozen = apply_cleanup(
                cleanup,
                remote,
                confirmation=confirmation_token(cleanup),
                legacy_service_stopped=False,
            )
            self.assertEqual(unfrozen.failed[artifact], "LEGACY_SERVICE_STOP_REQUIRED")
            self.assertEqual(remote.calls, [])

            disabled = LegacyCleanupConfig(
                enabled=False,
                marker=self.marker,
                local_root=cleanup.local_root,
                repositories=cleanup.repositories,
                artifacts=cleanup.artifacts,
            )
            disabled_result = apply_cleanup(
                disabled,
                remote,
                confirmation=confirmation_token(disabled),
                legacy_service_stopped=True,
            )
            self.assertFalse(disabled_result.complete)
            self.assertEqual(disabled_result.failed[artifact], "CLEANUP_DISABLED")

    def test_systemd_observe_gate_is_single_local_xdg_and_doppler_fenced(self) -> None:
        service = (
            Path(__file__).parents[1] / "systemd" / "ignite-glitchtip-paseo-controller.service"
        ).read_text()

        self.assertIn("Type=oneshot", service)
        self.assertIn("Environment=XDG_STATE_HOME=%h/.local/state", service)
        self.assertIn("ReadWritePaths=%h/.local/state/ignite-glitchtip-paseo-controller", service)
        self.assertIn("NoNewPrivileges=yes", service)
        self.assertIn("ProtectHome=read-only", service)
        self.assertIn("--project ignite-for-spotify --config prd", service)
        self.assertIn("report --config config/controller.toml --live", service)
        self.assertNotIn("DOPPLER_TOKEN=", service)
        self.assertNotIn("GITHUB_AUTOMATION_TOKEN=", service)

    def test_cli_defaults_to_dry_run_and_requires_a_confirmed_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            cleanup, artifact, registration, workspace = self._configured_artifact(temp)
            config = temp / "controller.toml"
            config.write_text(self._config_text(cleanup, artifact))
            remote = self._remote_for(artifact)

            dry_output = self._run_cli(
                "legacy-cleanup", "--config", str(config), legacy_client=remote
            )

            self.assertIn("mode=dry-run", dry_output)
            self.assertIn("eligible=1", dry_output)
            self.assertIn(f"confirmation={confirmation_token(cleanup)}", dry_output)
            self.assertTrue(registration.exists())
            self.assertTrue(workspace.exists())
            self.assertFalse(any(call[0] == "close_pull_request" for call in remote.calls))

            apply_output = self._run_cli(
                "legacy-cleanup",
                "--config",
                str(config),
                "--apply",
                "--legacy-service-stopped",
                "--confirm",
                confirmation_token(cleanup),
                legacy_client=remote,
            )

            self.assertIn("mode=apply", apply_output)
            self.assertIn("complete=yes", apply_output)
            self.assertFalse(registration.exists())
            self.assertFalse(workspace.exists())

    def _configured_artifact(
        self, temp: Path
    ) -> tuple[LegacyCleanupConfig, LegacyArtifactConfig, Path, Path]:
        root = temp / "legacy-state"
        registration = root / "registrations" / "legacy-17.json"
        workspace = root / "workspaces" / "legacy-17"
        registration.parent.mkdir(parents=True)
        workspace.mkdir(parents=True)
        artifact = LegacyArtifactConfig(
            repository=self.repository,
            pull_request=17,
            branch=self.branch,
            registration_path=registration,
            workspace_path=workspace,
        )
        registration.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "marker": self.marker,
                    "repository": artifact.repository,
                    "pull_request": artifact.pull_request,
                    "branch": artifact.branch,
                    "workspace_path": str(artifact.workspace_path),
                }
            )
        )
        return (
            LegacyCleanupConfig(
                enabled=True,
                marker=self.marker,
                local_root=root,
                repositories=(self.repository,),
                artifacts=(artifact,),
            ),
            artifact,
            registration,
            workspace,
        )

    def _remote_for(
        self, artifact: LegacyArtifactConfig, *, fail_branch_delete: bool = False
    ) -> FakeLegacyRemote:
        return FakeLegacyRemote(
            {
                (artifact.repository, artifact.pull_request): LegacyPullRequest(
                    repository=artifact.repository,
                    number=artifact.pull_request,
                    state="open",
                    head_branch=artifact.branch,
                    marker=self.marker,
                )
            },
            {(artifact.repository, artifact.branch)},
            fail_branch_delete=fail_branch_delete,
        )

    def _config_text(self, cleanup: LegacyCleanupConfig, artifact: LegacyArtifactConfig) -> str:
        return "\n".join(
            (
                "[controller]",
                'state_directory = "${XDG_STATE_HOME:-~/.local/state}/ignite-glitchtip-paseo-controller"',
                'workspace_root = "${XDG_STATE_HOME:-~/.local/state}/ignite-glitchtip-paseo-controller-workspace"',
                "dispatch_enabled = false",
                "",
                "[glitchtip]",
                'base_url = "https://glitchtip.scowalt.com"',
                'organization = "scowalt"',
                "project_ids = [1, 2]",
                'credential_capability = "glitchtip_api_token"',
                "",
                "[github]",
                'repository = "scowalt/ignite-for-spotify-app"',
                'credential_capability = "github_automation_token"',
                "",
                "[paseo]",
                'required_version = "0.3.1"',
                "",
                "[pi]",
                'model = "gpt-5.6-terra"',
                'thinking = "xhigh"',
                "",
                "[capabilities]",
                'required = ["glitchtip_api_token", "github_automation_token"]',
                "",
                "[legacy_cleanup]",
                "enabled = true",
                f"marker = {json.dumps(cleanup.marker)}",
                f"local_root = {json.dumps(str(cleanup.local_root))}",
                f"repositories = [{json.dumps(self.repository)}]",
                "",
                "[[legacy_cleanup.artifacts]]",
                f"repository = {json.dumps(artifact.repository)}",
                f"pull_request = {artifact.pull_request}",
                f"branch = {json.dumps(artifact.branch)}",
                'registration_path = "registrations/legacy-17.json"',
                'workspace_path = "workspaces/legacy-17"',
                "",
            )
        )

    @staticmethod
    def _run_cli(*argv: str, legacy_client: FakeLegacyRemote) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                argv, environ={"XDG_STATE_HOME": "/tmp/state"}, legacy_client=legacy_client
            )
        if exit_code != 0:
            raise AssertionError(f"expected success, got {exit_code}: {output.getvalue()}")
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
