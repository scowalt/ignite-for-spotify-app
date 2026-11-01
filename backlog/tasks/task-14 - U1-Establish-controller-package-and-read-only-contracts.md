---
id: TASK-14
title: 'U1: Establish controller package and read-only contracts'
status: Done
assignee:
  - '@myself'
created_date: '2026-07-22 21:10'
updated_date: '2026-07-22 21:53'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement U1 from docs/plans/2026-07-22-001-feat-glitchtip-paseo-remediation-plan.md: isolated Python package, typed adapters, fixtures, configuration validation, and non-mutating contract reporting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Fixture suite and configuration validation produce deterministic read-only compatibility reports
- [x] #2 Adapters preserve GlitchTip pagination, GitHub policy/check evidence, and Paseo capability metadata
- [x] #3 Child environment construction excludes ambient credentials and dispatch remains disabled on incompatibility
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect project and installed-tool conventions plus the existing GlitchTip helper.
2. Add the Python 3.12/uv package, validated config, read-only adapters, and CLI report.
3. Build captured contract fixtures and tests, including pagination/evidence preservation and child-environment isolation.
4. Run the package test suite and self-review against U1 verification.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Implemented the isolated Python 3.12/uv controller package with fixture and GET-only live compatibility reports.
- Added strict typed GlitchTip/GitHub/Paseo/Pi contract parsing, pagination/completeness guards, environment isolation, and no-redirect bearer transport.
- Verified package checks: uv lock --check; Ruff format/lint; strict Pyright on src; 20 unittest cases; fixture CLI report; git diff --check.
- Live GlitchTip probing remains unavailable in this checkout because Doppler has no configured prod context; the current interactive GitHub token cannot read check runs. U8 is the release-blocking authenticated/disposable capability preflight.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented the U1 controller contract harness.

Changes:
- Added a locked Python 3.12 package with strict static configuration, deterministic fixture reports, and a GET-only live-report path.
- Added typed GlitchTip, GitHub, Paseo, and Pi evidence adapters with exact-head, pagination, policy, and capability guards.
- Isolated child HOME/XDG/Git state, excluded ambient credentials, and refused redirect-based bearer-token forwarding.

Tests:
- uv lock --check
- uv run --python 3.12 ruff format --check .
- uv run --python 3.12 ruff check .
- uv run --python 3.12 pyright src
- uv run --python 3.12 python -m unittest discover -s tests -v (20 tests)

Live authenticated checks are intentionally deferred to U8; this checkout lacks a configured Doppler prod context and the interactive GitHub token cannot read check runs.
<!-- SECTION:FINAL_SUMMARY:END -->
