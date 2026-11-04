---
id: TASK-42
title: Introduce journaled SQLite migrations with explicit legacy adoption
status: Done
assignee:
  - '@pi'
created_date: '2026-11-03 15:51'
updated_date: '2026-11-03 21:57'
labels:
  - backend
  - database
dependencies: []
references:
  - backend/src/Ignite.Infrastructure/DependencyInjection.fs
  - backend/src/Ignite.Infrastructure/Data/IgniteDbContext.fs
  - backend/tests/Ignite.Infrastructure.Tests/DatabaseTests.fs
documentation:
  - docs/operations/database-migrations.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Provide a tested migration foundation for Ignite’s existing SQLite application database without replacing EF Core data access or changing live startup yet. Current startup uses EnsureCreated and ad hoc DDL without durable migration history. Follow the workspace DbUp/immutable-SQL standard through a project-specific legacy-adoption design; never guess a baseline or expose production data to CI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A DbUp-based migration module in Infrastructure uses stable embedded SQL identifiers and SHA-256 history, validates applied history even on no-op starts, and rejects modified, missing, duplicate or out-of-order applied migrations.
- [x] #2 Each pending batch and its journal updates commit in one explicit SQLite transaction; real database tests prove schema/data/history rollback on execution, journal, interruption and concurrency failures.
- [x] #3 Fresh synthetic databases are supported, while missing ordinary-production databases and unknown unjournaled schemas are refused; explicit legacy adoption validates a reviewed schema, including FTS objects, and preserves existing data.
- [x] #4 EF Core repositories and existing application behavior are preserved; migration initialization has a tested pre-serving interface, but current production startup and delivery remain unchanged until separately reviewed activation.
- [x] #5 Credential-free tests cover repeat startup, upgrades, schema mismatch, legacy adoption, existing repository/FTS behavior and refusal paths; scripts and diagnostics expose no production records or credentials.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Confirm the existing schema and startup/FTS behavior using source and synthetic databases, and use the available pinned .NET 10.0.402 SDK without changing global tool defaults. Record the explicit legacy-schema validation/adoption design before implementation.
2. Implement the Infrastructure migration module with pinned DbUp, stable embedded SQL identifiers, strict checksum/order history and a single transaction for each pending batch plus its journal. Keep EF Core for repositories and keep production startup wiring unchanged.
3. Add real SQLite integration/failure tests through the migration interface for fresh creation, explicit known-legacy adoption, repeat startup, upgrades, schema/data/journal rollback, process interruption, concurrent attempts and invalid history; retain existing repository/FTS coverage.
4. Run backend and migration tests, formatting, dependency/license/security checks and comment/secret checks. Review the implementation and document the startup integration contract and safe adoption procedure.
5. Stop for plan approval before coding. This foundation does not authorize live database access/adoption, updater changes, retention changes, service stops or deployment-contract activation; prepare those separately after the offline implementation is proven.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Initial investigation: production startup in DependencyInjection.fs currently validates core schema and performs ALTER TABLE / CREATE TABLE IF NOT EXISTS directly; there is no journaled migration catalogue. The application and Hangfire use separate database files, so ownership must remain explicit. Existing deployment takes a verified online backup then performs backend-first image replacement, and its recovery path always attempts image rollback; that behavior cannot be reused unchanged after a committed schema migration. Workspace migration standard specifies DbUp, strict immutable checksums, explicit legacy adoption, one transactional batch, single-instance planned downtime and no automatic live restore.
Tool check: Docker and Backlog available. Default dotnet shim cannot select its configured version in this shell, but the existing private dotnet-10.0.402 installation runs successfully; use that explicit pinned SDK for development. No application/runtime code or production state changed. Awaiting owner confirmation of the staged development plan.

Owner approved the staged development plan. Proceeding with the approved migration initialization/interface and real SQLite persistence/repository seams; production remains untouched until a separately approved exact adoption/upgrade procedure. Foundation stays unwired from production startup so existing image-only delivery remains operational.

