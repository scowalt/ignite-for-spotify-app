---
id: TASK-23
title: 'U9: Enable dispatch and observe initial operation'
status: Done
assignee:
  - '@myself'
created_date: '2026-07-23 20:08'
updated_date: '2026-08-16 16:31'
labels: []
dependencies:
  - TASK-22
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After the synthetic proof and completed manual legacy cleanup, explicitly enable the persisted dispatch gate and monitor conservative production operation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Enablement verifies preflight, baseline, proof, credentials, cleanup record, health, and no legacy recurrence
- [x] #2 Initial jobs preserve one-attempt deduplication, exact-SHA gates, controller-owned merge and resolution, and visible blocking
- [x] #3 Any duplicate, stale poll, persistence failure, credential leak, unexplained merge or resolution, or legacy recurrence pauses dispatch
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add the smallest production adapters for GlitchTip, GitHub, and Paseo, using the one shared GitHub credential directly in the Paseo agent environment so the agent can push and open its PR.
2. Add one durable controller tick and a `dispatch --once --enable-dispatch` CLI command: baseline first, poll projects, create one job per activation, resume/reconcile existing work, and dispatch at most one queued job.
3. Keep GitHub auto-merge as the only merge gate; after GitHub reports the linked PR merged, resolve GlitchTip with its normal update endpoint and clean the registered active resources.
4. Add a dispatch systemd service and one-minute timer that are disabled by default; retain the successful observe gate separately.
5. Add fake-client integration tests and run a synthetic proof only after code review. Real dispatch stays disabled during development.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Implemented the dispatch runtime and its disabled-by-default timer/service templates without enabling them.
- Final review fixes cover baseline timing, reactivation persistence, merged-PR recovery, dispatch recovery, Paseo/systemd compatibility, and explicit retry rejection when existing active resources could otherwise duplicate work.
- Development verification passed: 94 controller tests, Ruff, strict Pyright, lock, systemd, and diff checks. No live dispatch or synthetic proof has been run.

- PR #158 and the Python-runtime hotfix PR #160 merged to main.
- Updated the clean controller checkout, recreated the dedicated controller workspace clone, and passed fixture plus live observe preflight.
- Ran one explicit dispatch tick at 2026-07-25 after setting the ignored local policy to enabled; it established the durable baseline with `jobs=0` and launched no agent.
- The dispatch timer/service remain inactive and uninstalled; no real remediation has run.

- Operator explicitly enabled the dispatch timer at 2026-07-25. The user unit uses the dedicated clean checkout, controller workspace root, Paseo home/host, and local PATH override.
- The first two timer-driven ticks exited successfully with `baseline=existing`, `reconciled=0`, `launched=-`, and `jobs=0`.
- No remediation agent or PR has been launched yet. The timer remains enabled; monitor `journalctl --user -u ignite-glitchtip-paseo-controller-dispatch.service` and durable job status for the first real activation.

- Dispatch was deliberately paused after healthy zero-job ticks so TASK-22 could complete final local legacy cleanup. The timer and service remain disabled and inactive; resume them explicitly as the next TASK-23 operation.

- Completed the live production proof on 2026-08-16 with dispatch paused whenever a controller defect appeared. Initial fetch and launch failures remained visible as failed jobs; fixes #204-#206 restored live Paseo compatibility, authenticated exact-origin/main fetches, and explicit Pi-provider launches.
- Explicit retries preserved one-attempt deduplication: jobs 3 and 4 link to failed jobs 1 and 2. Each successful agent started from the persisted exact origin/main SHA, opened one linked PR (#207 and #208), and used GitHub auto-merge. The controller observed both merges before resolving GlitchTip issues 483 and 489.
- Cleanup failures also stayed visible and paused dispatch. Fixes #209 and #210 moved workspace cleanup to the Git worktree registry and made GitHub-auto-deleted branch cleanup idempotent. Both agents are archived, both remote branches are absent, all remediation worktrees/local branches are now absent, and the durable failed records remain preserved as evidence.
- A final resume check found the monotonic timer could become active-but-elapsed when re-enabled during the same boot. Fix #211 replaced it with a persistent minutely calendar schedule. The merged unit was installed locally, daemon-reloaded, enabled, restarted, and observed across repeated successful ticks with baseline=existing, reconciled=0, launched=-, jobs=4.
- Final gates: live compatibility report passed; Paseo daemon/CLI 0.3.1 is healthy with the configured model available; database integrity is ok; cutover evidence still reports failed=0, complete=yes, cutover_enabled=yes; the legacy service is not-found/inactive; dispatch credentials were not found in the service journal, durable database, or Paseo daemon log. The dispatch timer is enabled, active (waiting), and has a scheduled next tick.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Enabled and proved the production GlitchTip-to-Paseo dispatch controller.

- Two genuine issue activations were deduplicated, launched from exact origin/main SHAs, fixed by archived Paseo agents, merged through required GitHub checks/auto-merge, and resolved only after merge confirmation.
- Production-only compatibility, launch, cleanup, and timer-resume defects were fixed through merged PRs #204-#211; every failure remained visible and dispatch stayed paused during remediation.
- Verified no active remediation jobs or leftover remediation worktrees/branches, intact cutover evidence, no legacy recurrence, healthy durable state, and no credential leakage in inspected controller/Paseo evidence.
- Dispatch is now enabled and running from the persistent minutely user timer; repeated post-install ticks completed successfully.
<!-- SECTION:FINAL_SUMMARY:END -->
