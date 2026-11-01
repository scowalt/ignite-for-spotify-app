---
id: TASK-29
title: Fix staging controller toolchain and Renovate configuration
status: Done
assignee:
  - '@pi'
created_date: '2026-11-01 00:46'
updated_date: '2026-11-01 01:02'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The first private GitHub staging run selected Python 3.14.4 despite the controller requiring at least 3.14.7, and Renovate rejected the inherited bunInstall post-update option. Prepare minimal configuration fixes without enabling publishing or Renovate, touching production, or changing application behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Controller CI explicitly uses Python 3.14.7 and uv 0.12.19, matching the supported project toolchain.
- [x] #2 Renovate configuration passes its official schema without bunInstall, while enabled remains false.
- [x] #3 Local reproduction demonstrates the Python and Renovate failures and confirms the proposed fixes; controller tests and workflow safety checks pass.
- [x] #4 After explicit remote approval, protected-PR validation succeeds and the fixes are merged without weakening branch protections or enabling publishing.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the exact Python incompatibility and Renovate schema failure; retain value-free evidence.
2. Obtain approval for the concrete patch and protected-PR validation/merge in the new staging repository.
3. Pin controller setup and uv commands to Python 3.14.7; pin setup-uv to the declared uv 0.12.19. Remove only the invalid bunInstall option.
4. Run the controller suite, official Renovate schema validation, actionlint and workflow safety assertions locally.
5. Push a fix branch and use a protected PR only after approval; verify Actions for the exact head SHA and merge without changing protections.
6. Recheck that the repository is private, publisher skipped, Renovate disabled, no production credentials or package access added, and the old repository unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Initial staging root d1c13d1ef5d0956b19ed3632e383da18930f5fbe is deployed only as private GitHub source, not production. Backend/frontend/backup/public-source and comment-policy jobs pass; controller fails before tests, publisher skipped.
- Red/green Python probe: uv lock --check --python 3.14.4 fails with the exact incompatible-interpreter error; requesting 3.14.7 succeeds.
- Official Renovate JSON schema reproduces the invalid bunInstall value. GitHub Renovate issue #1 identifies the same error; enabled is already false.
- No code fix or additional remote push/PR/merge yet; awaiting approval for this configuration-only plan.

- Owner approved the two configuration fixes, local validation, a new-repository branch/PR and merge only after validation passes. No protection, publication, publisher, Renovate enablement, credential, package or production changes are authorized.
- Pinned controller setup and run commands to Python 3.14.7 and setup-uv to 0.12.19. Removed only the invalid bunInstall post-update option; Renovate stays disabled.
- Exact declared toolchain passed lock/sync, all 102 controller tests, ruff lint/format, strict pyright and fixture-only report. Official Renovate JSON schema, actionlint, static publisher safety assertions and diff checks all pass.
- Remote validation and merge remain pending; acceptance criterion 4 is not yet complete.

- Approved fix branch 139e3da16031559db355fdd00fc39c9a85c28f66 passed all PR validation workflows; publisher was skipped.
- PR #2 was squash-merged through GitHub after validation, producing main 03a4c3fa76e047c69b945bc3aa6744586b498f2d. Both post-merge workflows succeeded; backend, frontend, backup, publication guard and controller jobs passed; publisher skipped.
- New and original branch-protection readbacks are unchanged. New repository is still private with zero repository secrets, variables, environments or retained artifacts; Renovate remains disabled. Old main and production are untouched by this work.
- Five additional workflow log archives were captured privately and scanned with zero findings. The app-owned Renovate issue remains open; its config now passes the official schema, but automation has not been enabled.
- Task completion metadata is recorded locally after the authorized merge and is not an additional remote commit. Full publication and operational migration remain separate approvals.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the two private-staging configuration failures without changing application behavior or deployment controls.

Changes:
- Pinned controller Actions setup/commands to Python 3.14.7 and uv 0.12.19.
- Removed the invalid Renovate bunInstall post-update option; Renovate stays disabled.

Verification:
- Local declared-toolchain validation passed 102 controller tests, lock/sync, lint/format, type checking and fixture report. Official Renovate schema and workflow safety checks passed.
- PR #2 validation succeeded; merged as 03a4c3fa76e047c69b945bc3aa6744586b498f2d. Post-merge CI and comment-policy workflows also succeeded, with publishing skipped.
- Branch protections, private visibility and absence of production secrets/variables were verified unchanged.

The complete public development/CI/CD migration is not yet finished; publication and production/bot/controller handover still require approval.
<!-- SECTION:FINAL_SUMMARY:END -->
