from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glitchtip_paseo_controller.clients.github import PullRequestOutcome
from glitchtip_paseo_controller.clients.glitchtip import GlitchTipIssue
from glitchtip_paseo_controller.lifecycle import LifecycleService
from glitchtip_paseo_controller.state import Job, StateStore


class FakeGitHub:
    def __init__(self, outcome: PullRequestOutcome | None) -> None:
        self.outcome = outcome
        self.observations: list[tuple[str, int]] = []

    def observe_pull_request(
        self, *, repository: str, pull_request: int
    ) -> PullRequestOutcome | None:
        self.observations.append((repository, pull_request))
        return self.outcome


class FakeGlitchTip:
    def __init__(
        self,
        current_issue: GlitchTipIssue | None = None,
        resolution_issue: GlitchTipIssue | None = None,
    ) -> None:
        self.current = current_issue
        self.resolution = resolution_issue
        self.observations: list[tuple[int, str]] = []
        self.resolutions: list[tuple[int, str]] = []

    def current_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None:
        self.observations.append((project_id, issue_id))
        return self.current or _issue(project_id, issue_id, "2026-01-11T00:00:00Z")

    def resolve_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None:
        current = self.current or _issue(project_id, issue_id, "2026-01-11T00:00:00Z")
        resolved = self.resolution or _issue(
            project_id, issue_id, current.last_seen, status="resolved"
        )
        if (
            resolved.status == "resolved"
            and resolved.id == issue_id
            and resolved.project_id == str(project_id)
        ):
            self.resolutions.append((project_id, issue_id))
        return resolved


class FakePaseo:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str]] = []

    def archive_agent(self, agent_identity: str) -> None:
        self.actions.append(("archive", agent_identity))

    def remove_workspace(self, workspace: str) -> None:
        self.actions.append(("workspace", workspace))

    def remove_local_branch(self, branch: str) -> None:
        self.actions.append(("local_branch", branch))

    def remove_remote_branch(self, branch: str) -> None:
        self.actions.append(("remote_branch", branch))


class UnavailableGitHub(FakeGitHub):
    def observe_pull_request(
        self, *, repository: str, pull_request: int
    ) -> PullRequestOutcome | None:
        del repository, pull_request
        raise OSError("temporary network failure")


class InterruptingGlitchTip(FakeGlitchTip):
    def resolve_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None:
        del project_id, issue_id
        raise OSError("interrupted before resolution checkpoint")


class InterruptingPaseo(FakePaseo):
    def __init__(self, interrupted_action: str) -> None:
        super().__init__()
        self.interrupted_action = interrupted_action

    def archive_agent(self, agent_identity: str) -> None:
        self._record("archive", agent_identity)

    def remove_workspace(self, workspace: str) -> None:
        self._record("workspace", workspace)

    def remove_local_branch(self, branch: str) -> None:
        self._record("local_branch", branch)

    def remove_remote_branch(self, branch: str) -> None:
        self._record("remote_branch", branch)

    def _record(self, action: str, resource: str) -> None:
        if action == self.interrupted_action:
            raise OSError(f"interrupted before {action} checkpoint")
        self.actions.append((action, resource))


