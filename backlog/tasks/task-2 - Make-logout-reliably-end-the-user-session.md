---
id: TASK-2
title: Make logout reliably end the user session
status: Done
assignee:
  - '@myself'
created_date: '2026-07-22 18:33'
updated_date: '2026-07-27 23:53'
labels:
  - bug
  - frontend
  - authentication
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Logout control next to the user profile appears unresponsive. Users need a dependable way to end their Ignite and Spotify-backed session.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Activating Logout ends the current Ignite session and clears user-specific UI state
- [x] #2 After logout, the application displays the signed-out home-page state
- [x] #3 Logout failures provide visible feedback rather than appearing to do nothing
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the bug with `frontend/tests/auth-api.test.ts`: mock `POST /api/auth/logout` returning a successful empty `200` and prove `auth.logout()` currently rejects while trying to parse JSON.
2. Fix `frontend/src/lib/api.ts` so successful responses with no body resolve as `undefined`, while non-empty JSON responses continue to parse normally. Cover empty `200`, `204`, ordinary JSON, and failed-response behavior with Bun tests.
3. Harden `frontend/src/stores/authStore.ts`: clear stale errors at the start, guard duplicate logout attempts, preserve the session on an HTTP failure, and expose pending state. After confirmed success, clear the session, reset analytics identity, and use `window.location.replace("/")` so route-local state and the shared query cache are discarded.
4. Update every logout control (`frontend/src/App.tsx` and `frontend/src/components/PlaylistSidebar.tsx` via `MatchMyMusic.tsx`) to reflect/disable during the pending request. Render `authStore.error()` in the application shell as an accessible `role="alert"` so failures are visible from every route.
5. Run `bun test`, frontend typecheck, lint, and production build. Re-run the empty-response repro, verify failed logout retains the signed-in UI with an alert, and verify successful logout lands on the signed-out home state with user-specific UI removed. Then update acceptance criteria, notes, final summary, and status through Backlog CLI.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Began implementation after plan approval.
- Leading diagnosis: the logout endpoint returns an empty successful response, while the frontend API helper unconditionally parses successful non-204 responses as JSON.

- Added the approved public-seam regression test around `auth.logout()`.
- RED confirmed: an empty successful `200 OK` causes `auth.logout()` to reject with an end-of-JSON parse failure.

- GREEN: successful empty responses now resolve without JSON parsing; ordinary JSON and API error behavior remain covered.
- Logout now clears stale errors, rejects duplicate submissions, preserves authenticated state on HTTP failure, clears the session and analytics identity after success, and replaces the current document with `/` to remove route/query state.
- Header and playlist-sidebar controls expose pending state; the application shell renders auth failures as an assertive accessible alert.
- Review hardening guarantees non-empty HTTP error messages and prevents PostHog failures from interrupting successful logout.
- Added 10 Bun regression tests and wired them into frontend CI. Final review found no remaining high/medium issues.
- Verification passed: `bun run test` (10 tests), TypeScript typecheck, ESLint (0 errors; 3 pre-existing unrelated warnings), Vite production build, `git diff --check`, and debug-instrumentation scan.

- Rebased the completed change onto the latest `origin/main` dependency updates. Configured ESLint to include the new Bun tests without requiring them in the browser TypeScript project; the exact pre-commit lint path now passes.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed logout requests that completed on the server but appeared unresponsive because the frontend tried to parse an empty `200 OK` body as JSON.

Changes:
- Accept successful empty API responses while preserving JSON parsing and guaranteed non-empty failure messages.
- Guard duplicate logout requests, retain the current session on genuine HTTP failures, and reset auth/analytics state after success.
- Replace the current document with the home route after logout, clearing route-local and query-cached user state.
- Show pending state on every logout control and render failures in a global accessible alert.
- Add API/store regression coverage and execute frontend tests in CI.

Verification:
- `bun run test` (10 passed)
- `bun run typecheck`
- `bun run lint` (0 errors; 3 unrelated pre-existing warnings)
- `bun run build`
- `git diff --check`
<!-- SECTION:FINAL_SUMMARY:END -->
