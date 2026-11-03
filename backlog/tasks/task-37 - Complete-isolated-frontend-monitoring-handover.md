---
id: TASK-37
title: Complete isolated frontend monitoring handover
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 21:39'
updated_date: '2026-11-02 22:00'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure Mission Control monitoring covers the newly active isolated frontend organization as well as legacy/frontend and unchanged backend history, preserving metadata-only output and existing private diagnostics. Preserve pre-existing Mission Control working changes and publisher/deployment fences.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Default maintained monitoring reads both allowlisted organizations and distinguishes identical project slugs without emitting raw event data.
- [x] #2 Pagination cannot cross an organization boundary, and unavailable organization coverage fails visibly rather than silently reporting success.
- [x] #3 Offline regressions and a bounded live metadata-only check pass; canonical source and installed helper are synchronized while pre-existing work is preserved.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve existing Mission Control modifications and work from its current upstream in an isolated worktree.
2. Add explicit allowlisted multi-organization coverage, namespaced output and pagination guards with tests. Preserve existing diagnostics/sanitizers and no-event default.
3. Validate/merge through its forge, apply only the feature delta to the existing working source, install the verified helper and run one bounded metadata-only live check.
4. Keep all publisher/updater fences and other project work unchanged; report any supported-interface or authorization limitation rather than bypassing it.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Mission Control issue #59 / PR #60 merged as 0f7801384cc388cb7f6f43322103513432941b73 from exact tested head 5098b2f5b139a25eaf337eecbc6975647a6fc4bd, explicit Gmail author and expected head. Its existing Woodpecker push/PR pipelines 119/120 passed; GitHub Actions remains disabled as intended for Mission Control. Added the 42 offline reader tests to that existing pipeline rather than re-enabling unrelated CI.
- Applied only the feature edits to the permanent Mission Control source and catalog. Pre-existing formatting/other dirty work were preserved; its checkout HEAD was not reset/pulled through unrelated working changes. Installed helper was backed up and its prior behavioral equivalence reviewed before atomic replacement.
- Installed helper exactly matches maintained working source. Live default metadata-only check succeeded across both allowlisted organizations in five pages; no events/titles/messages requested. Identical project slugs are namespaced and failed coverage is not silently accepted.
- Ignite handoff documentation PR #9 merged as 291ea66cd56d7830c02068f5116a74d8bec7b6bd with required CI and publisher skipped. Runtime and publisher/updater fences are unchanged.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Closed the isolated-frontend monitoring gap in Mission Control without weakening privacy or credentials.

- Default metadata-only summaries read both scowalt and ignite-for-spotify-app-frontend, explicitly report coverage, namespace project identities, and reject cross-organization pagination.
- Missing organization access fails visibly; existing diagnostics and sanitizers remain intact.
- 42 offline tests and a bounded live installed-helper check pass. Existing Woodpecker CI was preserved and now runs these regressions.
- Upstream source, permanent working source and installed helper carry the feature; prior working edits/history remain preserved. No service or publisher activation occurred.
<!-- SECTION:FINAL_SUMMARY:END -->
