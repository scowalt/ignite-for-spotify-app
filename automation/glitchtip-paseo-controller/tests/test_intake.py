from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glitchtip_paseo_controller.clients.glitchtip import GlitchTipIssue, IssueListing
from glitchtip_paseo_controller.intake import IntakeService
from glitchtip_paseo_controller.state import StateError, StateStore


def issue(
    identifier: str,
    last_seen: str,
    status: str = "unresolved",
    *,
    first_seen: str | None = None,
) -> GlitchTipIssue:
    return GlitchTipIssue(
        identifier,
        status,
        identifier,
        "1",
        first_seen or last_seen,
        last_seen,
        "1",
        "project",
    )


def listing(*issues: GlitchTipIssue, complete: bool = True) -> IssueListing:
    return IssueListing(tuple(issues), (), (), complete)


class IntakeTests(unittest.TestCase):
    def test_preexisting_unresolved_issue_remains_baselined_even_with_a_later_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            store = StateStore(path)
            intake = IntakeService(store)
            intake.begin_baseline("2026-01-10T00:00:00Z")
            intake.scan(
                [
                    listing(
                        issue(
                            "old",
                            "2026-01-11T00:00:00Z",
                            first_seen="2026-01-01T00:00:00Z",
                        )
                    )
                ]
            )
            self.assertEqual(store.jobs(), ())
            store.close()

            restarted = StateStore(path)
            IntakeService(restarted).scan(
                [listing(issue("old", "2026-01-12T00:00:00Z", first_seen="2026-01-01T00:00:00Z"))]
            )
            self.assertEqual(restarted.jobs(), ())
            restarted.close()

    def test_post_baseline_issue_creates_exactly_one_queued_job_across_restart_and_polls(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            store = StateStore(path)
            intake = IntakeService(store)
            intake.begin_baseline("2026-01-10T00:00:00Z")
            first_observation = issue("new", "2026-01-11T00:00:00Z")
            intake.scan([listing(first_observation)])
            intake.scan([listing(first_observation)])
            self.assertEqual([(job.id, job.status) for job in store.jobs()], [(1, "queued")])
            store.close()

            restarted = StateStore(path)
            IntakeService(restarted).scan([listing(issue("new", "2026-01-12T00:00:00Z"))])
            self.assertEqual([(job.id, job.status) for job in restarted.jobs()], [(1, "queued")])
            restarted.close()

    def test_positive_resolution_followed_by_newer_unresolved_activity_creates_one_new_job(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            intake = IntakeService(store)
            intake.begin_baseline("2026-01-10T00:00:00Z")
            intake.scan([listing(issue("reactivated", "2026-01-11T00:00:00Z"))])
            intake.observe_detail(issue("reactivated", "2026-01-12T00:00:00Z", "resolved"))
            intake.scan([listing(issue("reactivated", "2026-01-13T00:00:00Z"))])
            intake.scan([listing(issue("reactivated", "2026-01-13T00:00:00Z"))])

            self.assertEqual(
                [(job.generation, job.status) for job in store.jobs()],
                [(1, "queued"), (2, "queued")],
            )
            store.close()

    def test_resolved_detail_with_equal_activity_is_persisted_for_later_reactivation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            intake = IntakeService(store)
            intake.begin_baseline("2026-01-10T00:00:00Z")
            intake.scan([listing(issue("reactivated", "2026-01-11T00:00:00Z"))])
            intake.observe_detail(issue("reactivated", "2026-01-11T00:00:00Z", "resolved"))
            intake.scan([listing(issue("reactivated", "2026-01-12T00:00:00Z"))])

            observed = store.issue(1, "reactivated")
            self.assertEqual(observed["status"] if observed else None, "unresolved")
            self.assertEqual(
                [(job.generation, job.status) for job in store.jobs()],
                [(1, "queued"), (2, "queued")],
            )
            store.close()

    def test_listing_absence_never_resolves_or_reactivates_an_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            intake = IntakeService(store)
            intake.begin_baseline("2026-01-10T00:00:00Z")
            intake.scan([listing(issue("new", "2026-01-11T00:00:00Z"))])
            job = store.jobs()[0]
            store.fail_job(job.id, "agent failed")
            intake.scan([listing()])
            intake.scan([listing(issue("new", "2026-01-12T00:00:00Z"))])

            self.assertEqual(store.issue(1, "new")["status"], "unresolved")
            self.assertEqual([(job.id, job.status) for job in store.jobs()], [(job.id, "failed")])
            store.close()

    def test_incomplete_listing_or_missing_baseline_fails_without_creating_a_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            intake = IntakeService(store)
            with self.assertRaisesRegex(StateError, "BASELINE_CUTOFF_REQUIRED"):
                intake.scan([listing(issue("new", "2026-01-11T00:00:00Z"))])
            intake.begin_baseline("2026-01-10T00:00:00Z")
            with self.assertRaisesRegex(StateError, "INCOMPLETE_SCAN"):
                intake.scan([listing(issue("new", "2026-01-11T00:00:00Z"), complete=False)])
            self.assertIsNone(store.issue(1, "new"))
            self.assertEqual(store.jobs(), ())
            store.close()


if __name__ == "__main__":
    unittest.main()
