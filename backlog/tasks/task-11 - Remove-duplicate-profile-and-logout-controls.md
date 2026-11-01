---
id: TASK-11
title: Remove duplicate profile and logout controls
status: Done
assignee:
  - '@pi-agent'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-09 02:09'
labels:
  - frontend
  - ux
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Profile and Logout controls appear both in the global header and above the playlist list, creating repetitive navigation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each responsive layout presents one clear profile and logout control group rather than duplicate groups
- [x] #2 Profile and logout actions remain easy to find from the playlist and results views
- [x] #3 Removing the duplicate controls does not reduce keyboard or mobile accessibility
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Removed duplicate Profile/Logout controls from the Match My Music playlist sidebar, leaving the global header as the single profile/logout group.

Changes:
- `PlaylistSidebar.tsx`: deleted the "User Info" block (avatar, display name, Logout button) rendered above the playlist list; removed the now-unused `user` and `onLogout` props and the `SpotifyUserProfile` import. This fixes duplicates in both the desktop aside and the mobile drawer, which share this component.
- `MatchMyMusic.tsx`: dropped `user`/`onLogout` props from both `<PlaylistSidebar>` usages (desktop + mobile drawer).
- `App.tsx`: added `type="button"` and `aria-label="Log out"` to the header Logout button, since it is now the sole logout control (screen-reader accessibility).

Verification:
- `bun run typecheck` passes
- `bun run lint` — 0 errors (3 pre-existing warnings in untouched files)
- `bun run build` succeeds

Accessibility: the header profile/logout group is always visible at every breakpoint and remains in normal tab order, so keyboard and mobile accessibility are unchanged; profile/logout stay findable from playlist and results views via the persistent header.
<!-- SECTION:FINAL_SUMMARY:END -->
