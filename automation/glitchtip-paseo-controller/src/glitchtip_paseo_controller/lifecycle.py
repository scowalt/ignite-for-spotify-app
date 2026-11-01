from __future__ import annotations

from .clients.github import GitHubLifecycleClient
from .clients.glitchtip import GlitchTipIssue, GlitchTipLifecycleClient
from .clients.paseo import PaseoLifecycleClient
from .runtime_clients import RuntimeClientError
from .state import Job, StateStore


class LifecycleService:
    def __init__(
        self,
        store: StateStore,
        *,
        repository: str,
        github: GitHubLifecycleClient,
        glitchtip: GlitchTipLifecycleClient,
        paseo: PaseoLifecycleClient,
    ) -> None:
        self._store = store
        self._repository = repository
        self._github = github
        self._glitchtip = glitchtip
        self._paseo = paseo

    def reconcile(self, job_id: int) -> Job:
        job = self._store.job(job_id)
        if job.status != "awaiting_merge":
            return job
        if not job.merge_observed:
            job = self._observe_merge(job)
        if job.status != "awaiting_merge" or not job.merge_observed:
            return job
        return self._resume_completion(job)

    def _observe_merge(self, job: Job) -> Job:
        if job.pull_request is None:
            return self._fail(job, "stored pull request is missing")
        try:
            outcome = self._github.observe_pull_request(
                repository=self._repository, pull_request=job.pull_request
            )
        except RuntimeClientError as error:
            return self._fail(job, f"stored pull request outcome failed: {error.code}")
        except Exception:
            return self._fail(job, "stored pull request outcome is unavailable")
        if outcome is None:
            return self._fail(job, "stored pull request outcome is unavailable")
        if outcome.number != job.pull_request:
            return self._fail(job, "stored pull request identity mismatch")
        if outcome.state == "merged":
            return self._store.record_merge_observed(job.id)
        if outcome.state == "closed":
            return self._fail(job, "linked pull request is closed")
        if outcome.state == "ci_failed":
            return self._fail(job, "linked pull request CI failed")
        if outcome.state == "unknown":
            return self._fail(job, "stored pull request outcome is uncertain")
        return job

    def _resume_completion(self, job: Job) -> Job:
        if not job.issue_resolved:
            job = self._resolve_current_activation(job)
            if job.status != "awaiting_merge" or not job.issue_resolved:
                return job
        job = self._cleanup_agent(job)
        if not job.agent_archived:
            return job
        job = self._cleanup_workspace(job)
        if not job.workspace_removed:
            return job
        job = self._cleanup_local_branch(job)
        if not job.local_branch_removed:
            return job
        job = self._cleanup_remote_branch(job)
        if not job.remote_branch_removed:
            return job
        return self._store.complete_job(job.id)

    def _resolve_current_activation(self, job: Job) -> Job:
        try:
            current = self._glitchtip.current_issue(
                project_id=job.project_id, issue_id=job.issue_id
            )
        except RuntimeClientError as error:
            return self._fail(job, f"current issue observation failed: {error.code}")
        except Exception:
            return self._fail(job, "current issue observation is unavailable")
        if current is None or not self._is_current_unresolved_issue(job, current):
            return self._fail(job, "current issue observation is ambiguous")
        if not self._store.activation_is_current(job.id):
            return self._fail(job, "stored job activation is no longer current")
        try:
            resolved = self._glitchtip.resolve_issue(
                project_id=job.project_id,
                issue_id=job.issue_id,
            )
        except RuntimeClientError as error:
            return self._fail(job, f"issue resolution failed: {error.code}")
        except Exception:
            return self._fail(job, "issue resolution failed")
        if not self._proves_resolution(current, resolved):
            return self._fail(job, "issue resolution is ambiguous")
        assert resolved is not None
        return self._store.record_issue_resolved(
            job.id,
            first_seen=resolved.first_seen,
            activity=resolved.last_seen,
        )

    @staticmethod
    def _is_current_unresolved_issue(job: Job, issue: GlitchTipIssue | None) -> bool:
        return (
            issue is not None
            and issue.id == job.issue_id
            and issue.project_id == str(job.project_id)
            and issue.status == "unresolved"
            and bool(issue.last_seen)
        )

    @staticmethod
    def _proves_resolution(current: GlitchTipIssue, resolved: GlitchTipIssue | None) -> bool:
        if resolved is None:
            return False
        return (
            resolved.id == current.id
            and resolved.project_id == current.project_id
            and resolved.first_seen == current.first_seen
            and resolved.status == "resolved"
        )

    def _cleanup_agent(self, job: Job) -> Job:
        if job.agent_archived:
            return job
        if job.agent_id is not None:
            try:
                self._paseo.archive_agent(job.agent_id)
            except RuntimeClientError as error:
                return self._fail(job, f"agent archive failed: {error.code}")
            except Exception:
                return self._store.job(job.id)
        return self._store.record_agent_archived(job.id)

    def _cleanup_workspace(self, job: Job) -> Job:
        if job.workspace_removed:
            return job
        if job.workspace is not None:
            try:
                self._paseo.remove_workspace(job.workspace)
            except RuntimeClientError as error:
                return self._fail(job, f"workspace cleanup failed: {error.code}")
            except Exception:
                return self._store.job(job.id)
        return self._store.record_workspace_removed(job.id)

    def _cleanup_local_branch(self, job: Job) -> Job:
        if job.local_branch_removed:
            return job
        if job.branch is not None:
            try:
                self._paseo.remove_local_branch(job.branch)
            except RuntimeClientError as error:
                return self._fail(job, f"local branch cleanup failed: {error.code}")
            except Exception:
                return self._store.job(job.id)
        return self._store.record_local_branch_removed(job.id)

    def _cleanup_remote_branch(self, job: Job) -> Job:
        if job.remote_branch_removed:
            return job
        if job.branch is not None:
            try:
                self._paseo.remove_remote_branch(job.branch)
            except RuntimeClientError as error:
                return self._fail(job, f"remote branch cleanup failed: {error.code}")
            except Exception:
                return self._store.job(job.id)
        return self._store.record_remote_branch_removed(job.id)

    def _fail(self, job: Job, reason: str) -> Job:
        current = self._store.job(job.id)
        if current.status == "awaiting_merge":
            return self._store.fail_job(current.id, reason)
        return current