Development underway on feat/journaled-sqlite-migrations; startup wiring and production remain unchanged. Baseline Infrastructure tests: 19 passed. New migration-interface tests reached 18 passing through observed red/green cycles for initialization/no-op history, changed/missing/reordered catalogues, strict encoding/admission and schema/data/history rollback. Native SQLite authorization now prevents migration SQL from committing an outer transaction or rewriting migration history; a regression first reproduced partial persistence through COMMIT.
Pinned DbUp Core 6.1.1 and SQLite provider 6.0.4; inspected exact upstream commits. DbUp single-transaction disposal can commit earlier statements when later preprocessing/event errors occur outside its command callback, so the module owns the outer transaction and commits only after full success. Remaining foundation work includes embedded application schema, explicit legacy validation/adoption, journal/event/process interruption/concurrency tests, broader regression/security/license checks and review. No criteria claimed complete yet.

Foundation implemented and self-reviewed with 43 real SQLite migration cases; all 137 backend tests pass, no skips. Coverage includes native transaction/journal protection, unchanged no-op history, exact source-derived schema-only adoption and refusal, repository/session/snapshot/job/FTS behavior, an injected journal timestamp-source error after an earlier successful script, callback failure outside DbUp command management, deferred-constraint commit failure, concurrency, and process-kill rollback. Added strict identifier anchors, embedded NUL refusal and final-component symlink rejection after failing regressions. The malformed-NUL experiment hit the bounded test-harness deadline before validation was tightened; no owned test process remained.
Fantomas 7.0.6 checks pass; comment policy checked 307 files with zero violations; NuGet reports no vulnerable packages for the backend graph; mechanical notice collection covers 52 components with zero gaps. Production contract remains exactly 417fe8060e7156e73c308c2148e0d282f9cadbbaaf952e7b0097744a31666d5f. Startup/ORM/updater/workflow/production unchanged. Source-derived EF/FTS adoption is proven with synthetic data only; historical production schema may differ and remains uninspected/unapproved. Protected review/CI remains to be completed before marking the task Done.

Draft PR #21 at exact code head 96c185237e2d2e6b54111800e18e3cc3668d368a passed hosted CI 41679797925 and comment-policy runs 41679797946/41679788805, including actual image/security/notice/backup/infrastructure gates and native fixtures. PR remains unmerged; no production release or state change occurred. The one timed-out adversarial-NUL test left only an owned empty synthetic database and rollback journal; those exact files were removed after confirming provenance, with no test processes or unrelated sessions touched.

After the separately approved metadata-only inventory, the initial unmerged/unactivated draft was corrected to reproduce the observed legacy fingerprint 91520ea3d23a8c812dea171d9bf5194e5f896069b3b540ffbab723e7b2ffa6a5 exactly. Red/green regression first observed the prior source-derived mismatch. Changes preserve the known appended official_dlc DEFAULT 0, public legacy playlist DDL and FTS definition layout. The standalone index terminator reproduces stored whitespace without source trailing whitespace; matching was not normalized or weakened. No live/persistent deployed migration was edited or executed.
Added a frozen test-only legacy DDL replay and synthetic old-schema row fixture, independent of future EF model generation. Adoption tests preserve that data through baseline adoption and subsequent catalogue upgrades; fresh creation reproduces the same exact fingerprint. Additional default-change refusal guards against broadening adoption. All 139 backend tests pass (45 migration cases), no skips, with formatting and diff checks clean. Raw inventory stays private; no unknown identifiers or non-public SQL literal values were used in source.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added an unwired DbUp-based SQLite migration foundation while preserving EF Core repositories and existing startup/delivery behavior.

- Embedded immutable numbered SQL, stable resource IDs, strict encoding/input/history checks, and one externally owned SQLite transaction for each pending batch and journal.
- Native authorization blocks transaction escape, attached databases, PRAGMAs and journal modification; diagnostic failures are fixed/redacted.
- Explicit schema-only legacy adoption now targets the exact metadata-reviewed production shape. The initial draft was corrected before any live adoption; no deployed migration or Git history was rewritten.
- Frozen legacy DDL and synthetic row fixtures do not depend on future EF models. Real concurrency/process-kill, journal/event/commit failure and repository/FTS preservation tests remain.

Verification: all 139 backend tests pass, including 45 migration cases; no skips. Prior exact foundation heads passed hosted image/security/notice/native gates; current baseline revision requires refreshed exact-head CI before merge. Runtime compatibility fingerprint remains unchanged.

The runner remains unwired and the PR unmerged. Metadata-only inspection was separately approved and performed without user rows, credentials or database/service changes. Actual adoption/operator activation remains unapproved.
<!-- SECTION:FINAL_SUMMARY:END -->
