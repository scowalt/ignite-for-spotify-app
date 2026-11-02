---
id: TASK-36
title: Restore scoped production backup access
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 19:57'
updated_date: '2026-11-02 21:18'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Diagnose the R2 Unauthorized response blocking the approved runtime cutover. Repair only the existing private backup-bucket access if necessary; preserve its scope and credentials unless replacement is proven necessary. Keep backend/frontend unchanged during recovery and resume the separately approved cutover only after fresh recovery checks pass.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A bounded value-redacted probe reproduces and identifies the actual backup-access failure using authoritative metadata or independent client evidence.
- [x] #2 Any necessary credential replacement preserves exact existing bucket/read-write scope, is transferred securely into Doppler, and refreshes only the backup container without exposing values or changing retention, repository format or bucket identity.
- [x] #3 Existing-repository access and storage accounting pass with no initialization/pruning or broader credentials; all other production identities and publisher fences remain intact.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the minimal signed metadata request and rank credential lifecycle, scope/conditions, and client/transport hypotheses. Read only the known token metadata before any mutation.
2. Establish the cause with authoritative provider or independent-client evidence. Do not rotate blindly or use broader credentials for backup-data access.
3. If required, replace only the same private-bucket read/write credential, securely update Doppler, refresh only the backup container, and prove access before retiring anything. If administration is unavailable, stop for secure human input.
4. Verify storage accounting and existing-repository reads, preserve all other service identities/fences, and revalidate the known-owned prepared checkout/operator state. Resume TASK-35 only under its existing guarded cutover contract.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner approved scoped recovery: diagnose first; same-scope credential replacement only if required, secure Doppler update and backup-only credential refresh permitted. No broader permissions, bucket initialization/pruning or backend/frontend recovery side effects.

- Minimal HeadObject probe remains red (401) from production and the independent development host; clock skew ruled out. A real Botocore 1.40.75 S3 client with the same existing pair independently returns 401, so this is not only the custom verifier.
- Cloudflare administration token self-verification succeeds and reports active; GET of the exact existing backup bucket succeeds. Both known account-token and user-token metadata endpoints deny the available administration token (403, code 9109). Bucket existence is confirmed, but token lifecycle/scope metadata and automated replacement are unavailable through this operator credential. No scopes were broadened and no token mutation was attempted.
- BLOCKED on human Cloudflare token administration. Prepared a three-stage ephemeral wizard: review current token, retrieve/create only an Object Read & Write pair scoped to ignite-for-spotify-db-backups, then use bb secret request for secure key-pair handoff. Do not delete old token before validation; no secrets in chat or terminal prompts.
- Wizard lives in private thread storage, preserves the shared template library, passes bash syntax checking and authored-stage linting; existing unused template helpers produce SC1087/SC2317 findings only. The wizard was not run by the agent. No Doppler/service/state changes occurred during this recovery.

Remote-friendly handoff: user should use Cloudflare in their own browser; no remote terminal wizard is required. Agent opened the BB secure two-field form with the exact remote destination, but it timed out. Do not assume submission; wait for the user to say ready and reopen the same secure form. No keys should be sent in chat.

- The secure form supplied a pair confirmed by the user as Object Read & Write for only the existing bucket. Independent SDK HeadObject returned 200; exact-bucket inventory succeeded. The old pair failed while the submitted pair works; expiry/revocation specifics remain unproven because token administration metadata is denied.
- Atomically updated only R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY with original-value guards; private readback matched, all non-target values/names and repository/encryption password were preserved. No applicable Doppler syncs/webhooks.
- A pre-service guard initially stopped on Docker mount-array ordering only. Corrected order-independent comparison retains every mount attribute and rejects real changes in tests; original evidence is preserved.
- Existing Watchtower paused under cutover approval; only backup credentials refreshed, preserving the original backup image payload, mounts/identity settings and all backend/frontend/Caddy/Alloy container identities. Existing Restic repository reads work before/after refresh.
- Fresh cutover backup and isolated verified restore then succeeded, proving actual read/write recovery without init/prune/retention or broader credential changes. Both publisher fences remain intact.

Secure handoff values were privately rechecked against Doppler and the owned temporary credential file was removed after successful runtime backup access and fresh snapshot/restore proof. No provider-token deletion or admin permission expansion was attempted; original token lifecycle details remain unavailable.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Restored production backup access using the user-confirmed, single-bucket replacement pair.

- Independent old/new probes isolated rejection of the old pair; no unsupported claim of expiry/revocation.
- Updated only two Doppler fields atomically and refreshed only backup credentials while preserving its original image and all non-target secrets/services.
- Retained exact bucket/repository/encryption identity, paused the existing updater under the cutover approval, and verified real Restic access plus a fresh encrypted snapshot and isolated integrity-checked restore.
- No bucket initialization, pruning, retention change, broader permission request or publisher enablement. Runtime cutover can continue under its existing approval.
<!-- SECTION:FINAL_SUMMARY:END -->
