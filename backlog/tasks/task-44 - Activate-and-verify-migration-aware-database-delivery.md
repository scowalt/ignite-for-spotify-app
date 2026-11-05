---
id: TASK-44
title: Activate and verify migration-aware database delivery
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-03 15:53'
updated_date: '2026-11-05 04:14'
labels:
  - deployment
  - database
  - operations
dependencies:
  - TASK-43
references:
  - scripts/install-deployer.py
  - scripts/ignite-deploy.py
documentation:
  - docs/operations/guarded-continuous-delivery.md
  - docs/operations/sqlite-backup-recovery.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After offline migration/protocol verification, prepare and obtain approval for a bounded one-time production adoption and updater upgrade. Then establish routine automatic delivery for eligible database changes without adding a production approval click to normal releases. This task is not itself authorization to access private records, stop services, alter the live database, upgrade the operator or restore data.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The owner approves a concrete one-time procedure identifying the exact signed release/operator versions, legacy schema-only validation, maintenance window, baseline/history transition, backup budgets, failure handling and stop conditions before production mutations.
- [x] #2 Production adoption preserves existing business data, application/Hangfire database separation, physical paths/volumes/ownership, backup repository/credentials/retention, auxiliary services and sole-updater identity; unknown schema/history/configuration stops rather than being guessed or reset.
- [x] #3 Fresh encrypted backup and isolated restore evidence is verified within existing budgets before the approved database transition; only bounded private schema/aggregate verification is exposed, never production records or credentials in CI, chat or public artifacts.
- [x] #4 A successful signed main release exercises the explicitly approved history adoption or a legitimate non-destructive migration through the actual timer, with no per-release approval or manual deployment command, verified migration history and healthy application behavior; no throwaway production schema is added solely for testing.
- [ ] #5 Post-activation no-op polling, existing image-only delivery, migration failure/recovery behavior, alert visibility and ownership/cleanup are verified; no unsafe old-image rollback, automatic live restore, initialization, pruning or unrelated service change occurs.
- [x] #6 Runbooks and task evidence explain eligible automatic migrations, expected downtime, strict journal compatibility, forward-fix/manual recovery after committed changes and retained boundaries for destructive/Hangfire/operator/infrastructure changes; no temporary publication hold or paused timer is left unresolved.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Under the owner-approved read-only scope, inspect current deployed image/source, ledger/policy/operator/unit identities, mounts/writers, disk headroom and SQLite schema/history metadata. Keep raw evidence private; stop on active deployment, unexpected identities or changing snapshots. No user-row query, credential disclosure, backup, SQL write/recovery, service change, upgrade or merge.
2. Compare the private inventory with the reviewed exact baseline and tested application/host/engine/Hangfire contracts; identify blockers without guessing equivalence.
3. Present an exact bounded operator/ledger/adoption/merge sequence with maintenance, backup, verification and failure conditions. Pause for separate approval before any production mutation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner approved a narrow metadata-only production inventory during development. It is complete and privately retained; no user rows, credentials, database writes, backups, downtime or updater changes occurred. This does NOT satisfy approval of the exact live adoption/upgrade procedure. The observed legacy schema differs from the initial source-derived fixture, so prepare an explicit production-compatible draft baseline/frozen fixture rather than guessing equivalence or weakening validation. Actual adoption remains unapproved and all acceptance criteria remain unchecked.

The separate image-only runtime security rollout completed successfully; metadata-only post-verification shows identical schema definitions and schema_version 22. No database adoption or operator upgrade happened. Production now runs main 5d0f565/runtime10.0.14 with the unchanged installed operator and contract. Exact migration activation approval remains outstanding.

TASK-43 offline implementation is complete: connected v2 updater/current-main code head 8d724cabdebc1735fdacf38d7c1b82e1cd4a8a36 passed full CI 41859648784, including actual native backup/restore, writer recovery, installer and image gates. The initial unactivated baseline now exactly matches the previously approved private schema inventory, with independent frozen fixtures; earlier mismatch notes are historical. Owner selected Finish first before merging, not permission for live adoption or updater activation.
Next requires fresh scoped read-only rollout preflight because production has received ordinary frontend-only releases since the last independent runtime inspection. Do not treat old 5d0f565 runtime evidence as current source. Gather only approved schema/history/runtime/policy/ledger/storage metadata privately, then present the exact one-time sequence for approval before changes. No live preflight or adoption has been performed here; all Task-44 AC remain unchecked.

Owner approved fresh read-only production preflight in the Preflight question. Approval permits only the metadata inspection scope above; it does not authorize migration, backup, service/operator/state changes, merge or live rollout. Beginning private evidence collection.

