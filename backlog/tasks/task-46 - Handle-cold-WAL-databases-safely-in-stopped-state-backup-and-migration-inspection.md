---
id: TASK-46
title: >-
  Handle cold WAL databases safely in stopped-state backup and migration
  inspection
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-04 22:01'
updated_date: '2026-11-04 22:47'
labels:
  - database
  - deployment
  - bug
dependencies: []
references:
  - scripts/deployment_backup.py
  - scripts/migration_tool.py
  - backend/src/Ignite.Infrastructure/Data/DatabaseMigrations.fs
documentation:
  - docs/operations/database-migrations.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Production migration-aware activation reached backup_started but stopped before journal adoption: after backend shutdown, a WAL-mode SQLite database without WAL/SHM files could not be opened through a filesystem-read-only mount. The native container fixture reproduced this; a proved-quiescent sidecar-free immutable read-only diagnostic confirmed the intact legacy database. Original services were restored once under the approved fallback; deployment and publishing are intentionally paused. Fix the offline code and fixtures, then prepare a separate reviewed recovery/upgrade procedure rather than replaying or resetting the held transaction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Real native fixtures cover a checkpointed cold WAL database after all writers stop, with fresh encrypted snapshot/isolated restore and schema/history inspection succeeding without weakening budgets or data isolation.
- [ ] #2 Live or uncheckpointed WAL and hot rollback-journal cases are not bypassed with unconditional immutable reads; recovery proves writer shutdown and preserves committed data.
- [ ] #3 Read-only preflight, production startup and all existing migration failure/commit/concurrency/secret/identity gates remain enforced, with regression tests that fail on the observed cold-WAL case.
- [ ] #4 A separately reviewed exact operator/policy and held-attempt recovery plan preserves active/high-water/failed fences and audits the already completed one-time prior-service restart; no live retry, ledger reset, data restore or second blind rollback is performed during development.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the live publishing/timer fences and held state; work offline from current main. Use the already approved native SQLite/container/backup/recovery seams and the recorded cold-WAL red reproducer.
2. Add an explicit stopped-database inspection operation and stopped-source backup mode. Immutable reads are eligible only after caller-proven quiescence and verified absence of every SQLite sidecar; normal live reads and recovery guards remain unchanged.
3. Add native cold-WAL, live/uncheckpointed-WAL and hot-journal fixtures, including actual encrypted snapshot/restore and combined updater/runtime paths, then run full existing tests/security/CI.
4. Prepare a separately reviewed exact operator/policy and audited held-attempt resolution/retry plan that preserves active/high-water/failed fences and the already-used fallback. No production changes, reset or retry during this task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Confirmed the recorded production failure with a native cold-WAL fixture, then added explicit inspect-stopped and quiesced-source backup modes. Immutable reads are selected only with caller-proven quiescence and no WAL/SHM/rollback-journal entries; sidecars retain the normal SQLite read path and symlinked sidecars are refused. Generic inspect/startup/online backup remain unchanged. SQLite primary documentation confirms the read-only WAL requirement and warns that immutable bypasses locking/change detection.
Native green evidence now includes unchanged main-file/no-new-sidecar inspection, actual encrypted cold-WAL snapshot and exact restore, committed uncheckpointed WAL retained while a read-only reader holds an older snapshot, and a joined cold-WAL backup → inspection → adoption → real API health path. Hot-journal inspect-stopped remains rejected until explicit recovery. Runtime/controller call sites now distinguish stopped inspection from live verification, and the stopped entry point refuses active writers. No production changes were made.

Full local verification: 190 backend tests pass with no skips. Python suite: 171 run, 170 executed successfully with real backend/writer/backup/Cosign fixtures, one pre-existing source-map CLI fixture deferred to its hosted job. Six actual backup tests pass, including cold WAL and retained uncheckpointed WAL; the joined backup/restore/adoption/health fixture passes. Hot-journal and sidecar-alias guards, caller quiescence, read-only mounts and source checksums are covered. Backend image security/secret/notice gates pass unchanged after tagging the local image in the verifier’s required namespace. Actionlint, formatting/diff checks and 344-file comment scan pass. Preparing draft fix/CI and an exact revised recovery proposal; production remains untouched.
<!-- SECTION:NOTES:END -->
