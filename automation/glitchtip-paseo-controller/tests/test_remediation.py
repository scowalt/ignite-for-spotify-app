from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Literal

from glitchtip_paseo_controller.clients.github import GitHubCredential, PullRequest
from glitchtip_paseo_controller.clients.paseo import AgentResult, OriginMain, WorkspaceLaunch
from glitchtip_paseo_controller.context import (
    Breadcrumb,
    IssueContext,
    StackFrame,
    build_issue_context,
    render_issue_context,
)
from glitchtip_paseo_controller.remediation import RemediationService, remediation_identity
from glitchtip_paseo_controller.state import StateError, StateStore


class FakePaseo:
    def __init__(self, launch_status: Literal["running", "complete", "failed"] = "running") -> None:
        self.origin_requests = 0
        self.origin = OriginMain("origin/main", "a" * 40)
        self.launch_status = launch_status
        self.launch_result_identity: str | None = None
        self.launches: list[WorkspaceLaunch] = []
        self.credentials: list[GitHubCredential] = []
        self.agent_requests: list[str] = []
        self.raise_agent_lookup = False
        self.results: dict[str, AgentResult | None] = {}

    def fresh_origin_main(self) -> OriginMain:
        self.origin_requests += 1
        return self.origin

    def agent_result(self, agent_identity: str) -> AgentResult | None:
        self.agent_requests.append(agent_identity)
        if self.raise_agent_lookup:
            raise OSError("agent lookup unavailable")
        return self.results.get(agent_identity)

    def launch(self, request: WorkspaceLaunch, credential: GitHubCredential) -> AgentResult:
        self.launches.append(request)
        self.credentials.append(credential)
        result = AgentResult(
            self.launch_result_identity or request.agent_identity, self.launch_status, None
        )
        self.results[request.agent_identity] = result
        return result


class ResponseLostPaseo(FakePaseo):
    def launch(self, request: WorkspaceLaunch, credential: GitHubCredential) -> AgentResult:
        self.launches.append(request)
        self.credentials.append(credential)
        self.results[request.agent_identity] = AgentResult(request.agent_identity, "running", None)
        raise OSError("launch response lost")


class FakeGitHub:
    def __init__(self) -> None:
        self.pull_requests: tuple[PullRequest, ...] = ()
        self.return_matching_pull_request = False
        self.return_closed_pull_request = False
        self.return_duplicate_pull_requests = False
        self.return_wrong_head_pull_request = False
        self.raise_auto_merge = False
        self.lookups: list[tuple[str, str, str]] = []
        self.auto_merge_requests: list[tuple[str, int]] = []
        self.auto_merge_credentials: list[GitHubCredential] = []

    def find_linked_pull_requests(
        self, *, repository: str, branch: str, marker: str
    ) -> tuple[PullRequest, ...]:
        self.lookups.append((repository, branch, marker))
        if self.return_matching_pull_request:
            return (PullRequest(42, "open", branch, f"Remediation\n{marker}"),)
        if self.return_closed_pull_request:
            return (PullRequest(42, "closed", branch, f"Remediation\n{marker}"),)
        if self.return_duplicate_pull_requests:
            return (
                PullRequest(42, "open", branch, f"Remediation\n{marker}"),
                PullRequest(43, "open", branch, f"Remediation\n{marker}"),
            )
        if self.return_wrong_head_pull_request:
            return (PullRequest(42, "open", "automation/wrong", f"Remediation\n{marker}"),)
        return self.pull_requests

    def request_auto_merge(
        self, *, repository: str, pull_request: int, credential: GitHubCredential
    ) -> None:
        self.auto_merge_requests.append((repository, pull_request))
        self.auto_merge_credentials.append(credential)
        if self.raise_auto_merge:
            raise OSError("response lost")


