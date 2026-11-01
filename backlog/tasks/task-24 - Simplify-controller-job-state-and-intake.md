---
id: TASK-24
title: Simplify controller job state and intake
status: Done
assignee:
  - '@myself'
created_date: '2026-07-23 22:07'
updated_date: '2026-07-23 22:20'
labels: []
dependencies:
  - TASK-22
  - TASK-23
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement simplified-plan U1: replace the transition/action ledger with one durable job record and preserve baseline/restart deduplication.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Controller retains one durable visible job per eligible issue activation without duplicate dispatch after restart
- [x] #2 Baseline, reactivation, failure, and explicit retry behavior follow the simplified requirements
- [x] #3 Legacy action/transition abstractions are removed or consolidated with focused regression coverage
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Characterize the existing U1/U2 state APIs and identify which behavior remains required by the simplified plan.
2. Replace the ledger with a compact job record and intake model while preserving restart deduplication.
3. Delete obsolete action/transition tests and add focused baseline, retry, failure, and restart coverage.
4. Run the controller suite and review the migration for data-loss and duplicate-job risks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Replaced the transition/action ledger with compact durable jobs and simple statuses.
- Preserved baseline/reactivation deduplication, single-process locking, explicit linked retry, restart visibility, backup, and fail-closed integrity behavior.
- Removed obsolete action code/tests and added focused CLI/state/intake coverage.
- Verified lock, Ruff, strict Pyright, full controller unit suite (30 tests), fixture report, and diff check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Simplified the controller foundation to a durable job model.

Changes:
- Replaced action/transition ledger machinery with compact SQLite jobs and visible lifecycle states.
- Retained durable GlitchTip baseline/reactivation intake, restart deduplication, explicit retry, and failure visibility.
- Added concise local status/list/retry CLI coverage and removed obsolete action code.

Tests:
- uv lock --check
- Ruff format/lint
- strict Pyright src
- controller unittest suite (30 tests)
<!-- SECTION:FINAL_SUMMARY:END -->
