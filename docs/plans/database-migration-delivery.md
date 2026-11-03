# Migration-aware database delivery

Approved development scope: TASK-42 then TASK-43, followed by a separately approved exact production procedure in TASK-44. No live database inspection/adoption, operator upgrade or deployment-contract activation is authorized by the development approval.

## Current behavior

EF Core owns application data access. Startup currently uses `EnsureCreated` outside production, checks a few required objects in production, and executes ad hoc DDL for official DLC and saved playlist results. There is no migration journal. `ignite.db` is application-owned; `hangfire.db` has a separate provider-owned schema.

The updater currently takes an online verified snapshot and attempts one image-only rollback after a failed switch. It cannot safely reuse that recovery policy after committing a schema migration. Whole-file fingerprints also reject ordinary edits to startup files without distinguishing migration compatibility.

## Approved stages

1. TASK-42 adds an unwired Infrastructure migration module, immutable embedded SQL, strict history and explicit legacy adoption. EF Core repositories and current production startup remain unchanged.
2. TASK-43 integrates versioned migration metadata into the signed release and updater. A migration deployment stops all backend writers before a fresh verified snapshot, then migrates before starting requests or background jobs. No broad fingerprint removal without replacement checks. The current publisher/operator protocol remains operational during preparation.
3. TASK-44 reviews the exact source/operator versions, observed schema-only baseline, maintenance window, adoption transition, backup proof and failure procedure before any live mutation. Routine eligible migrations subsequently need no production approval click.

## Migration module interface and test seams

The approved seams are the migration initialization/inspection interface over real SQLite files, and existing repositories/FTS behavior against the resulting schema. No tests mock migration internals or SQLite transactions. Process fixtures exercise that same interface to prove interruption handling.

The module owns path validation, exclusive migration execution, catalogue validation, history validation, one pending-batch transaction and fixed redacted errors. Callers explicitly select new-file initialization, existing-history upgrade or reviewed legacy adoption. Normal production startup must select existing-history upgrade; an absent file never authorizes creation. SQL and history remain Infrastructure concerns, not Domain dependencies.

Scripts use stable numbered logical identifiers independent of assembly names. SQL is strict UTF-8 without a BOM, uses LF line endings, and is hashed without substitution. Applied identifiers/checksums/timestamps are validated even when nothing is pending. Applied history must be an ordered prefix of the supplied catalogue. Modified, missing, reordered or duplicate migrations are errors.

A transaction is owned outside DbUp and committed only after the complete operation and journal validation succeed. Inspection of DbUp Core 6.1.1 at commit `41228ce747979fb52e1a59e3eec5823e6de869c8` shows its built-in single-transaction strategy commits on disposal unless a managed-command callback recorded an error; preprocessing or script-event failures can occur outside that callback. An outer transaction prevents those failures from committing earlier scripts. SQL cannot take over transaction control or modify the journal. Diagnostic/progress events contain bounded script identifiers only, never SQL errors or row data; an executed-script event is not proof of commit.

Legacy adoption is explicit and transactionally validates a reviewed schema including FTS definitions before adding baseline history. It never executes fresh-create SQL over an existing database, assumes `user_version`, silently repairs an unexpected schema or marks arbitrary pending migrations as applied. The separately approved metadata-only inventory identified production's historical shape before activation. The initial unmerged draft and a frozen, independently replayed legacy DDL fixture now reproduce that exact fingerprint, including its later default/column position and stored definition layout. This did not execute migrations against production or relax fingerprint checks. Raw inventory is private and only existing public schema identifiers/literals inform the source fixture; no production records go to CI or development machines. Actual adoption still requires the separately approved procedure and a fresh exact-baseline check.

## Failure policy

- No schema/history change, or a verified failed-batch rollback: restart the prior release only if its catalogue and operating assumptions remain valid.
- Migration committed but application unhealthy: preserve data and stop for a forward fix; an older catalogue missing a newly applied script is incompatible even if its business code accepts the new columns.
- Interrupted or uncertain outcome: inspect durable database history and deployment evidence before choosing recovery; do not infer a rollback merely from a failed process exit.
- No automatic down-migration, live backup restore, database initialization, journal reset, retention/pruning change or second image rollback.

The first automatic policy targets reviewed, bounded, backward-compatible migrations. Destructive changes, unbounded backfills and provider-owned Hangfire upgrades are outside this initial scope. A compatibility declaration is not proof of safety. Planned single-instance downtime includes quiescing writers, backup/restore verification, migration and readiness; it is not a zero-downtime design.

## Verification and preservation

Real SQLite tests cover fresh initialization, known-legacy adoption, unknown-schema refusal, repeat startup, upgrades, changed/missing/duplicate/order history, concurrent migration attempts, SQL/journal/event failures and process interruption. Existing repository and FTS tests exercise business-data access. Later container fixtures prove no requests or jobs start before migration success, committed-schema failure cannot launch an incompatible prior image, and all durable recovery/cleanup paths are bounded.

Preserve current CI/image/signature/source-map gates, secret boundaries, sole updater, replay/failed-release fences, database paths/volumes/UIDs, backup repository/password/retention/budgets, auxiliary services and private history. Do not broaden the project into a database/ORM/framework rewrite. No live automatic migration capability is claimed until the approved activation is independently verified.
