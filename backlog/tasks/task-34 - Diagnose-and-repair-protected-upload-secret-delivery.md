---
id: TASK-34
title: Diagnose and repair protected upload-secret delivery
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 16:19'
updated_date: '2026-11-02 17:13'
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
- [x] #2 The verified cause is repaired with the same scoped credential and an early missing-credential guard at the appropriate seam; no repository-level copy or broad inheritance is introduced.
- [x] #3 Protected PR validation and credential-presence verification pass; temporary diagnostics are removed or retained only as clearly scoped safety checks.
- [x] #4 Both publishers remain fenced, protections and running services unchanged, with no publication retry or credential-scope expansion.
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

- PR #6 merged at f98579bb4dc42021dd4dbcbdea9982eac1ff0a82 after CI 41485613099 and comment checks passed.
- Protected named-mapping run 41486334373: direct=present, unforwarded reusable=absent, declared-and-explicitly-mapped reusable=present. Only the named caller mapping changed. No credential re-provisioning/rotation, repository-level copy or scope expansion was needed.
- GitHub primary documentation confirms environment-only secrets must still be passed by the caller; missing mapping silently resolves empty.
- Added failing regressions first for the actual publisher configuration body and caller/callee contract, then repaired with exactly one named map, a required declaration, and an early conditional nonempty guard. All guard cases now pass, including missing-token rejection before build/upload.
- Removed temporary diagnostics after evidence capture. Actionlint, mock IaC, script suite and the real pinned credential-free protocol fixture pass. Live upload compatibility remains unproven; both publishers stay fenced.

- PR #7 merged as b278db534b91e54a09362f42a0d88f412432a0c5 from exact validated head 53c8e22d988349ef537d405251f4c29fc0c028b9, explicit Gmail author and expected-head control. PR CI 41487220188 and post-merge CI 41488023894 passed all ten validation jobs; publisher skipped. Comment checks passed.
- Final readback verified exact main/environment protections, read-only workflow-token defaults, all four staged release-variable fingerprints and environment-only secret placement. Secret creation/update metadata is unchanged. Both live publication fences remain in place; desired flag is false.
- Production container IDs/start times/images/projects/mounts still match the pre-publication baseline. No live source-map uploads, image pushes, deployments, credential changes, state applies or bot changes occurred during recovery.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Repaired the empty upload-secret handoff without changing credential scope or production.

- Protected differential checks showed that direct environment access works, but reusable jobs receive an empty value until the caller explicitly maps the secret name. A declaration alone did not fix it.
- The CI publisher now passes only GLITCHTIP_AUTH_TOKEN, declares that name required, and rejects an empty runtime value before frontend build when source maps are enabled.
- Removed temporary diagnostics, retained evidence/docs, and aligned desired publication to the live false safety fence.

Validation: real protected presence-only comparisons; red/green tests for the actual guard and contract; 35 script tests (binary fixture also run separately), mocked IaC, actionlint, workflow safety assertions, comment/secret checks, and protected PR/post-merge CI. Both publishers remain fenced and production unchanged. Live upload compatibility and publication retry require separate approval.
<!-- SECTION:FINAL_SUMMARY:END -->
