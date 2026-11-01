---
title: "fix: Improve match results discoverability and download CTA"
type: fix
status: completed
date: 2026-03-23
---

# fix: Improve match results discoverability and download CTA

## Overview

PostHog analytics revealed that 4 out of 7 users who completed playlist searches never clicked through to download a matched song. The most engaged non-converting user (`12172595106`) searched 25 playlists across 3 sessions in a single day — finding hundreds of matches — but their autocapture timeline shows zero interaction with any result card or download link. Every click was either a playlist name or "Search for Matches." Meanwhile, the top converting user (`1113564858`) clicked "Download" within 22 seconds of results appearing.

The evidence points to three compounding UX gaps in `MatchMyMusic.tsx`: results render below the fold with no scroll cue, the download action is styled as a subtle text link rather than a button, and searches returning zero matches show no feedback below the summary banner.

## Problem Frame

Users complete searches that return matches, but the results section renders below the sticky search bar and "Search Complete!" summary banner. On most viewports, results are not visible without scrolling. There is no visual indicator that content appeared below the fold. Additionally, the download CTA is a plain green text link that blends with other metadata, and zero-match searches silently render nothing in the results area.

## Requirements Trace

- R1. After a search completes with matches, the viewport must scroll to make the first result visible without manual user action
- R2. The download action for each match must have clear button affordance (background, padding, visual weight) distinct from surrounding text
- R3. When a search completes with zero matches, a clear empty-state message must appear in the results area

## Scope Boundaries

- No changes to search logic, SignalR handlers, or the backend
- No changes to the sidebar/playlist selector layout
- No new analytics events (existing `match_downloaded` tracking is sufficient)
- No test infrastructure setup — the frontend has no existing test files

## Context & Research

### Relevant Code and Patterns

- `frontend/src/pages/MatchMyMusic.tsx` — the single file containing all three change points
  - Lines 102-111: `ReceiveSearchComplete` handler where auto-scroll should trigger
  - Lines 326-337: "Search Complete!" summary banner (renders for both 0-match and N-match cases)
  - Lines 340-411: Results section, conditionally rendered only when `searchResults().length > 0`
  - Lines 394-402: Download link — currently an `<a>` with `text-spotify-green hover:underline text-sm`
- `frontend/src/lib/analytics.ts` — existing analytics; `matchDownloaded` fires on download click
- Login button pattern (line 172): `bg-spotify-green hover:bg-green-500 text-black font-bold py-2 px-6 rounded-full` — the project's established "primary action" button style
- SolidJS reactivity primitives already imported: `createSignal`, `createEffect`, `Show`

## Key Technical Decisions

- **Auto-scroll uses a SolidJS ref + `createEffect`**: Rather than scrolling inside the `ReceiveSearchComplete` SignalR handler (which fires before the DOM updates), a `createEffect` watching `searchComplete()` will trigger after SolidJS reconciles the DOM. This ensures the results section element exists before scrolling to it.
- **`scrollIntoView` with `behavior: 'smooth'`**: Native browser API, no dependencies. Scroll target is the results heading, not the summary banner — the user has already seen the banner.
- **Download button inherits the project's existing button pattern**: The login button and search button both use `bg-spotify-green text-black font-bold rounded` variants. The download button should use a smaller variant of this same pattern to stay consistent while fitting the compact match card layout.
- **Empty state is a sibling `<Show>` block**: A new `<Show when={searchComplete() && searchResults().length === 0}>` block renders alongside the existing results `<Show>`. This avoids nesting complexity and follows the same pattern used for the error state and progress bar.

## Open Questions

### Resolved During Planning

- **Should auto-scroll happen during streaming results or only on completion?** On completion only. Scrolling mid-search while results are still streaming in would be disorienting. The `searchComplete` signal is the right trigger.
- **Should the empty state suggest actions?** Yes — suggest trying a different playlist. This gives the user a clear next step rather than a dead end.

### Deferred to Implementation

- **Exact scroll offset/padding**: Whether `scrollIntoView` with `block: 'start'` positions perfectly or needs a small offset will depend on the sticky header height. Adjust during implementation if needed.
- **Download button sizing**: The exact `py-` and `px-` values that look right in the compact match card layout should be tuned visually during implementation.

## Implementation Units

