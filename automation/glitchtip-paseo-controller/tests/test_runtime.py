from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from glitchtip_paseo_controller.cli import main
from glitchtip_paseo_controller.clients.github import (
    GitHubCredential,
    PullRequest,
    PullRequestOutcome,
)
from glitchtip_paseo_controller.clients.glitchtip import GlitchTipIssue, IssueListing
from glitchtip_paseo_controller.clients.paseo import AgentResult, OriginMain, WorkspaceLaunch
from glitchtip_paseo_controller.config import load_config
from glitchtip_paseo_controller.remediation import remediation_identity
from glitchtip_paseo_controller.runtime import DispatchRuntime, TickResult
from glitchtip_paseo_controller.runtime_clients import RuntimeClientError
from glitchtip_paseo_controller.state import StateError, StateStore

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "config" / "controller.example.toml"
CAPABILITIES = {"glitchtip_api_token", "github_automation_token"}


def issue(identifier: str, first_seen: str, last_seen: str | None = None) -> GlitchTipIssue:
    return GlitchTipIssue(
        identifier,
        "unresolved",
        f"Issue {identifier}",
        "1",
        first_seen,
        last_seen or first_seen,
        "2",
        "backend",
    )


class FakeGlitchTip:
    def __init__(self, listings: list[tuple[IssueListing, IssueListing]]) -> None:
        self.listings = listings
        self.tick = 0
        self.resolved: list[tuple[int, str]] = []

    def list_unresolved(self, project_id: int) -> IssueListing:
        current = self.listings[min(self.tick, len(self.listings) - 1)]
        if project_id == 2:
            self.tick += 1
        return current[0] if project_id == 1 else current[1]

    def issue_context_data(
        self, *, project_id: int, issue_id: str
    ) -> tuple[GlitchTipIssue, dict[str, object]]:
        return issue(issue_id, "2026-01-11T00:00:00Z"), {"title": "Failure"}

    def latest_event(self, *, issue_id: str) -> dict[str, object]:
        del issue_id
        return {"message": "bounded event"}

    def current_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue:
        return issue(issue_id, "2026-01-11T00:00:00Z")

    def resolve_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue:
        self.resolved.append((project_id, issue_id))
        return GlitchTipIssue(
            issue_id,
            "resolved",
            "Issue",
            "1",
            "2026-01-11T00:00:00Z",
            "2026-01-11T00:00:00Z",
            str(project_id),
            "backend",
        )


class FakeGitHub:
    def __init__(self, outcome: PullRequestOutcome | None = None) -> None:
        self.outcome = outcome
        self.auto_merge_requests: list[int] = []

    def find_linked_pull_requests(
        self, *, repository: str, branch: str, marker: str
    ) -> tuple[PullRequest, ...]:
        del repository, branch, marker
        return ()

    def request_auto_merge(
        self, *, repository: str, pull_request: int, credential: GitHubCredential
    ) -> None:
        del repository, credential
        self.auto_merge_requests.append(pull_request)

    def observe_pull_request(
        self, *, repository: str, pull_request: int
    ) -> PullRequestOutcome | None:
        del repository, pull_request
        return self.outcome


class FakePaseo:
    def __init__(self) -> None:
        self.launches: list[WorkspaceLaunch] = []
        self.actions: list[tuple[str, str]] = []

    def fresh_origin_main(self) -> OriginMain:
        return OriginMain("origin/main", "a" * 40)

    def launch(self, request: WorkspaceLaunch, credential: GitHubCredential) -> AgentResult:
        del credential
        self.launches.append(request)
        return AgentResult(request.agent_identity, "running", None)

    def agent_result(self, agent_identity: str) -> AgentResult | None:
        return AgentResult(agent_identity, "running", None)

    def archive_agent(self, agent_identity: str) -> None:
        self.actions.append(("archive", agent_identity))

    def remove_workspace(self, workspace: str) -> None:
        self.actions.append(("workspace", workspace))

    def remove_local_branch(self, branch: str) -> None:
        self.actions.append(("local", branch))

    def remove_remote_branch(self, branch: str) -> None:
        self.actions.append(("remote", branch))


class DispatchRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(
            EXAMPLE,
            available_capabilities=CAPABILITIES,
            environ={"XDG_STATE_HOME": "/tmp/controller-state"},
        )
        self.credential = GitHubCredential("shared-token")

    def test_first_tick_baselines_then_next_tick_launches_one_new_issue(self) -> None:
        old = issue("old", "2026-01-01T00:00:00Z")
        new = issue("new", "2026-01-11T00:00:00Z")
        glitchtip = FakeGlitchTip(
            [
                (IssueListing((), (), (), True), IssueListing((old,), (), (), True)),
                (IssueListing((), (), (), True), IssueListing((old, new), (), (), True)),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            paseo = FakePaseo()
            runtime = self._runtime(store, glitchtip, FakeGitHub(), paseo)

            first = runtime.tick()
            second = runtime.tick()

            self.assertTrue(first.baseline_created)
            self.assertIsNone(first.launched_job)
            self.assertFalse(second.baseline_created)
            self.assertEqual(second.launched_job, 1)
            self.assertEqual(
                [(job.issue_id, job.status) for job in second.jobs], [("new", "working")]
            )
            self.assertEqual(len(paseo.launches), 1)
            runtime.close()

    def test_first_scan_uses_a_pre_listing_cutoff_and_queues_a_new_arrival(self) -> None:
        arrival = issue("arrival", "2026-01-10T00:00:01Z")
        order: list[str] = []

        class OrderedGlitchTip(FakeGlitchTip):
            def list_unresolved(self, project_id: int) -> IssueListing:
                order.append(f"listing-{project_id}")
                return super().list_unresolved(project_id)

        glitchtip = OrderedGlitchTip(
            [(IssueListing((), (), (), True), IssueListing((arrival,), (), (), True))]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            runtime = DispatchRuntime(
                self.config,
                store,
                glitchtip=glitchtip,
                github=FakeGitHub(),
                paseo=FakePaseo(),
                github_credential=self.credential,
                now=lambda: order.append("cutoff") or "2026-01-10T00:00:00Z",
            )

            result = runtime.tick()

            self.assertEqual(order[0], "cutoff")
            self.assertTrue(result.baseline_created)
            self.assertEqual(result.launched_job, 1)
            self.assertEqual(
                [(job.issue_id, job.status) for job in result.jobs], [("arrival", "working")]
            )
            runtime.close()

    def test_incomplete_first_listing_does_not_persist_a_baseline_or_issue(self) -> None:
        glitchtip = FakeGlitchTip(
            [(IssueListing((), (), (), True), IssueListing((), (), (), False))]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            runtime = self._runtime(store, glitchtip, FakeGitHub(), FakePaseo())

            with self.assertRaisesRegex(StateError, "INCOMPLETE_SCAN"):
                runtime.tick()

            self.assertIsNone(store.baseline_cutoff())
            self.assertEqual(store.issues(), ())
            self.assertEqual(store.jobs(), ())
            runtime.close()

    def test_working_job_adopts_persisted_agent_when_context_is_unavailable(self) -> None:
        class ContextOutageGlitchTip(FakeGlitchTip):
            def __init__(self) -> None:
                super().__init__([(IssueListing((), (), (), True), IssueListing((), (), (), True))])
                self.context_requests = 0

            def issue_context_data(
                self, *, project_id: int, issue_id: str
            ) -> tuple[GlitchTipIssue, dict[str, object]]:
                del project_id, issue_id
                self.context_requests += 1
                raise RuntimeClientError("GLITCHTIP_UNAVAILABLE")

        glitchtip = ContextOutageGlitchTip()
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(2, "working", 1)
            identity = remediation_identity(job, OriginMain("origin/main", "a" * 40))
            store.start_job(job.id)
            store.record_launch_intent(
                job.id,
                workspace=identity.workspace,
                agent_id=identity.agent_identity,
                branch=identity.branch,
                base=OriginMain("origin/main", "a" * 40),
                marker=identity.marker,
            )
            paseo = FakePaseo()
            runtime = self._runtime(store, glitchtip, FakeGitHub(), paseo)

            result = runtime.tick()

            self.assertEqual(result.reconciled, 1)
            self.assertEqual(result.jobs[0].status, "working")
            self.assertIsNone(result.jobs[0].failure_reason)
            self.assertEqual(glitchtip.context_requests, 0)
            self.assertEqual(paseo.launches, [])
            runtime.close()

    def test_typed_launch_failure_is_visible_and_never_retried_automatically(self) -> None:
        new = issue("typed-failure", "2026-01-11T00:00:00Z")

        class FailingPaseo(FakePaseo):
            def __init__(self) -> None:
                super().__init__()
                self.launch_attempts = 0

            def launch(self, request: WorkspaceLaunch, credential: GitHubCredential) -> AgentResult:
                del request, credential
                self.launch_attempts += 1
                raise RuntimeClientError("PASEO_UNAVAILABLE")

        glitchtip = FakeGlitchTip(
            [
                (IssueListing((), (), (), True), IssueListing((), (), (), True)),
                (IssueListing((), (), (), True), IssueListing((new,), (), (), True)),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            paseo = FailingPaseo()
            runtime = self._runtime(store, glitchtip, FakeGitHub(), paseo)

            runtime.tick()
            failed = runtime.tick()
            after_recovery_tick = runtime.tick()

            self.assertEqual(failed.jobs[0].status, "failed")
            self.assertIn("PASEO_UNAVAILABLE", failed.jobs[0].failure_reason or "")
            self.assertEqual(after_recovery_tick.jobs[0].status, "failed")
            self.assertEqual(paseo.launch_attempts, 1)
            runtime.close()

    def test_tick_launches_at_most_one_queued_job(self) -> None:
        first = issue("first", "2026-01-11T00:00:00Z")
        second = issue("second", "2026-01-11T00:00:01Z")
        glitchtip = FakeGlitchTip(
            [
                (IssueListing((), (), (), True), IssueListing((), (), (), True)),
                (IssueListing((), (), (), True), IssueListing((first, second), (), (), True)),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            paseo = FakePaseo()
            runtime = self._runtime(store, glitchtip, FakeGitHub(), paseo)

            runtime.tick()
            result = runtime.tick()

            self.assertEqual(result.launched_job, 1)
            self.assertEqual([job.status for job in result.jobs], ["working", "queued"])
            self.assertEqual(len(paseo.launches), 1)
            runtime.close()

    def test_completed_agent_with_closed_listing_pr_reconciles_a_merged_pr(self) -> None:
        class CompletedAgentPaseo(FakePaseo):
            def agent_result(self, agent_identity: str) -> AgentResult | None:
                return AgentResult(agent_identity, "complete", None)

        class ClosedListingGitHub(FakeGitHub):
            def find_linked_pull_requests(
                self, *, repository: str, branch: str, marker: str
            ) -> tuple[PullRequest, ...]:
                del repository
                return (PullRequest(42, "closed", branch, marker),)

        glitchtip = FakeGlitchTip(
            [(IssueListing((), (), (), True), IssueListing((), (), (), True))]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            store.queue_job(2, "merged-on-first-inspection", 1)
            paseo = CompletedAgentPaseo()
            runtime = self._runtime(
                store, glitchtip, ClosedListingGitHub(PullRequestOutcome(42, "merged")), paseo
            )

            runtime.tick()
            result = runtime.tick()

            self.assertEqual(result.jobs[0].status, "complete")
            self.assertEqual(result.jobs[0].pull_request, 42)
            self.assertEqual(len(paseo.launches), 1)
            self.assertEqual(glitchtip.resolved, [(2, "merged-on-first-inspection")])
            runtime.close()

    def test_awaiting_merge_retries_auto_merge_before_lifecycle_after_lost_response_and_restart(
        self,
    ) -> None:
        class LostResponseGitHub(FakeGitHub):
            def __init__(self) -> None:
                super().__init__(PullRequestOutcome(42, "open"))
                self.events: list[str] = []

            def find_linked_pull_requests(
                self, *, repository: str, branch: str, marker: str
            ) -> tuple[PullRequest, ...]:
                del repository
                self.events.append("lookup")
                return (PullRequest(42, "open", branch, marker),)

            def request_auto_merge(
                self, *, repository: str, pull_request: int, credential: GitHubCredential
            ) -> None:
                del repository, credential
                self.events.append("auto-merge")
                self.auto_merge_requests.append(pull_request)
                if len(self.auto_merge_requests) == 1:
                    raise OSError("response lost after auto-merge request")

            def observe_pull_request(
                self, *, repository: str, pull_request: int
            ) -> PullRequestOutcome | None:
                del repository, pull_request
                self.events.append("lifecycle")
                return self.outcome

        glitchtip = FakeGlitchTip(
            [(IssueListing((), (), (), True), IssueListing((), (), (), True))]
        )
        github = LostResponseGitHub()
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            store = StateStore(database)
            job = store.queue_job(2, "recover-auto-merge", 1)
            store.start_job(job.id)
            store.record_resources(
                job.id,
                workspace="workspace-recover",
                agent_id="agent-recover",
                branch="automation/recover",
                pull_request=42,
            )
            store.await_merge(job.id)

            first_runtime = self._runtime(store, glitchtip, github, FakePaseo())
            first = first_runtime.tick()

            self.assertEqual(first.jobs[0].status, "awaiting_merge")
            self.assertFalse(first.jobs[0].auto_merge_requested)
            self.assertEqual(github.events, ["lookup", "auto-merge", "lifecycle"])
            first_runtime.close()

            restarted_store = StateStore(database)
            restarted_runtime = self._runtime(restarted_store, glitchtip, github, FakePaseo())
            second = restarted_runtime.tick()

            self.assertEqual(second.jobs[0].status, "awaiting_merge")
            self.assertTrue(second.jobs[0].auto_merge_requested)
            self.assertEqual(github.auto_merge_requests, [42, 42])
            self.assertEqual(
                github.events,
                ["lookup", "auto-merge", "lifecycle", "lookup", "auto-merge", "lifecycle"],
            )
            restarted_runtime.close()

    def test_confirmed_merged_pull_request_resolves_and_cleans_up(self) -> None:
        glitchtip = FakeGlitchTip(
            [(IssueListing((), (), (), True), IssueListing((), (), (), True))]
        )
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(2, "99", 1)
            store.start_job(job.id)
            store.record_resources(
                job.id,
                workspace="workspace-99",
                agent_id="agent-99",
                branch="automation/99",
                pull_request=42,
            )
            store.await_merge(job.id)
            paseo = FakePaseo()
            runtime = self._runtime(
                store, glitchtip, FakeGitHub(PullRequestOutcome(42, "merged")), paseo
            )

            result = runtime.tick()

            self.assertEqual(result.jobs[0].status, "complete")
            self.assertEqual(glitchtip.resolved, [(2, "99")])
            self.assertEqual(
                [action for action, _ in paseo.actions], ["archive", "workspace", "local", "remote"]
            )
            runtime.close()

    def test_dispatch_cli_requires_explicit_flag_and_report_never_builds_dispatch_runtime(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "controller.toml"
            config.write_text(
                EXAMPLE.read_text().replace("dispatch_enabled = false", "dispatch_enabled = true")
            )
            calls: list[object] = []

            def factory(*_: object) -> DispatchRuntime:
                calls.append(object())
                raise AssertionError("dispatch runtime must not be built")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "dispatch",
                        "--config",
                        str(config),
                        "--once",
                        "--capability-env",
                        "glitchtip_api_token=GLITCHTIP_API_TOKEN",
                        "--capability-env",
                        "github_automation_token=GITHUB_AUTOMATION_TOKEN",
                    ],
                    environ={
                        "XDG_STATE_HOME": directory,
                        "GLITCHTIP_API_TOKEN": "gt",
                        "GITHUB_AUTOMATION_TOKEN": "gh",
                    },
                    dispatch_factory=factory,
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("EXPLICIT_DISPATCH_ENABLE_REQUIRED", output.getvalue())
            self.assertEqual(calls, [])

            with redirect_stdout(io.StringIO()):
                report_exit = main(
                    [
                        "report",
                        "--config",
                        str(config),
                        "--fixtures",
                        str(ROOT / "tests" / "fixtures"),
                        "--capability",
                        "glitchtip_api_token",
                        "--capability",
                        "github_automation_token",
                    ],
                    environ={"XDG_STATE_HOME": directory},
                    dispatch_factory=factory,
                )
            self.assertEqual(report_exit, 0)
            self.assertEqual(calls, [])

            disabled = Path(directory) / "disabled.toml"
            disabled.write_text(EXAMPLE.read_text())
            output = io.StringIO()
            with redirect_stdout(output):
                disabled_exit = main(
                    [
                        "dispatch",
                        "--config",
                        str(disabled),
                        "--once",
                        "--enable-dispatch",
                        "--capability-env",
                        "glitchtip_api_token=GLITCHTIP_API_TOKEN",
                        "--capability-env",
                        "github_automation_token=GITHUB_AUTOMATION_TOKEN",
                    ],
                    environ={
                        "XDG_STATE_HOME": directory,
                        "GLITCHTIP_API_TOKEN": "gt",
                        "GITHUB_AUTOMATION_TOKEN": "gh",
                    },
                    dispatch_factory=factory,
                )
            self.assertEqual(disabled_exit, 2)
            self.assertIn("DISPATCH_DISABLED_BY_POLICY", output.getvalue())
            self.assertEqual(calls, [])

    def test_enabled_dispatch_invokes_one_tick_without_printing_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "controller.toml"
            config.write_text(
                EXAMPLE.read_text().replace("dispatch_enabled = false", "dispatch_enabled = true")
            )
            secret = "github-token-never-rendered"
            ticks: list[object] = []
            captured: list[dict[str, str]] = []

            class OneTickRuntime:
                def tick(self) -> TickResult:
                    ticks.append(object())
                    return TickResult(False, 0, None, ())

                def close(self) -> None:
                    return None

            def factory(_: object, secrets: object, __: object) -> OneTickRuntime:
                captured.append(dict(secrets))  # type: ignore[arg-type]
                return OneTickRuntime()

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "dispatch",
                        "--config",
                        str(config),
                        "--once",
                        "--enable-dispatch",
                        "--capability-env",
                        "glitchtip_api_token=GLITCHTIP_API_TOKEN",
                        "--capability-env",
                        "github_automation_token=GITHUB_AUTOMATION_TOKEN",
                    ],
                    environ={
                        "XDG_STATE_HOME": directory,
                        "GLITCHTIP_API_TOKEN": "glitchtip-token-never-rendered",
                        "GITHUB_AUTOMATION_TOKEN": secret,
                    },
                    dispatch_factory=factory,  # type: ignore[arg-type]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(ticks), 1)
            self.assertEqual(
                captured,
                [
                    {
                        "github_automation_token": secret,
                        "glitchtip_api_token": "glitchtip-token-never-rendered",
                    }
                ],
            )
            self.assertNotIn(secret, output.getvalue())
            self.assertNotIn("glitchtip-token-never-rendered", output.getvalue())

    def test_report_keeps_a_legacy_config_without_dispatch_fields_safely_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "controller.toml"
            config.write_text(
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
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "report",
                        "--config",
                        str(config),
                        "--fixtures",
                        str(ROOT / "tests" / "fixtures"),
                        "--capability",
                        "glitchtip_api_token",
                        "--capability",
                        "github_automation_token",
                    ],
                    environ={"XDG_STATE_HOME": directory},
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Dispatch: disabled", output.getvalue())

    def _runtime(
        self, store: StateStore, glitchtip: FakeGlitchTip, github: FakeGitHub, paseo: FakePaseo
    ) -> DispatchRuntime:
        return DispatchRuntime(
            self.config,
            store,
            glitchtip=glitchtip,
            github=github,
            paseo=paseo,
            github_credential=self.credential,
            now=lambda: "2026-01-10T00:00:00Z",
        )


if __name__ == "__main__":
    unittest.main()
