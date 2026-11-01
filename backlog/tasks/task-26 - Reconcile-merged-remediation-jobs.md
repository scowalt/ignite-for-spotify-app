---
id: TASK-26
title: Reconcile merged remediation jobs
status: Done
assignee:
  - '@myself'
created_date: '2026-07-23 22:07'
updated_date: '2026-07-23 22:57'
labels: []
dependencies:
  - TASK-24
  - TASK-25
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement simplified-plan U3: observe PR state, resolve GlitchTip only after confirmed merge, and clean up registered resources.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Confirmed merged PR resolves only its current GlitchTip issue and archives/cleans registered work
- [x] #2 Failed, closed, or uncertain PRs remain unresolved and inspectable without automatic retry
- [x] #3 Restart safely adopts post-merge progress without a new job
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Define typed PR observation and resource cleanup seams using only stored job identifiers.
2. Add red lifecycle/status tests for merged, failed, uncertain, and restarted jobs.
3. Implement reconciliation that resolves GlitchTip only after confirmed merge and otherwise preserves evidence.
4. Run controller verification and self-review cleanup idempotency.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented idempotent post-merge reconciliation with durable checkpoints, failed/uncertain PR preservation, GlitchTip resolution only after confirmed merge, and registered-resource cleanup. Verified 41 controller tests plus strict Pyright, Ruff, lock, and diff checks.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented CI-only auto-merge outcome reconciliation: confirmed merged PRs resolve GlitchTip and clean registered resources; failed or uncertain PRs stay visible and unresolved. Added restart-safe lifecycle and status coverage (41 controller tests).
<!-- SECTION:FINAL_SUMMARY:END -->
