---
id: TASK-13
title: Remove excessive space above the footer
status: Done
assignee:
  - '@myself'
created_date: '2026-07-22 18:33'
updated_date: '2026-07-28 19:46'
labels:
  - bug
  - frontend
  - layout
  - responsive
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On large screens, Match My Music can leave a large empty gap between the results area and the footer, making the page feel unfinished.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The footer follows Match My Music content without an excessive empty vertical gap on common desktop viewport sizes
- [x] #2 The layout remains balanced for empty, short, and long result states
- [x] #3 The fix does not cause the footer to overlap content or introduce horizontal scrolling
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the authenticated Match My Music layout at representative desktop and mobile viewport sizes, covering no playlist, short/empty results, and long results; record the content, page, and footer dimensions to confirm which fixed-height and margin rules create the gap.
2. Make the smallest responsive layout change in the Match My Music page/app shell so the authenticated content height is driven by its rendered state instead of reserving an unconditional viewport-sized block, while preserving the desktop playlist sidebar and mobile drawer behavior.
3. Verify empty, short, and long states at common desktop sizes and a narrow mobile size, checking that the footer follows content, never overlaps it, and the document does not gain horizontal overflow.
4. Run frontend lint, typecheck, tests, and production build; add focused regression coverage where the existing test setup can assert the layout contract, and document browser verification for the visual-only cases.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Reproduced against the actual production bundle in headless Chromium with mocked authenticated API responses. At 1440x900 the fixed Match layout is 836px tall and leaves a 604px content-to-footer gap; at 1280x720 the gap is 424px.
- Tested hypotheses independently. Setting only the Match wrapper height to auto reduces the gap to the intended 48px (content padding plus footer margin); removing the footer margin, neutralizing shell spacing, or changing inner overflow does not remove the excessive gap. Root cause is the unconditional `h-[calc(100vh-4rem)]` wrapper.

- Removed the fixed viewport height from the authenticated Match My Music wrapper so empty, short, and long states size the page from rendered content.
- Rebuilt and reran the production-bundle Chromium harness at 1440x900, 1024x768, and 390x844. Empty, one-result, and 30-result states all leave the intended 48px content-to-footer spacing, produce no footer overlap, and add no Match layout horizontal overflow. The pre-existing narrow-header overflow at 390px is unchanged by this fix.
- Verification passed: `bun test` (25 tests), `bun run typecheck`, `bun run lint` (0 errors; 3 pre-existing warnings), and `bun run build`.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Removed the unconditional viewport height from the authenticated Match My Music layout, allowing the page and footer to follow empty, short, and long content naturally instead of reserving hundreds of blank pixels.

User impact:
- The footer now sits directly after Match My Music content with the existing intentional spacing.
- Long result lists expand the document without overlapping the footer or adding Match-area horizontal overflow.

Verification:
- `bun test` — 25 passing
- `bun run typecheck`
- `bun run lint` — 0 errors (3 existing warnings)
- `bun run build`
- Production-bundle Chromium checks at desktop, tablet, and mobile viewport sizes across empty, short, and long states
<!-- SECTION:FINAL_SUMMARY:END -->
