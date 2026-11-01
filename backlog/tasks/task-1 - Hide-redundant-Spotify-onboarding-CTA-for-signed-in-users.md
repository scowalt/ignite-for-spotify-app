---
id: TASK-1
title: Hide redundant Spotify onboarding CTA for signed-in users
status: Done
assignee:
  - '@myself'
created_date: '2026-07-22 18:33'
updated_date: '2026-07-25 20:37'
labels:
  - bug
  - frontend
  - authentication
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A signed-in user still sees the ‘Get Started with Spotify’ button. Activating it spends a long time loading before returning to the same page, creating a confusing and unnecessary authentication round trip.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Signed-in users are not shown a Spotify onboarding action that restarts authentication
- [x] #2 Signed-out users can still start Spotify authentication from the home page
- [x] #3 Authentication-state changes update the home-page action without a long redirect loop back to the same state
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Render the home hero primary action from the reactive authentication state.
2. Show no auth-sensitive CTA while loading, Spotify onboarding when signed out, and Match My Music when signed in.
3. Run frontend typecheck, lint, build, and manual state verification.
4. Record acceptance criteria and completion through Backlog CLI.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Made the home hero CTA reactive to auth loading and session state.
- Signed-out users retain Spotify onboarding; signed-in users receive a direct Match My Music action.
- Removed the duplicate home-page login analytics call; authStore remains the single event source.
- Verification passed: frozen Bun install, TypeScript typecheck, ESLint (0 errors; 4 pre-existing unrelated warnings), Vite production build, targeted source assertions, and git diff check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented an auth-aware home-page hero action. The Spotify onboarding CTA is withheld while session state loads, remains available when signed out, and changes to Match My Music when signed in. Removed duplicate login-initiation analytics from the page. Frontend typecheck, lint, production build, source assertions, and diff checks pass.
<!-- SECTION:FINAL_SUMMARY:END -->
