from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from glitchtip_paseo_controller.cli import main
from glitchtip_paseo_controller.state import StateStore


class LocalJobCliTests(unittest.TestCase):
    def test_status_list_and_retry_are_concise_and_expose_job_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            store = StateStore(database)
            queued = store.queue_job(1, "queued-issue", 1)
            failed = store.queue_job(2, "failed-issue", 1)
            store.start_job(failed.id)
            store.record_resources(
                failed.id,
                workspace="/worktrees/failed-issue",
                agent_id="agent-2",
                branch="fix/failed-issue",
                pull_request=42,
            )
            store.fail_job(failed.id, "pull request creation failed")
            retryable = store.queue_job(3, "retryable-issue", 1)
            store.fail_job(retryable.id, "origin/main fetch failed")
            store.close()

            status = self._run("status", "--database", str(database))
            self.assertEqual(
                status,
                "\n".join(
                    (
                        "jobs=3 queued=1 failed=2",
                        "job=1 issue=1/queued-issue generation=1 state=queued reason=- "
                        "workspace=- agent=- branch=- pr=- "
                        "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                        "retry_of=-",
                        "job=2 issue=2/failed-issue generation=1 state=failed "
                        "reason=pull request creation failed workspace=/worktrees/failed-issue "
                        "agent=agent-2 branch=fix/failed-issue pr=42 "
                        "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                        "retry_of=-",
                        "job=3 issue=3/retryable-issue generation=1 state=failed "
                        "reason=origin/main fetch failed workspace=- agent=- branch=- pr=- "
                        "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                        "retry_of=-",
                        "",
                    )
                ),
            )

            listing = self._run("list", "--database", str(database))
            self.assertEqual(
                listing,
                "\n".join(
                    (
                        "job=1 issue=1/queued-issue generation=1 state=queued reason=- "
                        "workspace=- agent=- branch=- pr=- "
                        "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                        "retry_of=-",
                        "job=2 issue=2/failed-issue generation=1 state=failed "
                        "reason=pull request creation failed workspace=/worktrees/failed-issue "
                        "agent=agent-2 branch=fix/failed-issue pr=42 "
                        "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                        "retry_of=-",
                        "job=3 issue=3/retryable-issue generation=1 state=failed "
                        "reason=origin/main fetch failed workspace=- agent=- branch=- pr=- "
                        "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                        "retry_of=-",
                        "",
                    )
                ),
            )

            rejected = io.StringIO()
            with redirect_stdout(rejected):
                rejected_exit = main(["retry", "--database", str(database), "2"])
            self.assertEqual(rejected_exit, 2)
            self.assertIn(
                "operator must resolve, clean, or adopt the existing resources first",
                rejected.getvalue(),
            )

            retried = self._run("retry", "--database", str(database), "3")
            self.assertEqual(retried, "queued job=4 retry_of=3\n")
            self.assertTrue(
                self._run("status", "--database", str(database)).startswith(
                    "jobs=4 queued=2 failed=2\n"
                )
            )
            self.assertEqual(queued.id, 1)

    @staticmethod
    def _run(*argv: str) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(argv)
        if exit_code != 0:
            raise AssertionError(f"expected success, got {exit_code}: {output.getvalue()}")
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