- [ ] **Unit 1: Auto-scroll to results on search completion**

  **Goal:** When a search finishes with matches, smoothly scroll the main content area so the results heading is visible.

  **Requirements:** R1

  **Dependencies:** None

  **Files:**
  - Modify: `frontend/src/pages/MatchMyMusic.tsx`

  **Approach:**
  - Add a ref to the results section container (the `<div class="space-y-4">` wrapping the results heading and cards)
  - Add a `createEffect` that watches `searchComplete()` — when it transitions to non-null and `searchResults().length > 0`, call `scrollIntoView({ behavior: 'smooth', block: 'start' })` on the ref
  - The effect must guard against the ref being null (it won't exist if results are empty)

  **Patterns to follow:**
  - Existing `createEffect` usage in the component (lines 57-61, 75-121)
  - SolidJS ref pattern: `let resultsRef: HTMLDivElement | undefined;` then `ref={resultsRef}` on the element

  **Test scenarios:**
  - Search with matches: viewport scrolls to results heading after completion
  - Search with 0 matches: no scroll occurs (ref doesn't exist)
  - Rapid re-search: previous results cleared, new scroll on new completion
  - Mobile viewport: scroll works within the `overflow-y-auto` main container

  **Verification:**
  - After searching a playlist with known matches, the results heading is visible without manual scrolling on both desktop and mobile viewports

- [ ] **Unit 2: Restyle download link as a button**

  **Goal:** Make the download action visually prominent with clear button affordance.

  **Requirements:** R2

  **Dependencies:** None

  **Files:**
  - Modify: `frontend/src/pages/MatchMyMusic.tsx`

  **Approach:**
  - Change the `<a>` element's classes from `text-spotify-green hover:underline text-sm` to a compact button style using the project's green button pattern: green background, black text, rounded, with padding
  - Keep it as an `<a>` tag (it opens an external link in a new tab), just restyle it
  - Use a smaller variant than the full "Search for Matches" button since it's inside a compact card

  **Patterns to follow:**
  - Login button: `bg-spotify-green hover:bg-green-500 text-black font-bold py-2 px-6 rounded-full`
  - Adapt to compact size: smaller padding, `text-sm`, `rounded` instead of `rounded-full`

  **Test scenarios:**
  - Download button is visually distinguishable from surrounding text at a glance
  - Button hover state provides feedback
  - Link still opens in new tab and fires analytics event
  - Multiple download buttons in a result card with many matches don't crowd the layout

  **Verification:**
  - The download action reads as a clickable button, not a text link, when viewing the results page

- [ ] **Unit 3: Add empty state for zero-match searches**

  **Goal:** When a search completes and finds no matches, display a clear message with a suggestion to try another playlist.

  **Requirements:** R3

  **Dependencies:** None

  **Files:**
  - Modify: `frontend/src/pages/MatchMyMusic.tsx`

  **Approach:**
  - Add a new `<Show>` block between the "Search Complete" summary (line 337) and the results section (line 340)
  - Condition: `searchComplete() && searchResults().length === 0`
  - Display a centered message with an icon, "No matches found" heading, and suggestion text like "Try a different playlist — larger playlists with popular songs tend to have more CDLC matches"
  - Follow the visual pattern of the existing "No playlist selected" empty state (lines 275-293): gray background card, centered icon, muted text

  **Patterns to follow:**
  - "No playlist selected" state (lines 275-293): `bg-gray-800 rounded-lg p-8 text-center` with SVG icon and `text-gray-400` text

  **Test scenarios:**
  - Search that returns 0 matches shows the empty state message
  - Search that returns matches does NOT show the empty state
  - Starting a new search clears the empty state (because `searchComplete` resets to null)
  - Empty state is visually consistent with other empty/placeholder states in the page

  **Verification:**
  - Searching a playlist with no CDLC matches shows a helpful message instead of blank space below the summary banner

## System-Wide Impact

- **Interaction graph:** Changes are isolated to the `MatchMyMusic` component's render output. No callbacks, stores, or other components are affected.
- **Error propagation:** No new error paths. The `scrollIntoView` call is fire-and-forget on a DOM element.
- **State lifecycle risks:** None. All three changes are purely presentational, reading existing signals without modifying them.
- **API surface parity:** N/A — frontend-only changes.
- **Integration coverage:** No backend changes. Visual verification is the primary validation method.

## Risks & Dependencies

- **Scroll behavior on the `overflow-y-auto` container:** `scrollIntoView` on a child of a scrollable container scrolls the container, not the window. This is the correct behavior for this layout, but should be verified on both desktop (sidebar layout) and mobile (drawer layout).
- **No frontend tests:** The project has no frontend test infrastructure. All three units should be verified manually in a running dev server.

## Sources & References

- PostHog analytics investigation (this conversation): Users `12172595106`, `31nc3uujel5i7gtvvvgraxwjx2ye`, `stevengraffen` searched with matches but never interacted with results
- Converting user `1113564858` comparison: clicked "Download" within 22 seconds, demonstrating the button text IS discoverable when results are visible
- Related code: `frontend/src/pages/MatchMyMusic.tsx`, `frontend/src/lib/analytics.ts`
