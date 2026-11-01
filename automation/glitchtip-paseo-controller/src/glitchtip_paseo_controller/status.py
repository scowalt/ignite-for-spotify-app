from __future__ import annotations

from collections.abc import Sequence

from .state import Job

_JOB_STATES = ("queued", "working", "awaiting_merge", "failed", "complete")


def render_status(jobs: Sequence[Job]) -> str:
    counts = {state: sum(job.status == state for job in jobs) for state in _JOB_STATES}
    summary = " ".join(f"{state}={count}" for state, count in counts.items() if count)
    lines = [f"jobs={len(jobs)}" if not summary else f"jobs={len(jobs)} {summary}"]
    lines.extend(render_job(job) for job in jobs)
    return "\n".join(lines) + "\n"


def render_jobs(jobs: Sequence[Job]) -> str:
    if not jobs:
        return "jobs=0\n"
    return "\n".join(render_job(job) for job in jobs) + "\n"


def render_job(job: Job) -> str:
    progress = ",".join(
        (
            f"merge:{_mark(job.merge_observed)}",
            f"resolve:{_mark(job.issue_resolved)}",
            f"archive:{_mark(job.agent_archived)}",
            f"workspace:{_mark(job.workspace_removed)}",
            f"local-branch:{_mark(job.local_branch_removed)}",
            f"remote-branch:{_mark(job.remote_branch_removed)}",
        )
    )
    return " ".join(
        (
            f"job={job.id}",
            f"issue={job.project_id}/{job.issue_id}",
            f"generation={job.generation}",
            f"state={job.status}",
            f"reason={_display(job.failure_reason)}",
            f"workspace={_display(job.workspace)}",
            f"agent={_display(job.agent_id)}",
            f"branch={_display(job.branch)}",
            f"pr={_display(job.pull_request)}",
            f"progress={progress}",
            f"retry_of={_display(job.retry_of)}",
        )
    )


def _display(value: str | int | None) -> str:
    return "-" if value is None else str(value)


def _mark(value: bool) -> str:
    return "yes" if value else "-"
