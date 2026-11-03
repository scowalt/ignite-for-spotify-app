# SQLite migration foundation

This module is implemented for offline preparation, not enabled in production startup.
The current `InitializeDatabaseAsync` path and image-only updater remain unchanged.
See [the approved staged plan](../plans/database-migration-delivery.md) for the remaining
signed-release/updater integration and separately approved production adoption.

## Ownership and interface

Infrastructure owns migrations for `ignite.db`; EF Core continues to own ordinary
repository access. Hangfire's separate database is not adopted by this module. Domain
and application interfaces gain no migration-framework dependency.

`ApplicationMigrations.catalogue()` reads embedded, numbered SQL using fixed resource
logical names. `DatabaseMigrations.run path mode catalogue` is the initialization
interface. `runObserved` additionally takes a `TimeProvider` and a callback receiving
each completed-but-uncommitted script identifier. It exposes neither SQL output nor
row data. Callback failure aborts the pending transaction; callbacks are not commit
receipts. `inspect path` reads schema fingerprints and bounded journal metadata without
applying changes. Inspection alone does not establish compatibility with a catalogue.

Modes are explicit:

- `CreateNew`: create a new file exclusively. An existing file is never overwritten.
- `UpgradeExisting`: require an existing file with valid, nonempty migration history.
  A missing file or an unjournaled legacy schema is an error, not an initialization case.
- `AdoptLegacy expectedSchemaSha256`: require an existing unjournaled database, an
  independently reviewed expected schema fingerprint and exactly the initial baseline
  script. The observed schema must also match the baseline recreated in isolated memory.
  A native SQLite authorization guard rejects business-data writes during that baseline
  rehearsal. Only baseline history is inserted; existing business data is not copied,
  rewritten or silently repaired. Pending migrations cannot be marked as already applied.

Paths must be absolute and not directory/file symlinks at the final path component.
The deployment controller remains responsible for approved paths, mount ownership,
filesystem identity, capacity and protecting the containing directories from replacement.
Normal application startup must never choose adoption as a fallback after upgrade fails.
A failed new-file initialization can leave its owned empty file; it is not automatically
removed or repurposed. Production initialization is outside this feature's normal path.

## Catalogue and history

Scripts use `NNNN_lower_case.sql` identifiers, with unique increasing nonzero numbers.
Identifiers do not depend on assembly or namespace names. SQL is strict UTF-8, without
a BOM, CR characters or embedded NULs; `.gitattributes` fixes SQL line endings to LF.
There is no variable substitution, schema stripping or arbitrary preprocessor chain.
Limits are 4,096 scripts and 1 MiB per script.

`__ignite_migrations` records contiguous positions, identifiers, exact SQL SHA-256 values
and UTC timestamps. The journal definition and metadata are validated, including no-op
starts. Applied history must be an identical ordered prefix of the supplied catalogue.
Changed, missing, reordered or duplicate migrations are rejected. Applied SQL is immutable;
corrections belong in new forward migrations. A prior application artifact missing a new
journal entry is not a compatible rollback target, even for additive schema changes.

A read-only inspection returns a hash of ordered SQLite schema definitions, including
FTS and trigger definitions but excluding the migration journal and SQLite-owned objects.
It does not emit those definitions or user records. A corrupt or empty journal is refused,
not interpreted as permission to adopt again. The fingerprint is deliberately exact:
formatting or legacy schema variants can differ. A separately owner-approved read-only
metadata inventory identified the existing production shape as
`91520ea3d23a8c812dea171d9bf5194e5f896069b3b540ffbab723e7b2ffa6a5`. The initial
unmerged/unactivated draft was corrected to reproduce that exact shape, including the
appended `official_dlc` default and legacy playlist/FTS definitions. No deployed migration
was edited, no live schema changed, and raw metadata remains private. A frozen test-only
legacy fixture replays the old public DDL sequence instead of regenerating from future
EF models. Tests seed synthetic data and prove exact adoption and repository preservation.
Unknown shapes still stop; no fingerprint matching was weakened. The metadata inventory
is not approval to adopt production. Recheck the exact baseline in the later approved
procedure, and never treat a freshly observed hash as automatic authorization.

## Transaction and failure behavior

The module owns one immediate SQLite transaction around history validation, the entire
pending batch and journal writes, committing only after successful validation. DbUp Core
6.1.1 and its SQLite provider 6.0.4 perform script orchestration inside that transaction;
DbUp does not own the commit. This also covers errors outside its managed-command callback,
where the built-in transaction strategy alone would not establish full-batch rollback.

Native SQLite authorization prevents migration SQL from taking over transaction control,
attaching databases, running PRAGMAs or modifying the reserved migration journal. SQL
literals containing similar words or variable-like text remain literal. These controls do
not prove that arbitrary business-data transformations are backward-compatible or harmless.

A one-second SQLite lock-wait timeout bounds concurrent writer admission; it is **not**
an overall execution deadline for SQL. The migration-aware controller must enforce a
separate bounded process deadline and quiesce all writers. Error output is fixed/redacted;
raw SQL/provider exceptions and their inner exceptions are not propagated. A failed or
terminated process alone does not establish whether commit happened: recovery must inspect
durable history before selecting a prior image or a forward fix. No down-migration, live
restore, repository initialization/pruning or automatic operator upgrade is provided.

## Verification

Real file-backed SQLite tests cover initialization/no-op startup, catalogue/history drift,
encoding/admission failures, schema-only legacy adoption/refusal, repository and FTS
behavior, concurrent writers, journal timestamp-source failures, script-observer failures,
deferred-constraint commit failures and process termination after an uncommitted script.
They verify schema/data/history preservation without mocking migration internals.
The process fixture is only in the test assembly and is never shipped in the backend image.
All data is synthetic; no production snapshots, sessions or credentials are test inputs.

Run the repository's pinned SDK:

```sh
dotnet test backend/tests/Ignite.Infrastructure.Tests --filter FullyQualifiedName~DatabaseMigrationTests
dotnet test backend/Ignite.slnx
```

These tests establish the migration module, not live R2 recovery, readiness gating,
image rollback compatibility or activation. Those require the remaining migration-aware
release/controller work and an approved production procedure. Keep existing signing,
image/security/notice gates, backup credentials/retention/budgets and deployment fences.
