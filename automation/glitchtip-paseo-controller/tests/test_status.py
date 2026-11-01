from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glitchtip_paseo_controller.state import StateStore
from glitchtip_paseo_controller.status import render_job, render_status


class StatusTests(unittest.TestCase):
    def test_status_keeps_failed_reason_and_registered_resource_identifiers_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.db")
            job = store.queue_job(2, "issue-2", 1)
            store.start_job(job.id)
            store.record_resources(
                job.id,
                workspace="/worktrees/issue-2",
                agent_id="agent-2",
                branch="automation/issue-2",
                pull_request=42,
            )
            failed = store.fail_job(job.id, "linked pull request CI failed")

            self.assertEqual(
                render_job(failed),
                "job=1 issue=2/issue-2 generation=1 state=failed "
                "reason=linked pull request CI failed workspace=/worktrees/issue-2 "
                "agent=agent-2 branch=automation/issue-2 pr=42 "
                "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                "retry_of=-",
            )
            self.assertEqual(
                render_status((failed,)),
                "jobs=1 failed=1\n"
                "job=1 issue=2/issue-2 generation=1 state=failed "
                "reason=linked pull request CI failed workspace=/worktrees/issue-2 "
                "agent=agent-2 branch=automation/issue-2 pr=42 "
                "progress=merge:-,resolve:-,archive:-,workspace:-,local-branch:-,remote-branch:- "
                "retry_of=-\n",
            )
            store.close()


if __name__ == "__main__":
    unittest.main()
