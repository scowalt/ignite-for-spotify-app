---
id: TASK-44
title: Activate and verify migration-aware database delivery
status: To Do
assignee: []
created_date: '2026-11-03 15:53'
updated_date: '2026-11-04 15:43'
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
- [ ] #1 The owner approves a concrete one-time procedure identifying the exact signed release/operator versions, legacy schema-only validation, maintenance window, baseline/history transition, backup budgets, failure handling and stop conditions before production mutations.
- [ ] #2 Production adoption preserves existing business data, application/Hangfire database separation, physical paths/volumes/ownership, backup repository/credentials/retention, auxiliary services and sole-updater identity; unknown schema/history/configuration stops rather than being guessed or reset.
- [ ] #3 Fresh encrypted backup and isolated restore evidence is verified within existing budgets before the approved database transition; only bounded private schema/aggregate verification is exposed, never production records or credentials in CI, chat or public artifacts.
- [ ] #4 A successful signed main release exercises the explicitly approved history adoption or a legitimate non-destructive migration through the actual timer, with no per-release approval or manual deployment command, verified migration history and healthy application behavior; no throwaway production schema is added solely for testing.
- [ ] #5 Post-activation no-op polling, existing image-only delivery, migration failure/recovery behavior, alert visibility and ownership/cleanup are verified; no unsafe old-image rollback, automatic live restore, initialization, pruning or unrelated service change occurs.
- [ ] #6 Runbooks and task evidence explain eligible automatic migrations, expected downtime, strict journal compatibility, forward-fix/manual recovery after committed changes and retained boundaries for destructive/Hangfire/operator/infrastructure changes; no temporary publication hold or paused timer is left unresolved.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner approved a narrow metadata-only production inventory during development. It is complete and privately retained; no user rows, credentials, database writes, backups, downtime or updater changes occurred. This does NOT satisfy approval of the exact live adoption/upgrade procedure. The observed legacy schema differs from the initial source-derived fixture, so prepare an explicit production-compatible draft baseline/frozen fixture rather than guessing equivalence or weakening validation. Actual adoption remains unapproved and all acceptance criteria remain unchecked.

The separate image-only runtime security rollout completed successfully; metadata-only post-verification shows identical schema definitions and schema_version 22. No database adoption or operator upgrade happened. Production now runs main 5d0f565/runtime10.0.14 with the unchanged installed operator and contract. Exact migration activation approval remains outstanding.

TASK-43 offline implementation is complete: connected v2 updater/current-main code head 8d724cabdebc1735fdacf38d7c1b82e1cd4a8a36 passed full CI 41859648784, including actual native backup/restore, writer recovery, installer and image gates. The initial unactivated baseline now exactly matches the previously approved private schema inventory, with independent frozen fixtures; earlier mismatch notes are historical. Owner selected Finish first before merging, not permission for live adoption or updater activation.
Next requires fresh scoped read-only rollout preflight because production has received ordinary frontend-only releases since the last independent runtime inspection. Do not treat old 5d0f565 runtime evidence as current source. Gather only approved schema/history/runtime/policy/ledger/storage metadata privately, then present the exact one-time sequence for approval before changes. No live preflight or adoption has been performed here; all Task-44 AC remain unchecked.
<!-- SECTION:NOTES:END -->
