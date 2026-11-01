---
id: TASK-5
title: Improve branded search discoverability
status: Done
assignee:
  - '@scowalt'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-16 20:58'
labels:
  - frontend
  - seo
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Searching Google for ‘Ignite for Spotify’ surfaces community posts and ordinary Spotify pages instead of the Ignite website. Improve crawlability and branded metadata without relying on a guaranteed ranking position.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Public pages provide unique indexable titles and descriptions that identify Ignite for Spotify
- [x] #2 Search engines can discover the canonical production URL through valid canonical, robots, and sitemap configuration
- [x] #3 A documented search-console or equivalent check confirms the production home page is eligible for indexing
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation started from the approved plan on 2026-08-16. The production audit found generic app-shell metadata on every route, HTML fallbacks at /robots.txt and /sitemap.xml, HTTP apex returning 521, and HTTPS www returning 525.

Implemented one typed metadata source shared by four Vite HTML entries and runtime navigation. Home, Match, Discover, and Privacy now emit unique branded titles, descriptions, canonical URLs, Open Graph metadata, and one homepage WebSite JSON-LD record in the initial HTML. Added public robots.txt and sitemap.xml, real unknown-path 404 behavior, permanent legacy/trailing-slash redirects, and apex redirect configuration for HTTP/www variants. Added six metadata/crawler unit tests and a build/production eligibility verifier.

Verification passed: 36 frontend tests, TypeScript typecheck, ESLint including the verifier, production build with generated-output metadata validation, git diff check, both Caddy configurations, and a clean Impeccable detector. Browser checks covered all four routes at 1440x900, 390x844, and a 200% zoom approximation: each had one H1, one description, one canonical, correct runtime metadata, no horizontal overflow, and the expected homepage-only structured data.

PR #216 merged as 9346be2. Protected-branch CI and the production image build, security scans, and deployment all passed. Production Caddy was validated and recreated with the canonical host configuration. HTTP apex, HTTPS www, trailing-slash routes, and legacy routes now permanently redirect to the HTTPS apex; unknown paths return 404. The strict production eligibility verifier passed from the production host through Cloudflare, confirming four 200 HTML routes with unique metadata, valid robots.txt and sitemap.xml content/types, canonical consistency, redirects, and 404 behavior. One previously populated ARN cache edge briefly retained the old robots response under its pre-deploy four-hour TTL; the production origin and a fresh CDG edge served the valid file, so this transient edge object will expire without configuration changes. Search Console ownership was not available, so the approved equivalent production check supplied acceptance evidence.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Published route-specific branded search metadata, canonical URLs, WebSite structured data, robots.txt, and sitemap.xml for Ignite for Spotify. Consolidated duplicate URL variants, added real 404 behavior and repeatable build/production eligibility checks, deployed the result, and verified the canonical production site through Cloudflare.
<!-- SECTION:FINAL_SUMMARY:END -->