class RemediationTests(unittest.TestCase):
    def test_queued_job_launches_one_deterministic_workspace_from_fresh_origin_main(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(1, "issue-1", 1)
            paseo = FakePaseo()
            credential = GitHubCredential("shared-credential")
            service = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=paseo,
                github=FakeGitHub(),
                github_credential=credential,
            )

            context = IssueContext(
                f"Frontend error token={credential.value}",
                "Event text key=prompt-secret",
                (StackFrame("src/index.tsx", "render", 21, "throw error"),),
                (Breadcrumb("ui.click", "error", "Save failed"),),
            )
            result = service.dispatch(job.id, context)

            self.assertEqual(result.status, "working")
            self.assertEqual(paseo.origin_requests, 1)
            self.assertEqual(len(paseo.launches), 1)
            launch = paseo.launches[0]
            self.assertEqual(launch.base.reference, "origin/main")
            self.assertEqual(launch.base.commit_sha, "a" * 40)
            self.assertEqual(result.workspace, launch.workspace)
            self.assertEqual(result.agent_id, launch.agent_identity)
            self.assertEqual(result.branch, launch.branch)
            self.assertIn("a" * 12, launch.workspace)
            self.assertIn("a" * 12, launch.agent_identity)
            self.assertIn("a" * 12, launch.branch)
            self.assertEqual(paseo.credentials, [credential])
            self.assertIn("issue-related change", launch.prompt)
            self.assertIn("relevant tests", launch.prompt)
            self.assertIn("create a commit", launch.prompt)
            self.assertIn("exactly one linked pull request", launch.prompt)
            self.assertIn("GitHub auto-merge", launch.prompt)
            self.assertIn("src/index.tsx", launch.prompt)
            self.assertIn("Save failed", launch.prompt)
            self.assertNotIn("shared-credential", launch.prompt)
            self.assertNotIn("prompt-secret", launch.prompt)
            self.assertNotIn("shared-credential", repr(credential))
            store.close()

    def test_context_is_bounded_and_redacts_untrusted_event_data(self) -> None:
        detail = {
            "title": "Login\x00 failure token=title-secret path?debug=QUERY_FRAGMENT",
            "culprit": "/session?access_token=url-secret",
            "metadata": {"value": "metadata-secret"},
            "request": {
                "data": "REQUEST_BODY_SECRET",
                "cookies": "COOKIE_SECRET",
                "query_string": "QUERY_SECRET",
            },
        }
        frames = [
            {
                "filename": f"/app/{index}?token=frame-secret",
                "function": f"function_{index}",
                "lineno": index,
                "context_line": f"key=frame-secret-{index}\x1b[31m",
                "vars": {"password": "STACK_LOCAL_SECRET"},
            }
            for index in range(20)
        ]
        breadcrumbs = [
            {
                "category": "http",
                "level": "info",
                "message": f"GET /search?api_key=breadcrumb-secret-{index}",
                "data": {"cookies": "BREADCRUMB_SECRET"},
            }
            for index in range(20)
        ]
        event = {
            "message": "M" * 2_000 + " bearer event-secret",
            "request": detail["request"],
            "exception": {"values": [{"stacktrace": {"frames": frames}}]},
            "breadcrumbs": {"values": breadcrumbs},
        }

        context = build_issue_context(detail, event)
        rendered = render_issue_context(context)

        self.assertLessEqual(len(context.title), 500)
        self.assertLessEqual(len(context.message), 500)
        self.assertLessEqual(len(context.frames), 8)
        self.assertLessEqual(len(context.breadcrumbs), 12)
        self.assertNotIn("\x00", rendered)
        self.assertNotIn("\x1b", rendered)
        for forbidden in (
            "title-secret",
            "url-secret",
            "metadata-secret",
            "REQUEST_BODY_SECRET",
            "COOKIE_SECRET",
            "QUERY_SECRET",
            "QUERY_FRAGMENT",
            "STACK_LOCAL_SECRET",
            "frame-secret",
            "breadcrumb-secret",
            "BREADCRUMB_SECRET",
            "event-secret",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_successful_agent_records_one_linked_pull_request_and_requests_auto_merge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(2, "issue-2", 1)
            paseo = FakePaseo("complete")
            github = FakeGitHub()
            github.return_matching_pull_request = True
            credential = GitHubCredential("shared-credential")
            service = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=paseo,
                github=github,
                github_credential=credential,
            )

            result = service.dispatch(job.id, IssueContext("Backend error", "Event text", (), ()))

            self.assertEqual(result.status, "awaiting_merge")
            self.assertEqual(result.pull_request, 42)
            self.assertEqual(github.auto_merge_requests, [("scowalt/ignite-for-spotify-2", 42)])
            self.assertEqual(github.auto_merge_credentials, [credential])
            self.assertEqual(len(github.lookups), 1)
            self.assertEqual(len(paseo.launches), 1)
            store.close()

    def test_persisted_launch_intent_adopts_or_visibly_fails_an_unlaunched_agent(self) -> None:
        for outcome, expected_status in (("running", "working"), ("absent", "failed")):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / "state.db")
                job = store.queue_job(1, "issue-crash", 1)
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
                paseo.results[identity.agent_identity] = (
                    AgentResult(identity.agent_identity, "running", None)
                    if outcome == "running"
                    else None
                )

                reconciled = RemediationService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    paseo=paseo,
                    github=FakeGitHub(),
                    github_credential=GitHubCredential("shared-credential"),
                ).dispatch(job.id, IssueContext("Error", "Event text", (), ()))

                self.assertEqual(reconciled.status, expected_status)
                self.assertEqual(paseo.launches, [])
                if outcome == "absent":
                    self.assertIn("absent", reconciled.failure_reason or "")
                store.close()

    def test_lost_launch_response_keeps_the_job_adoptable_without_a_duplicate_agent_or_retry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(1, "issue-response-lost", 1)
            paseo = ResponseLostPaseo()
            service = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=paseo,
                github=FakeGitHub(),
                github_credential=GitHubCredential("shared-credential"),
            )
            context = IssueContext("Error", "Event text", (), ())

            adopted = service.dispatch(job.id, context)

            self.assertEqual(adopted.status, "working")
            self.assertIsNone(adopted.failure_reason)
            self.assertIsNotNone(adopted.launch_reference)
            self.assertIsNotNone(adopted.launch_commit_sha)
            self.assertIsNotNone(adopted.launch_marker)
            self.assertEqual(len(store.jobs()), 1)
            self.assertEqual(len(paseo.launches), 1)
            self.assertEqual(paseo.agent_requests, [adopted.agent_id])
            with self.assertRaisesRegex(StateError, "RETRY_REQUIRES_FAILED_JOB"):
                store.retry_job(job.id)

            reconciled = service.dispatch(job.id, context)

            self.assertEqual(reconciled.status, "working")
            self.assertEqual(len(store.jobs()), 1)
            self.assertEqual(len(paseo.launches), 1)
            self.assertEqual(paseo.agent_requests, [adopted.agent_id, adopted.agent_id])
            store.close()

    def test_lost_launch_and_unavailable_adoption_lookup_stays_non_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(1, "issue-response-lookup", 1)
            paseo = ResponseLostPaseo()
            paseo.raise_agent_lookup = True

            uncertain = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=paseo,
                github=FakeGitHub(),
                github_credential=GitHubCredential("shared-credential"),
            ).dispatch(job.id, IssueContext("Error", "Event text", (), ()))

            self.assertEqual(uncertain.status, "working")
            self.assertIsNone(uncertain.failure_reason)
            self.assertEqual(len(store.jobs()), 1)
            self.assertEqual(len(paseo.launches), 1)
            self.assertEqual(paseo.agent_requests, [uncertain.agent_id])
            store.close()

    def test_invalid_origin_agent_or_pull_request_identity_fails_visibly(self) -> None:
        scenarios = ("origin", "agent", "pull_request")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / "state.db")
                job = store.queue_job(1, f"issue-{scenario}", 1)
                paseo = FakePaseo("complete")
                github = FakeGitHub()
                github.return_matching_pull_request = scenario == "agent"
                github.return_wrong_head_pull_request = scenario == "pull_request"
                if scenario == "origin":
                    paseo.origin = OriginMain("origin/not-main", "a" * 40)
                if scenario == "agent":
                    paseo.launch_result_identity = "other-agent"
                result = RemediationService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    paseo=paseo,
                    github=github,
                    github_credential=GitHubCredential("shared-credential"),
                ).dispatch(job.id, IssueContext("Error", "Event text", (), ()))

                self.assertEqual(result.status, "failed")
                self.assertEqual(len(paseo.launches), 0 if scenario == "origin" else 1)
                expected_reason = {
                    "origin": "origin/main",
                    "agent": "identity",
                    "pull_request": "invalid",
                }[scenario]
                self.assertIn(expected_reason, result.failure_reason or "")
                store.close()

    def test_auto_merge_exception_keeps_the_exact_pull_request_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(2, "issue-auto-merge", 1)
            paseo = FakePaseo("complete")
            github = FakeGitHub()
            github.return_matching_pull_request = True
            github.raise_auto_merge = True
            service = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=paseo,
                github=github,
                github_credential=GitHubCredential("shared-credential"),
            )

            uncertain = service.dispatch(job.id, IssueContext("Error", "Event text", (), ()))

            self.assertEqual(uncertain.status, "awaiting_merge")
            self.assertEqual(uncertain.pull_request, 42)
            self.assertFalse(uncertain.auto_merge_requested)
            github.raise_auto_merge = False
            reconciled = service.dispatch(job.id, IssueContext("Error", "Event text", (), ()))
            self.assertEqual(reconciled.status, "awaiting_merge")
            self.assertTrue(reconciled.auto_merge_requested)
            self.assertEqual(github.auto_merge_requests, [("scowalt/ignite-for-spotify-2", 42)] * 2)
            self.assertEqual(len(paseo.launches), 1)
            store.close()

    def test_restart_adopts_recorded_workspace_branch_and_pull_request_without_launching(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            store = StateStore(database)
            job = store.queue_job(1, "issue-restart", 1)
            initial_paseo = FakePaseo("complete")
            github = FakeGitHub()
            github.return_matching_pull_request = True
            initial = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=initial_paseo,
                github=github,
                github_credential=GitHubCredential("shared-credential"),
            ).dispatch(job.id, IssueContext("Error", "Event text", (), ()))
            self.assertEqual(initial.status, "awaiting_merge")
            store.close()

            restarted_store = StateStore(database)
            restarted_paseo = FakePaseo()
            restarted = RemediationService(
                restarted_store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=restarted_paseo,
                github=FakeGitHub(),
                github_credential=GitHubCredential("shared-credential"),
            ).dispatch(job.id, IssueContext("Error", "Event text", (), ()))

            self.assertEqual(restarted, initial)
            self.assertEqual(restarted_paseo.origin_requests, 0)
            self.assertEqual(restarted_paseo.launches, [])
            restarted_store.close()

    def test_completed_agent_with_an_already_closed_linked_pr_preserves_it_for_lifecycle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(1, "issue-closed", 1)
            paseo = FakePaseo("complete")
            github = FakeGitHub()
            github.return_closed_pull_request = True

            awaiting_merge = RemediationService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                paseo=paseo,
                github=github,
                github_credential=GitHubCredential("shared-credential"),
            ).dispatch(job.id, IssueContext("Error", "Event text", (), ()))

            self.assertEqual(awaiting_merge.status, "awaiting_merge")
            self.assertEqual(awaiting_merge.pull_request, 42)
            self.assertFalse(awaiting_merge.auto_merge_requested)
            self.assertEqual(github.auto_merge_requests, [])
            self.assertEqual(len(paseo.launches), 1)
            store.close()

    def test_failed_agents_and_invalid_linked_pull_requests_fail_without_duplicate_launches(
        self,
    ) -> None:
        scenarios = (
            ("agent", "failed", "agent failed"),
            ("missing", "complete", "linked pull request is missing"),
            ("duplicate", "complete", "linked pull request is duplicated"),
        )
        for scenario, agent_status, expected_reason in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / "state.db")
                job = store.queue_job(1, f"issue-{scenario}", 1)
                paseo = FakePaseo(agent_status)
                github = FakeGitHub()
                github.return_duplicate_pull_requests = scenario == "duplicate"
                github.return_closed_pull_request = scenario == "closed"
                service = RemediationService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    paseo=paseo,
                    github=github,
                    github_credential=GitHubCredential("shared-credential"),
                )

                failed = service.dispatch(job.id, IssueContext("Error", "Event text", (), ()))
                adopted = service.dispatch(job.id, IssueContext("Error", "Event text", (), ()))

                self.assertEqual(failed.status, "failed")
                self.assertEqual(failed.failure_reason, expected_reason)
                self.assertEqual(adopted, failed)
                self.assertEqual(len(paseo.launches), 1)
                store.close()


if __name__ == "__main__":
    unittest.main()
