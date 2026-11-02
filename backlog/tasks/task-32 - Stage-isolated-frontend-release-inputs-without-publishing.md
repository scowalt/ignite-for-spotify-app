---
id: TASK-32
title: Stage isolated frontend release inputs without publishing
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 13:36'
updated_date: '2026-11-02 14:27'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stage the approved isolated GlitchTip frontend target and minimum protected CI inputs without activating publishing or changing production. Preserve legacy inputs, protections and observability history.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The upload workflow and operating guidance identify the isolated frontend organization/project 8, while backend project 2 and legacy frontend project 1 remain intact.
- [x] #2 IaC manages exactly the four approved production-environment variables with public client values sourced privately and invalid legacy DSNs rejected; publication remains false.
- [x] #3 Only the dedicated project:releases credential from Doppler is transferred into the protected environment, with no plaintext token in code, logs, plans or Terraform state.
- [x] #4 Protected PR and post-merge validation pass; scoped provisioning readbacks preserve main/environment protections, old publisher inputs and services, with no uploads, image publication or bot activation.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add required public client inputs and four environment-variable resources to the isolated IaC root, plus mocked positive/negative tests and persistent native state locking. Preserve all existing resources and disabled publishing.
2. Retarget source-map organization routing, add routing regressions and update guidance/read-only CLI organization selection without changing existing defaults or mutation endpoints.
3. Validate source locally and through a protected PR; merge only the exact green head with explicit Gmail author.
4. Privately retrieve the existing PostHog client value and project 8 public DSN, generate/review a plan, and apply only the four already-approved additions. Stop for any other drift/action.
5. Securely transfer only the dedicated Doppler upload token to the production environment, verify metadata and unchanged protections/old inputs, and leave publishing false. No file uploads, images, runtime changes or bot activation.

Owner explicitly approved this CI-staging scope. Keep old Doppler build inputs unchanged and all operator credentials out of Terraform state.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Retargeted source-map routing to the isolated organization/project 8; legacy CLI default remains scowalt with explicit opt-in for the new organization. Added offline routing regressions without real API calls.
- Added exactly four environment-variable resources, required redacted public-client inputs, wrong/legacy-DSN rejection and native backend locking. Seven mocked plan tests pass; no live values or operator token enter CI fixtures.
- Dedicated upload credential stays outside Terraform. The approved live staging will add only these inputs, retain publication=false and preserve old Doppler build inputs. No upload/deployment has occurred.

Local validation passed: eight mocked IaC plan tests, 32 script scenarios (binary protocol case separately executed), source-map routing/protocol regression, 94 backend tests, 37 frontend tests plus lint/types, shellcheck and actionlint. Public analytics inputs reject personal-token shapes; isolated DSN guard rejects old project 1 and unreviewed hosts. Live staging is not yet performed.

- PR #3 merged as 2d4b69a9bf9c3c107e7481e641c780de484f7ce0 with explicit Gmail author/expected head. PR CI 41457051585 and post-merge CI 41458303457 passed all ten validation jobs; publishing skipped. Hosted protocol/routing tests executed and image report summaries passed.
- Live plan contained exactly four approved environment-variable additions and no resource updates/deletions. An initial review stop identified only null/empty-team and null/zero-wait-timer provider normalization; required reviewer and actual API policy remained unchanged. The exact normalization was recorded, not masked by ignore_changes.
- Applied the four inputs, privately verified values against approved sources, and securely transferred only the dedicated project:releases token from Doppler into production environment secret GLITCHTIP_AUTH_TOKEN. No plaintext operator credentials are present in state; GitHub encrypted secret values cannot be read back, so metadata/transfer success is recorded rather than an unverifiable value claim.
- Follow-up live plan is empty; state serial is 4. Main/environment protections, old publisher input metadata, old Doppler DSN absence and unrelated state hashes are preserved. Publication remains false. No file upload, registry publication, service change or bot activation occurred.
- Final task completion metadata is local after merge, pending a later approved documentation commit.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Staged isolated frontend release configuration without publishing.

Changes:
- Routed future source-map uploads to the isolated organization/project 8; retained legacy project 1/backend project 2 and explicit opt-in operator queries.
- Added four IaC-managed production variables with public-client input validation and native state locking. Operator credential transfer stays outside Terraform.
- Updated operating instructions and regression coverage, preserving disabled publishing and existing protections.

Validation and provisioning:
- Eight mock IaC tests, script/protocol/routing tests, application tests and static/source checks passed; protected PR #3 and post-merge CI passed.
- Applied only four approved variables; transferred the dedicated upload credential securely from Doppler. Follow-up plan is empty, all values/policies verified within available readback limits.

No source-map upload, image push, runtime cutover or bot activation occurred. Existing production and old publisher inputs remain unchanged.
<!-- SECTION:FINAL_SUMMARY:END -->