Approved read-only preflight completed privately at 2026-11-04 16:03 UTC. Production source is fe21dc7928bcdd50257c40847ef07737c60362ef, order [70,1], runtime 10.0.14; operator remains 7b1953e and configuration checkout 4ef6b03. Ledger/policy/runtime/configuration stayed stable, no pending transaction/failed fence/owned scratch or tools, all app images healthy, timer enabled/active and service successful.
Exact legacy schema fingerprint still matches 91520ea3d23a8c812dea171d9bf5194e5f896069b3b540ffbab723e7b2ffa6a5; all known column shapes match, no unexpected objects or migration journal, WAL/schema_version 22. Logical size 71,942,144 bytes; data/workspace filesystem free space 13.43 GiB. Only backend/backup consume the data volume. Existing API dependency metadata confirms the reviewed Hangfire identity. Two probes stopped before SQL on an optional Docker Volumes field; a read-only-template correction resolved it. No production write/backup/service/operator/merge action occurred.
Prepared a private proposed rollout plan bound to tested head/operator 9b6574bc9871a78fb08b38e7f8832f1ad9cbec7a and its exact tree/contracts/catalogue. It proposes a temporary owned-timer/publishing fence, protected merge and authenticated artifact capture, explicit preserving ledger/policy/operator transition, fresh stopped-state backup/isolated restore and actual-timer baseline adoption, then no-op/same-catalogue verification and restoration of temporary controls. Reserve a 40-minute maintenance window; committed/uncertain failure can require longer forward-fix downtime. The plan is NOT approved; all Task-44 AC remain unchecked. Raw evidence stays private.

Owner explicitly approved the linked exact one-time rollout, then requested continuation. Proceed only under its reviewed source/tree/operator/pins, temporary owned timer/publishing fence, preserving state upgrade, fresh verified recovery and actual-timer adoption. Rehearse the transition locally before live writes and stop on any changed identity or failed gate.

Approved rollout began after exact read-only revalidation. The immutable 9b6574b operator bundle was staged without selecting it; local cross-file transition rehearsal passed success, interruption/resume and refusal cases. Paused only the enabled owned timer while its service was idle; application services and old ledger/policy/operator stayed unchanged. PR #22 merged through native protection with explicit expectedHeadOid and Gmail author as df13eb6acb60816ac833252117e0d597afe7866f; merge tree exactly equals tested tree 17cc201f96892bc81ce2446fb7a947e7cacc1968 and protection readback is unchanged. Awaiting normal main publication before operator/database changes. Timer pause remains intentionally active; publishing not fenced yet.

Rollout stopped safely at backup_started for signed df13eb6/order [78,1], artifact c731b6de7e296ab03cbfebc911ca49f709c3d5b52032498f8e4ebeaf3f91d87b. The timer reached manual_recovery with no verified recovery receipt; child migration outcome was blocked, not committed. A real native local fixture reproduced cold-WAL read-only-mount inspection failure. Private production diagnostics proved all known writers stopped, WAL/SHM/rollback-journal files absent, exact approved legacy schema/inode/ownership retained, quick_check OK and no migration journal. An immutable read-only URI was used only for this proved-quiescent, sidecar-free diagnostic; no user rows were exposed or data restored.
Used the approved single compatible prior-service fallback: restarted only the exact original backend and backup containers once, after durable private recovery intent and independent compatibility proof. Both are healthy again; frontend/Caddy/Alloy/Watchtower identities and all mounts remain preserved. No journal adoption occurred. The ledger was NOT reset/edited to clear recovery: it remains schema 2/manual_recovery, active prior fe21dc7/order [70,1], high-water [78,1], failed artifact fenced. Operator 9b6574b/policy v2 remain installed.
INTENTIONAL HOLDS: owned timer paused but enabled; PRODUCTION_PUBLISHING_ENABLED=false. No owned tooling/scratch remains. Need a regression-tested cold-WAL fix and separately reviewed new operator/policy/failed-attempt resolution before any retry. Do not replay the approved 9b rollout, delete history/fences, invoke once or force old-image rollback again. AC2–6 remain unchecked; activation is not complete.

2026-11-05: owner-approved revised e3b6bd2 recovery completed the first successful live adoption. Fresh read-only checks and a locally rehearsed interruption-safe helper proved the original services already healthy, archived original metadata, recorded explicit manual resolution and closed only the held pointer without another restart. Active/high-water/failed fences and blocked sidecar were preserved. PR #27 merged as 2fb52ca with exact tested tree; controlled CI 41963026186 passed all gates and authenticated a new signed artifact/order [88,1]. After reviewed contract/operator selection and read-only check, the actual timer verified a fresh encrypted snapshot and isolated exact restore, then adopted one baseline entry and committed healthy images. Independent metadata/readiness checks confirm original application schema, inode/UID/mounts, backup identity and auxiliaries unchanged; no rollback or live restore. Publishing remains temporarily fenced pending the next real no-op tick; same-catalogue follow-up and final handover remain.

Independent no-op proof: the next real timer invocation completed successfully with outcome unchanged, identical ledger bytes and all six container IDs/start times unchanged. The existing unit journal exposes the historical manual_recovery outcome followed by deployed and unchanged; no production failure injection or new notification route was used. Public homepage and backend/frontend readiness returned HTTP 200. Restored PRODUCTION_PUBLISHING_ENABLED=true; timer remains enabled/active. Runbooks now describe active v2 eligibility, downtime, strict history, forward-fix policy and retained failed evidence. Preparing the approved legitimate documentation-only same-catalogue release; AC5 remains open until that automatic delivery is independently verified.
<!-- SECTION:NOTES:END -->
