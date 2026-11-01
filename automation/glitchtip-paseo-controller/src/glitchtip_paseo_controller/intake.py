from __future__ import annotations

from collections.abc import Sequence

from .clients.glitchtip import GlitchTipIssue, IssueListing
from .state import StateError, StateStore


class IntakeService:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def begin_baseline(self, cutoff: str) -> None:
        self.store.set_baseline(cutoff)

    def scan(self, listings: Sequence[IssueListing]) -> None:
        if not all(listing.complete for listing in listings):
            raise StateError("INCOMPLETE_SCAN")
        cutoff = self.store.baseline_cutoff()
        if cutoff is None:
            raise StateError("BASELINE_CUTOFF_REQUIRED")
        observed: dict[tuple[int, str], GlitchTipIssue] = {}
        for listing in listings:
            for issue in listing.issues:
                if issue.status != "unresolved":
                    raise StateError("LISTING_NOT_UNRESOLVED")
                key = (int(issue.project_id), issue.id)
                previous = observed.get(key)
                if previous is None or issue.last_seen > previous.last_seen:
                    observed[key] = issue
        self.store.ingest_listing_observations(
            cutoff,
            tuple(
                (project_id, issue_id, issue.status, issue.first_seen, issue.last_seen)
                for (project_id, issue_id), issue in observed.items()
            ),
        )

    def observe_detail(self, issue: GlitchTipIssue) -> None:
        cutoff = self.store.baseline_cutoff()
        if cutoff is None:
            raise StateError("BASELINE_CUTOFF_REQUIRED")
        self.store.observe_detail(
            cutoff,
            int(issue.project_id),
            issue.id,
            issue.status,
            issue.first_seen,
            issue.last_seen,
        )
