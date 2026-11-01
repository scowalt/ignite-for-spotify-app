---
id: TASK-22
title: 'U6: Perform manual legacy shutdown and cleanup'
status: Done
assignee:
  - '@myself'
created_date: '2026-07-23 20:08'
updated_date: '2026-07-25 11:52'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Use an operator-reviewed runbook to freeze the legacy remediator, clean exact PRs and refs across four repositories, remove exact local artifacts, and verify no recurrence without adding destructive controller code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Saved inventory identifies each remote and local artifact through class-appropriate exact evidence
- [x] #2 All verified remote PRs and refs are cleaned before exact local service, state, session, payload, checkout, and worktree artifacts
- [x] #3 Replacement dispatch stays disabled until the manual verification record is complete
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Record the exact legacy service identity and current state.
2. Stop and disable the operator-approved legacy service.
3. Verify it is inactive and disabled before preparing the guarded cleanup inventory.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Operator-approved legacy shutdown performed at 2026-07-24T16:17:55-04:00.
- `glitchtip-auto-remediator.service` is disabled and no longer running. systemd records exit status 143 from the requested stop, so its unit state is `failed` rather than `inactive`; this does not restart it.
- No PR, branch, workspace, or local artifact cleanup has been performed.

- Prepared an exact local manifest and registrations for the 10 verified `scowalt/ignite-for-spotify-2` legacy PR/worktree pairs.
- Guarded dry run succeeded at 2026-07-24: `eligible=10`, `skipped=0`, `ready=yes`.
- Saved confirmation token: `DELETE-LEGACY-CLEANUP-34465bbc4cd92352`.
- Apply has not been run; no legacy PR, branch, workspace, registration, or other artifact has been removed.

- Apply completed at 2026-07-24 with `failed=0`, `complete=yes`, and `cutover_enabled=yes`. Evidence: `~/.local/state/ignite-glitchtip-paseo-controller/cutover-20260724171513/`.
- Post-apply verification found zero matching open legacy PRs and zero configured Ignite worktrees. The legacy service remains disabled with MainPID 0.
- TASK-22 remains in progress: the legacy service unit/source checkout and any other class-specific local artifacts have not been removed by the bounded controller cleanup.

- Installed the replacement user-level observe gate from a clean `~/src/ignite-for-spotify-2` checkout after cutover.
- A local systemd PATH override supplies the already-installed `doppler`, `uv`, and `paseo` executables without changing the committed unit.
- The latest unit run exited 0 after a live compatibility report; it is an enabled `Type=oneshot` service, so `inactive (dead)` after successful completion is expected. Dispatch is still disabled.

- Paused the replacement dispatch timer and service before final local cleanup and saved a healthy zero-job SQLite backup at `~/.local/state/ignite-glitchtip-paseo-controller/state.db.backup-20260725115009`.
- Reconfirmed the saved remote cutover evidence reports `failed=0`, `complete=yes`, and `cutover_enabled=yes`; the legacy checkout was clean and the disabled legacy service had no running process.
- Removed only the approved legacy unit, source checkout, runtime state, and shared session/worktree paths. After `daemon-reload`, the unit is `not-found` and inactive, all four paths are absent, and the replacement database still passes `PRAGMA integrity_check` with zero jobs.
- Replacement dispatch remains disabled and inactive for deliberate resumption under TASK-23.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed the manual legacy remediator shutdown and cleanup.

Changes:
- Preserved the successful ten-PR remote cutover record and backed up the healthy replacement controller state.
- Removed the exact legacy user service, clean source checkout, runtime state, payload/log archive, Pi sessions, and worktree directories.
- Reloaded user systemd and left replacement dispatch paused for TASK-23.

Verification:
- Legacy unit: `not-found`, inactive, no PID.
- Legacy paths: all four approved targets absent.
- Replacement state: `PRAGMA integrity_check` is `ok`, zero jobs, cutover evidence intact.
<!-- SECTION:FINAL_SUMMARY:END -->
