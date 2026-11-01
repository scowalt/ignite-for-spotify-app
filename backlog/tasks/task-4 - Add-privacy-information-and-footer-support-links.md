---
id: TASK-4
title: Add privacy information and footer support links
status: Done
assignee:
  - '@scowalt'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-16 20:21'
labels:
  - frontend
  - privacy
  - content
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The site has no discoverable privacy or legal information and no clear footer route for contacting the operator or reporting an issue. Publish the disclosures appropriate for the service and make support paths easy to find.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A public privacy page clearly explains the service’s relevant data collection, use, retention, and contact details
- [x] #2 The site footer links clearly to the privacy page
- [x] #3 The footer provides a clear contact or report-an-issue link that works without searching the site
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a public /privacy route with factual disclosures for Spotify data, cookies, PostHog analytics and session replay, diagnostics, providers, retention, user choices, and privacy@igniteforspotify.com contact details.

Added Privacy and pre-addressed Contact / report-an-issue links to the global responsive footer, plus a privacy notice beside the signed-out Spotify CTA.

Logout now confirms the destructive action, deletes saved match snapshots before the local Spotify session, preserves the session on deletion failure, and provides keyboard-safe focus containment and restoration.

Automatic analytics and provider-side retention remain disclosed rather than consent-gated; the notice makes no jurisdiction-specific compliance claim.

Verification passed: 90 backend tests, 30 frontend tests, frontend typecheck, lint, production build, git diff check, responsive browser checks at 1440x900 and 390x844, effective 200% zoom, failure-state and keyboard dialog checks, and a clean Impeccable detector result. The inline Impeccable finish review disposition was ship; a separate reviewer was not used because delegation was not authorized for this task.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Published a discoverable privacy notice and direct support path throughout the site. Users now see what Ignite collects, why it is used, how long it remains, which providers process it, and how to request help or deletion before connecting Spotify. Logout now clearly confirms and removes the user live session, tokens, and saved playlist match results.
<!-- SECTION:FINAL_SUMMARY:END -->
