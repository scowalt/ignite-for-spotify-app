---
id: TASK-3
title: Serve the Ignite favicon across the site
status: Done
assignee: []
created_date: '2026-07-22 18:33'
updated_date: '2026-08-09 15:23'
labels:
  - bug
  - frontend
  - branding
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Browsers continue to show the default browser icon instead of Ignite branding, including after refresh.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Supported browsers display the Ignite favicon on every application page
- [x] #2 The favicon asset and page metadata remain correct after a hard refresh and direct navigation
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Resolved upstream by PR #183 (commit 92b7f05, merged 2026-08-08): frontend/public/favicon.svg was missing, so Vite never served the asset nor copied it into the production build and browsers fell back to the default icon. The PR added the Ignite flame mark (gradient flame on brand dark tile), a cache-busting ?v=1 on the icon link, and a theme-color meta. Verified upstream: build emits dist/favicon.svg, preview serves HTTP 200 image/svg+xml, typecheck/lint pass.

Note: this worktree independently produced an alternate favicon set (green flame SVG + ICO/PNG fallbacks); discarded in favor of the upstream design.
<!-- SECTION:FINAL_SUMMARY:END -->