class LifecycleTests(unittest.TestCase):
    def test_confirmed_merged_pr_resolves_current_issue_and_cleans_registered_resources(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = _awaiting_merge_job(store)
            github = FakeGitHub(PullRequestOutcome(42, "merged"))
            glitchtip = FakeGlitchTip()
            paseo = FakePaseo()

            complete = LifecycleService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                github=github,
                glitchtip=glitchtip,
                paseo=paseo,
            ).reconcile(job.id)

            self.assertEqual(complete.status, "complete")
            self.assertTrue(complete.merge_observed)
            self.assertTrue(complete.issue_resolved)
            self.assertTrue(complete.agent_archived)
            self.assertTrue(complete.workspace_removed)
            self.assertTrue(complete.local_branch_removed)
            self.assertTrue(complete.remote_branch_removed)
            self.assertEqual(github.observations, [("scowalt/ignite-for-spotify-2", 42)])
            self.assertEqual(glitchtip.resolutions, [(2, "issue-2")])
            self.assertEqual(
                paseo.actions,
                [
                    ("archive", "agent-2"),
                    ("workspace", "/worktrees/issue-2"),
                    ("local_branch", "automation/issue-2"),
                    ("remote_branch", "automation/issue-2"),
                ],
            )
            self.assertEqual(store.jobs(), (complete,))
            store.close()

    def test_closed_or_ci_failed_pr_fails_without_resolution_or_cleanup(self) -> None:
        for state, reason in (
            ("closed", "linked pull request is closed"),
            ("ci_failed", "CI failed"),
        ):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / "state.db")
                job = _awaiting_merge_job(store)
                github = FakeGitHub(PullRequestOutcome(42, state))  # type: ignore[arg-type]
                glitchtip = FakeGlitchTip()
                paseo = FakePaseo()

                service = LifecycleService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    github=github,
                    glitchtip=glitchtip,
                    paseo=paseo,
                )
                failed = service.reconcile(job.id)

                self.assertEqual(failed.status, "failed")
                self.assertIn(reason, failed.failure_reason or "")
                self.assertEqual(failed.pull_request, 42)
                self.assertEqual(failed.workspace, "/worktrees/issue-2")
                self.assertFalse(failed.merge_observed)
                self.assertEqual(service.reconcile(job.id), failed)
                self.assertEqual(len(github.observations), 1)
                self.assertEqual(glitchtip.resolutions, [])
                self.assertEqual(paseo.actions, [])
                self.assertEqual(store.jobs(), (failed,))
                store.close()

    def test_unavailable_or_uncertain_pr_never_resolves_or_deletes_resources(self) -> None:
        outcomes = (
            FakeGitHub(None),
            FakeGitHub(PullRequestOutcome(42, "unknown")),
            UnavailableGitHub(None),
        )
        for github in outcomes:
            with (
                self.subTest(github=type(github).__name__),
                tempfile.TemporaryDirectory() as directory,
            ):
                store = StateStore(Path(directory) / "state.db")
                job = _awaiting_merge_job(store)
                glitchtip = FakeGlitchTip()
                paseo = FakePaseo()

                failed = LifecycleService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    github=github,
                    glitchtip=glitchtip,
                    paseo=paseo,
                ).reconcile(job.id)

                self.assertEqual(failed.status, "failed")
                self.assertIn("outcome", failed.failure_reason or "")
                self.assertEqual(glitchtip.resolutions, [])
                self.assertEqual(paseo.actions, [])
                store.close()

    def test_open_or_wrong_merged_pull_request_never_resolves_or_cleans(self) -> None:
        for outcome, expected_status in (
            (PullRequestOutcome(42, "open"), "awaiting_merge"),
            (PullRequestOutcome(43, "merged"), "failed"),
        ):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / "state.db")
                job = _awaiting_merge_job(store)
                glitchtip = FakeGlitchTip()
                paseo = FakePaseo()

                result = LifecycleService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    github=FakeGitHub(outcome),
                    glitchtip=glitchtip,
                    paseo=paseo,
                ).reconcile(job.id)

                self.assertEqual(result.status, expected_status)
                self.assertEqual(glitchtip.resolutions, [])
                self.assertEqual(paseo.actions, [])
                store.close()

    def test_same_unresolved_activation_with_later_activity_still_resolves_the_merged_job(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = _awaiting_merge_job(store)
            glitchtip = FakeGlitchTip(_issue(2, "issue-2", "2026-01-12T00:00:00Z"))
            paseo = FakePaseo()

            complete = LifecycleService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                github=FakeGitHub(PullRequestOutcome(42, "merged")),
                glitchtip=glitchtip,
                paseo=paseo,
            ).reconcile(job.id)

            self.assertEqual(complete.status, "complete")
            self.assertEqual(glitchtip.resolutions, [(2, "issue-2")])
            store.close()

    def test_resolution_checkpoint_persists_issue_and_later_listing_reactivates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            cutoff = "2026-01-10T00:00:00Z"
            store.set_baseline(cutoff)
            store.ingest_listing_observations(
                cutoff,
                ((2, "issue-2", "unresolved", "2026-01-11T00:00:00Z", "2026-01-11T00:00:00Z"),),
            )
            first = store.jobs()[0]
            store.start_job(first.id)
            store.record_resources(
                first.id,
                workspace="/worktrees/issue-2",
                agent_id="agent-2",
                branch="automation/issue-2",
                pull_request=42,
            )
            store.await_merge(first.id)

            complete = LifecycleService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                github=FakeGitHub(PullRequestOutcome(42, "merged")),
                glitchtip=FakeGlitchTip(),
                paseo=FakePaseo(),
            ).reconcile(first.id)

            resolved = store.issue(2, "issue-2")
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(complete.status, "complete")
            self.assertTrue(complete.issue_resolved)
            self.assertEqual(resolved["status"], "resolved")
            self.assertEqual(resolved["activity"], "2026-01-11T00:00:00Z")

            store.ingest_listing_observations(
                cutoff,
                ((2, "issue-2", "unresolved", "2026-01-11T00:00:00Z", "2026-01-12T00:00:00Z"),),
            )

            self.assertEqual(
                [(job.generation, job.status) for job in store.jobs()],
                [(1, "complete"), (2, "queued")],
            )
            store.close()

    def test_ambiguous_resolution_never_records_resolution_or_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = _awaiting_merge_job(store)
            glitchtip = FakeGlitchTip(
                _issue(2, "issue-2", "2026-01-12T00:00:00Z"),
                _issue(2, "other-issue", "2026-01-13T00:00:00Z", status="resolved"),
            )
            paseo = FakePaseo()

            failed = LifecycleService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                github=FakeGitHub(PullRequestOutcome(42, "merged")),
                glitchtip=glitchtip,
                paseo=paseo,
            ).reconcile(job.id)

            self.assertEqual(failed.status, "failed")
            self.assertIn("ambiguous", failed.failure_reason or "")
            self.assertEqual(glitchtip.resolutions, [])
            self.assertEqual(paseo.actions, [])
            store.close()

    def test_merged_older_generation_fails_without_resolving_a_reactivated_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            store.set_baseline("2026-01-10T00:00:00Z")
            store.ingest_listing_observations(
                "2026-01-10T00:00:00Z",
                ((2, "issue-2", "unresolved", "2026-01-11T00:00:00Z", "2026-01-11T00:00:00Z"),),
            )
            first = store.jobs()[0]
            store.start_job(first.id)
            store.record_resources(
                first.id,
                workspace="/worktrees/issue-2",
                agent_id="agent-2",
                branch="automation/issue-2",
                pull_request=42,
            )
            store.await_merge(first.id)
            store.observe_detail(
                "2026-01-10T00:00:00Z",
                2,
                "issue-2",
                "resolved",
                "2026-01-11T00:00:00Z",
                "2026-01-12T00:00:00Z",
            )
            store.ingest_listing_observations(
                "2026-01-10T00:00:00Z",
                ((2, "issue-2", "unresolved", "2026-01-11T00:00:00Z", "2026-01-13T00:00:00Z"),),
            )
            glitchtip = FakeGlitchTip(_issue(2, "issue-2", "2026-01-13T00:00:00Z"))
            paseo = FakePaseo()

            stale = LifecycleService(
                store,
                repository="scowalt/ignite-for-spotify-2",
                github=FakeGitHub(PullRequestOutcome(42, "merged")),
                glitchtip=glitchtip,
                paseo=paseo,
            ).reconcile(first.id)

            self.assertEqual(stale.status, "failed")
            self.assertIn("activation", stale.failure_reason or "")
            self.assertEqual(
                [(job.generation, job.status) for job in store.jobs()],
                [(1, "failed"), (2, "queued")],
            )
            self.assertEqual(glitchtip.resolutions, [])
            self.assertEqual(paseo.actions, [])
            store.close()

    def test_restart_resumes_each_post_merge_checkpoint_without_a_new_job(self) -> None:
        interruptions = (
            ("archive", FakeGlitchTip(), InterruptingPaseo("archive")),
            ("workspace", FakeGlitchTip(), InterruptingPaseo("workspace")),
            ("local_branch", FakeGlitchTip(), InterruptingPaseo("local_branch")),
            ("remote_branch", FakeGlitchTip(), InterruptingPaseo("remote_branch")),
        )
        for stage, initial_glitchtip, initial_paseo in interruptions:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                database = Path(directory) / "state.db"
                store = StateStore(database)
                job = _awaiting_merge_job(store)
                stalled = LifecycleService(
                    store,
                    repository="scowalt/ignite-for-spotify-2",
                    github=FakeGitHub(PullRequestOutcome(42, "merged")),
                    glitchtip=initial_glitchtip,
                    paseo=initial_paseo,
                ).reconcile(job.id)
                self.assertEqual(stalled.status, "awaiting_merge")
                self.assertTrue(stalled.merge_observed)
                store.close()

                restarted_store = StateStore(database)
                restarted_github = FakeGitHub(None)
                restarted_glitchtip = FakeGlitchTip()
                restarted_paseo = FakePaseo()
                complete = LifecycleService(
                    restarted_store,
                    repository="scowalt/ignite-for-spotify-2",
                    github=restarted_github,
                    glitchtip=restarted_glitchtip,
                    paseo=restarted_paseo,
                ).reconcile(job.id)

                self.assertEqual(complete.status, "complete")
                self.assertEqual(len(restarted_store.jobs()), 1)
                self.assertEqual(restarted_github.observations, [])
                self.assertEqual(restarted_glitchtip.resolutions, [])
                expected_actions = {
                    "archive": ["archive", "workspace", "local_branch", "remote_branch"],
                    "workspace": ["workspace", "local_branch", "remote_branch"],
                    "local_branch": ["local_branch", "remote_branch"],
                    "remote_branch": ["remote_branch"],
                }[stage]
                self.assertEqual(
                    [action for action, _ in restarted_paseo.actions], expected_actions
                )
                restarted_store.close()


def _issue(
    project_id: int, issue_id: str, activity: str, *, status: str = "unresolved"
) -> GlitchTipIssue:
    return GlitchTipIssue(
        issue_id,
        status,
        "Issue",
        "1",
        "2026-01-11T00:00:00Z",
        activity,
        str(project_id),
        "project",
    )


def _awaiting_merge_job(store: StateStore) -> Job:
    job = store.queue_job(2, "issue-2", 1, activation_activity="2026-01-11T00:00:00Z")
    store.start_job(job.id)
    store.record_resources(
        job.id,
        workspace="/worktrees/issue-2",
        agent_id="agent-2",
        branch="automation/issue-2",
        pull_request=42,
    )
    return store.await_merge(job.id)


if __name__ == "__main__":
    unittest.main()
