from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from glitchtip_paseo_controller.clients.paseo import OriginMain
from glitchtip_paseo_controller.state import StateError, StateStore


class StateStoreTests(unittest.TestCase):
    def test_jobs_keep_visible_state_resources_and_failure_reason_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            store = StateStore(path)
            job = store.queue_job(1, "issue-1", 1)
            self.assertEqual(job.status, "queued")
            self.assertIsNone(job.workspace)
            self.assertIsNone(job.failure_reason)

            store.start_job(job.id)
            store.record_resources(
                job.id,
                workspace="/worktrees/issue-1",
                agent_id="agent-1",
                branch="fix/issue-1",
                pull_request=17,
            )
            store.fail_job(job.id, "agent could not open pull request")
            failed = store.job(job.id)
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.workspace, "/worktrees/issue-1")
            self.assertEqual(failed.agent_id, "agent-1")
            self.assertEqual(failed.branch, "fix/issue-1")
            self.assertEqual(failed.pull_request, 17)
            self.assertEqual(failed.failure_reason, "agent could not open pull request")
            store.close()

            restarted = StateStore(path)
            self.assertEqual(restarted.job(job.id), failed)
            restarted.close()

    def test_explicit_retry_creates_one_linked_queued_job_without_retrying_automatically(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            first = store.queue_job(2, "issue-2", 1)
            store.fail_job(first.id, "CI failed")

            self.assertEqual([job.id for job in store.jobs()], [first.id])
            retry = store.retry_job(first.id)
            self.assertEqual(retry.status, "queued")
            self.assertEqual(retry.retry_of, first.id)
            self.assertEqual([job.id for job in store.jobs()], [first.id, retry.id])
            with self.assertRaisesRegex(StateError, "ACTIVE_JOB_EXISTS"):
                store.retry_job(first.id)
            store.close()

    def test_explicit_retry_rejects_failed_jobs_with_persisted_resources(self) -> None:
        scenarios = ("launch_intent", "agent", "pull_request", "lifecycle_checkpoint")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / "state.db")
                job = store.queue_job(2, f"issue-{scenario}", 1)
                store.start_job(job.id)
                if scenario == "launch_intent":
                    store.record_launch_intent(
                        job.id,
                        workspace="workspace",
                        agent_id="agent",
                        branch="branch",
                        base=OriginMain("origin/main", "a" * 40),
                        marker="marker",
                    )
                elif scenario == "agent":
                    store.record_resources(job.id, agent_id="agent")
                elif scenario == "pull_request":
                    store.record_resources(job.id, pull_request=42)
                else:
                    store.await_merge(job.id)
                    store.record_merge_observed(job.id)
                store.fail_job(job.id, "failed after resources existed")

                with self.assertRaisesRegex(
                    StateError,
                    "operator must resolve, clean, or adopt the existing resources first",
                ):
                    store.retry_job(job.id)

                self.assertEqual([stored.id for stored in store.jobs()], [job.id])
                store.close()

    def test_duplicate_jobs_and_corrupt_databases_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = StateStore(root / "state.db")
            store.queue_job(1, "issue-1", 1)
            with self.assertRaisesRegex(StateError, "JOB_EXISTS"):
                store.queue_job(1, "issue-1", 1)
            store.close()

            broken = root / "broken.db"
            broken.write_bytes(b"not sqlite")
            with self.assertRaisesRegex(StateError, "DATABASE"):
                StateStore(broken)

    def test_v2_jobs_gain_durable_lifecycle_checkpoints_without_losing_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE issues (
                  project_id INTEGER NOT NULL,
                  issue_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  first_seen TEXT NOT NULL,
                  activity TEXT NOT NULL,
                  PRIMARY KEY(project_id, issue_id)
                );
                CREATE TABLE jobs (
                  id INTEGER PRIMARY KEY,
                  project_id INTEGER NOT NULL,
                  issue_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  workspace TEXT,
                  agent_id TEXT,
                  branch TEXT,
                  pull_request INTEGER,
                  failure_reason TEXT,
                  retry_of INTEGER
                );
                INSERT INTO jobs(id, project_id, issue_id, generation, status)
                VALUES(1, 1, 'completed-issue', 1, 'complete');
                PRAGMA user_version=2;
                """
            )
            connection.close()

            store = StateStore(path)
            migrated = store.job(1)

            self.assertEqual(store.schema_version, 4)
            self.assertEqual(migrated.status, "complete")
            self.assertTrue(migrated.merge_observed)
            self.assertTrue(migrated.issue_resolved)
            self.assertTrue(migrated.agent_archived)
            self.assertTrue(migrated.workspace_removed)
            self.assertTrue(migrated.local_branch_removed)
            self.assertTrue(migrated.remote_branch_removed)
            self.assertIsNone(migrated.activation_activity)
            self.assertIsNone(migrated.launch_reference)
            self.assertFalse(migrated.auto_merge_requested)
            store.close()

    def test_single_process_lock_and_backup_are_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "state.db"
            store = StateStore(path)
            self.assertEqual(store.schema_version, 4)
            self.assertEqual(store.journal_mode, "wal")
            store.queue_job(1, "issue-1", 1)
            with self.assertRaisesRegex(StateError, "LOCKED"):
                StateStore(path)
            backup = store.backup(root / "backup.db")
            store.close()

            restored = StateStore(backup)
            self.assertEqual(restored.jobs()[0].issue_id, "issue-1")
            restored.close()


if __name__ == "__main__":
    unittest.main()
