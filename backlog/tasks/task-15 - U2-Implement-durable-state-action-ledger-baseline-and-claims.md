---
id: TASK-15
title: 'U2: Implement durable state, action ledger, baseline, and claims'
status: Done
assignee:
  - '@myself'
created_date: '2026-07-22 21:10'
updated_date: '2026-07-22 22:08'
labels: []
dependencies:
  - TASK-14
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement U2 from the approved remediation plan: SQLite lifecycle/action ledger, fenced ownership, baseline intake, eligibility, and restart-safe reconciliation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Atomic state transitions, projections, actions, and ownership fencing preserve lifecycle invariants
- [x] #2 Baseline and reactivation rules create exactly one eligible attempt and retain capacity-limited work
- [x] #3 Fault, integrity, concurrency, and restart coverage prevents duplicate attempts or unsafe replay
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Define SQLite migrations, ownership fencing, immutable transitions, materialized projections, action contracts, and integrity/backup seams.
2. Write red tests for baseline cutoff, claims, reactivation, action recovery, concurrent ownership, restart adoption, and projection rebuilding.
3. Implement the durable state/action foundation and GlitchTip polling intake against U1 typed adapters.
4. Run the controller suite and self-review duplicate-prevention, failure-closed, and restart invariants.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Added a stdlib SQLite lifecycle store with WAL/FULL/FK pragmas, migrations, fenced ownership, immutable transitions, projection verification, backups, and read-only status.
- Added typed action intent/recovery contracts plus atomic cutoff baseline/intake/claim processing with monotonic issue watermarks.
- Added concurrency, crash/recovery, omission, stale-listing, restart, projection-mismatch, and duplicate-prevention coverage.
- Verified uv lock; Ruff; strict Pyright src; complete unittest suite (31 tests); and git diff --check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented U2's durable lifecycle and intake foundation.

Changes:
- Added transactional SQLite state, append-only transitions/actions, owner fencing, integrity rebuilds, backups, and status queries.
- Added deterministic baseline/claim/reactivation intake with complete-scan atomicity and terminal parked-attempt semantics.
- Added action recovery contracts that distinguish safe replay, authoritative adoption, and parked ambiguous outcomes.

Tests:
- uv lock --check
- uv run --python 3.12 ruff format --check .
- uv run --python 3.12 ruff check .
- uv run --python 3.12 pyright src
- uv run --python 3.12 python -m unittest discover -s tests -v (31 tests)
<!-- SECTION:FINAL_SUMMARY:END -->
