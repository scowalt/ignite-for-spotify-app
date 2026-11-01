---
id: TASK-27
title: Automate guarded cutover operations
status: Done
assignee:
  - '@myself'
created_date: '2026-07-23 22:07'
updated_date: '2026-07-23 23:19'
labels: []
dependencies:
  - TASK-24
  - TASK-26
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement simplified-plan U4: guarded legacy cleanup, local service, CI, and operations documentation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Only exactly identified legacy artifacts may be deleted and remote failure blocks local deletion
- [x] #2 Controller is locally operable through a fenced service with documented observe/enable/pause/status flows
- [x] #3 CI and documentation reflect the simple CI-only auto-merge model
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Build test-first exact-marker/allowlist legacy inventory and guarded deletion behavior.
2. Add local systemd configuration, CI job, tool pinning, and operations guidance for the simplified controller.
3. Verify deletion safety, observe mode, and secret-safe service configuration with controller tests and review.
4. Do not run destructive legacy cleanup or install the service during implementation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented guarded legacy cleanup, local observe service, controller CI, and operations runbooks. Verified 50 controller tests, Ruff, strict Pyright, lock, systemd unit, and diff checks. No live cleanup, service action, or credential use occurred.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented guarded cutover operations: exact-evidence legacy cleanup with explicit dry-run/apply confirmation, local observe-mode service, CI, and `prd` operations guidance. Verified with 50 controller tests and static/service validation; live cutover remains an operator action.
<!-- SECTION:FINAL_SUMMARY:END -->
