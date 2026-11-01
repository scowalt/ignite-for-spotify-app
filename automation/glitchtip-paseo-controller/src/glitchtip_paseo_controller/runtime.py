from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from .clients.github import GitHubCredential, GitHubLifecycleClient, GitHubRemediationClient
from .clients.glitchtip import GlitchTipIssue, GlitchTipLifecycleClient, IssueListing
from .clients.paseo import PaseoLifecycleClient, PaseoRemediationClient
from .config import ControllerConfig
from .context import IssueContext, build_issue_context
from .intake import IntakeService
from .lifecycle import LifecycleService
from .remediation import RemediationService
from .runtime_clients import RuntimeClientError
from .state import Job, StateError, StateStore


class DispatchGlitchTipClient(GlitchTipLifecycleClient, Protocol):
    def list_unresolved(self, project_id: int) -> IssueListing: ...

    def issue_context_data(
        self, *, project_id: int, issue_id: str
    ) -> tuple[GlitchTipIssue, Mapping[str, object]]: ...

    def latest_event(self, *, issue_id: str) -> Mapping[str, object]: ...


class DispatchGitHubClient(GitHubLifecycleClient, GitHubRemediationClient, Protocol):
    pass


class DispatchPaseoClient(PaseoLifecycleClient, PaseoRemediationClient, Protocol):
    pass


@dataclass(frozen=True)
class TickResult:
    baseline_created: bool
    reconciled: int
    launched_job: int | None
    jobs: tuple[Job, ...]

    def render(self) -> str:
        launched = "-" if self.launched_job is None else str(self.launched_job)
        return (
            f"dispatch baseline={'created' if self.baseline_created else 'existing'} "
            f"reconciled={self.reconciled} launched={launched} jobs={len(self.jobs)}"
        )


class DispatchRuntime:
    def __init__(
        self,
        config: ControllerConfig,
        store: StateStore,
        *,
        glitchtip: DispatchGlitchTipClient,
        github: DispatchGitHubClient,
        paseo: DispatchPaseoClient,
        github_credential: GitHubCredential,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._glitchtip = glitchtip
        self._github = github
        self._paseo = paseo
        self._credential = github_credential
        self._now = now or _utc_now

    def close(self) -> None:
        self._store.close()

    def tick(self) -> TickResult:
        intake = IntakeService(self._store)
        baseline_cutoff = self._store.baseline_cutoff() or self._now()
        listings = tuple(
            self._glitchtip.list_unresolved(project_id)
            for project_id in self._config.glitchtip.project_ids
        )
        if not all(listing.complete for listing in listings):
            raise StateError("INCOMPLETE_SCAN")
        baseline_created = self._store.baseline_cutoff() is None
        if baseline_created:
            intake.begin_baseline(baseline_cutoff)
        self._observe_absent_known_issues(intake, listings)
        intake.scan(listings)

        lifecycle = LifecycleService(
            self._store,
            repository=self._config.github.repository,
            github=self._github,
            glitchtip=self._glitchtip,
            paseo=self._paseo,
        )
        remediation = RemediationService(
            self._store,
            repository=self._config.github.repository,
            paseo=self._paseo,
            github=self._github,
            github_credential=self._credential,
        )

        reconciled = 0
        for job in self._store.jobs():
            if job.status == "awaiting_merge":
                reconciled += self._reconcile_awaiting_merge(remediation, lifecycle, job)
            elif job.status == "working":
                resumed = self._resume_working(remediation, job)
                reconciled += 1
                if resumed.status == "awaiting_merge":
                    reconciled += self._reconcile_awaiting_merge(remediation, lifecycle, resumed)

        launched_job: int | None = None
        queued = next((job for job in self._store.jobs() if job.status == "queued"), None)
        if queued is not None:
            dispatched = self._dispatch_one(remediation, queued)
            launched_job = queued.id
            if dispatched.status == "awaiting_merge":
                reconciled += self._reconcile_awaiting_merge(remediation, lifecycle, dispatched)

        return TickResult(baseline_created, reconciled, launched_job, self._store.jobs())

    @staticmethod
    def _reconcile_awaiting_merge(
        remediation: RemediationService,
        lifecycle: LifecycleService,
        job: Job,
    ) -> int:
        if job.pull_request is not None and not job.auto_merge_requested:
            job = remediation.resume_auto_merge(job.id)
        if job.status != "awaiting_merge":
            return 0
        lifecycle.reconcile(job.id)
        return 1

    def _observe_absent_known_issues(
        self, intake: IntakeService, listings: tuple[IssueListing, ...]
    ) -> None:
        listed = {
            (int(issue.project_id), issue.id) for listing in listings for issue in listing.issues
        }
        for row in self._store.issues():
            project_id = int(row["project_id"])
            issue_id = str(row["issue_id"])
            if str(row["status"]) == "unresolved" and (project_id, issue_id) not in listed:
                issue = self._glitchtip.current_issue(project_id=project_id, issue_id=issue_id)
                if issue is not None:
                    intake.observe_detail(issue)

    @staticmethod
    def _resume_working(remediation: RemediationService, job: Job) -> Job:
        return remediation.resume_working(job.id)

    def _dispatch_one(self, remediation: RemediationService, job: Job) -> Job:
        context = self._context(job)
        if context is None:
            return self._store.job(job.id)
        return remediation.dispatch(job.id, context)

    def _context(self, job: Job) -> IssueContext | None:
        try:
            _, detail = self._glitchtip.issue_context_data(
                project_id=job.project_id, issue_id=job.issue_id
            )
            event = self._glitchtip.latest_event(issue_id=job.issue_id)
            return build_issue_context(detail, event)
        except RuntimeClientError as error:
            self._fail_if_active(job.id, f"issue context retrieval failed: {error.code}")
            return None
        except Exception:
            self._fail_if_active(job.id, "issue context retrieval failed")
            return None

    def _fail_if_active(self, job_id: int, reason: str) -> None:
        try:
            current = self._store.job(job_id)
            if current.status in {"queued", "working", "awaiting_merge"}:
                self._store.fail_job(job_id, reason)
        except StateError:
            raise


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
