---
id: TASK-43
title: Make guarded releases and recovery aware of database migrations
status: To Do
assignee: []
created_date: '2026-11-03 15:51'
labels:
  - deployment
  - database
dependencies:
  - TASK-42
references:
  - scripts/release_record.py
  - scripts/deployment_transaction.py
  - scripts/deployment_runtime.py
documentation:
  - docs/operations/guarded-continuous-delivery.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Integrate the journaled SQLite foundation into the signed-release and guarded-updater protocol so eligible database migrations can accompany normal green main releases without recurring production approvals. Preserve the current image-only path until a separately reviewed activation; do not remove contract checks without replacement evidence.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Signed release metadata binds the exact backend image and immutable migration catalogue to a versioned migration protocol; compatible catalogue additions no longer require manually repinning the entire startup-file fingerprint, while unrelated operating-contract changes remain guarded.
- [ ] #2 Migration releases serialize deployment, prepare before downtime, quiesce the old backend and all its HTTP/background writers, verify a fresh encrypted backup and isolated restore of the stopped state, then migrate before requests or background jobs are accepted.
- [ ] #3 Durable recovery distinguishes unchanged or rolled-back migration history from committed or uncertain schema changes; prior-image rollback is permitted only with verified compatibility, and incompatible/unknown states stop safely rather than restoring live data, repeating migrations blindly or launching an incompatible old image.
- [ ] #4 The first automatic policy supports reviewed backward-compatible bounded migrations; destructive changes, unbounded backfills, provider-managed Hangfire schema changes and operator/infrastructure changes are not implicitly authorized. A declaration alone is not treated as proof of compatibility.
- [ ] #5 Real SQLite/container and process-kill fixtures verify migration failure, commit-before-health-failure, restart/concurrency, backup budgets/cleanup and preservation of data/mount/auxiliary identities; existing signing, CI, replay/failure fences and secret boundaries remain enforced.
- [ ] #6 Production remains on the existing reviewed path until an explicit adoption/upgrade procedure is approved; no automatic operator upgrade, ledger reset, database initialization, restoration, pruning or credential change is introduced.
<!-- AC:END -->
