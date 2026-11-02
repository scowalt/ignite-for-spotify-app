---
id: TASK-34
title: Diagnose and repair protected upload-secret delivery
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 16:19'
updated_date: '2026-11-02 16:49'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Resolve the empty SENTRY_AUTH_TOKEN observed in the first publication run using protected presence-only diagnostics, without broadening credentials or retrying publication. Keep both publishers fenced and preserve production.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A protected, exact-head presence-only comparison isolates direct versus reusable secret delivery without disclosing values or making upload/registry/service requests.
- [ ] #2 The verified cause is repaired with the same scoped credential and an early missing-credential guard at the appropriate seam; no repository-level copy or broad inheritance is introduced.
- [ ] #3 Protected PR validation and credential-presence verification pass; temporary diagnostics are removed or retained only as clearly scoped safety checks.
- [ ] #4 Both publishers remain fenced, protections and running services unchanged, with no publication retry or credential-scope expansion.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve/replay the failed release trace; compare protected direct, reusable undeclared and reusable declared-secret paths using presence-only checks on reviewed main.
2. Test one cause at a time: stored value, reusable binding/declaration, or context/timing. Preserve identity/environment metadata and never print values.
3. Repair only the demonstrated cause, re-provisioning the same environment credential only if necessary; add an early presence guard and appropriate regression.
4. Validate protected PRs and repeat the original presence seam. Remove temporary probes after evidence is captured or retain only a documented permanent safety check.
5. Keep both publishers fenced and reconcile source policy to false so an IaC apply cannot silently undo the safety fence. No source-map upload, images, deployment, broader secret scope or publication retry.

Owner explicitly approved narrow recovery and protected presence-only execution. The original first-publication approval does not authorize a retry.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Prepared a three-path protected presence-only comparison: direct, reusable without declaration, reusable with optional declaration. All paths use the same existing environment/secret; no checkout, network commands, package permissions, forwarding or uploads. Local synthetic present/absent tests prove constant-only output. Source publication policy is false to match the live safety fence. Mock IaC (8), actionlint, script tests and comment checks passed; real secret behavior remains unverified pending reviewed main execution.

- PR #5 merged at b952036ee722d2f62735741ce44719239c61cb5f after CI 41483141786 and both comment checks passed; desired publishing is now false.
- Protected presence-only run 41484155322: direct=present, reusable=absent, optional-declared reusable=absent. Thus the environment value exists and declaration alone does not fix delivery. Both publishers remain fenced; no credential or service mutation.
- Next falsifiable probe changes only the declared caller to explicitly map the one secret name. No inherit, repository-level copy or real upload; no re-provisioning is warranted by the evidence.
<!-- SECTION:NOTES:END -->
