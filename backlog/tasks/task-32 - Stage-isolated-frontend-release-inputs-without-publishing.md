---
id: TASK-32
title: Stage isolated frontend release inputs without publishing
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 13:36'
updated_date: '2026-11-02 13:51'
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
- [ ] #2 IaC manages exactly the four approved production-environment variables with public client values sourced privately and invalid legacy DSNs rejected; publication remains false.
- [ ] #3 Only the dedicated project:releases credential from Doppler is transferred into the protected environment, with no plaintext token in code, logs, plans or Terraform state.
- [ ] #4 Protected PR and post-merge validation pass; scoped provisioning readbacks preserve main/environment protections, old publisher inputs and services, with no uploads, image publication or bot activation.
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
<!-- SECTION:NOTES:END -->
