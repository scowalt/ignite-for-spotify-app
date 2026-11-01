---
id: TASK-25
title: Launch coding agents with auto-merge PRs
status: Done
assignee:
  - '@myself'
created_date: '2026-07-23 22:07'
updated_date: '2026-07-23 22:33'
labels: []
dependencies:
  - TASK-24
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement simplified-plan U2: run one Paseo coding agent with bounded context and shared non-bypass GitHub credential to create an auto-merge PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each queued job creates or adopts one named workspace, branch, and linked PR
- [x] #2 Agent context is bounded/redacted and the accepted PR has GitHub auto-merge requested
- [x] #3 Agent and PR failures remain visible without duplicate workspace creation
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect installed Paseo command behavior and current controller clients to define the smallest restart-adoptable workspace/PR seam.
2. Add bounded issue context and remediation tests before implementation.
3. Implement deterministic agent launch, branch/PR adoption, and auto-merge request using the shared non-bypass credential.
4. Verify controller tests and failure paths without running live external effects.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented deterministic coding-agent launch/adoption, bounded redacted issue context, linked PR validation, and auto-merge request seams using injected clients. Verified 35 controller tests plus Ruff, strict Pyright, lock, fixture report, and diff check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented simplified remediation publication.

Changes:
- Added bounded/redacted issue context and deterministic Paseo workspace/agent launch.
- Added linked PR adoption/validation and GitHub auto-merge request support.
- Preserved restart adoption and visible failure behavior without duplicate workspaces.

Tests: full controller suite (35 tests), Ruff, strict Pyright, and lock validation.
<!-- SECTION:FINAL_SUMMARY:END -->
