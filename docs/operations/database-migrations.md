# SQLite migration foundation

The unmerged integration branch includes journaled startup, the packaged migration CLI,
versioned release/ledger policy and coordinated updater recovery. None is activated in
production; deployed main still uses the reviewed image-only updater. See
[the approved staged plan](../plans/database-migration-delivery.md) for offline verification
and the separately approved adoption/operator transition required before merging.

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
Limits are 4,096 scripts, 1 MiB per script and 16 MiB across the catalogue.

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

## Prepared migration-aware interface (not activated)

The integration branch adds `AutomaticUpgrade` for rehearsals and `VerifiedUpgrade`
for a release-bound target. Both require the exact prior schema/history and an explicit
positive database budget no greater than 256 MiB. A verified upgrade also checks the
published target schema before committing. Production startup's `requireReady` reads
complete history/schema; it never applies pending SQL.

The first automatic policy permits simple nullable appended columns, ordinary nonunique
indexes and new ordinary tables. It rejects data rewrites, old-object removal/renaming,
complex column constraints, expression/partial/unique indexes, and new trigger/view/virtual
table work. Native authorization is supplemented by old object/root/column checks and
per-operation HMAC comparison of existing row values. Random keys are erased after use;
row values and those private data hashes are never emitted or added to deployment state.
This is a conservative structural policy, not proof of arbitrary business compatibility.

An SQLite page limit bounds the logical database during mutations. Native tests verify
that over-budget index creation rolls back and that a new connection does not inherit the
fixture's lower limit. This is not a WAL/temp/filesystem quota: container limits, storage
headroom, writer cleanup and wall-clock deadlines remain deployment-controller duties.
See [SQLite limits](https://www.sqlite.org/limits.html) and
[`max_page_count`](https://www.sqlite.org/pragma.html#pragma_max_page_count).

`Data/Migrations/manifest.json` classifies the exact ordered script set as `baseline`,
`automatic-schema` or `manual`; only the first script may be the baseline. Build rehearsal
uses synthetic databases and native automatic checks, not a declaration alone. Manual
steps can be represented without authorizing their live execution. The catalogue hash is
SHA-256 of UTF-8 `ignite-database-catalogue-v1\n` followed by one
`id<TAB>sql-sha256<TAB>delivery<LF>` row per script. SQL checksums include original LF bytes.
The generated descriptor contains protocol, catalogue/baseline/target schema hashes and
script identities, not SQL or row data. Generate it once at build time, not by replaying
historical SQL on application startup. The publisher binds it to signed schema-v2 releases
and the consumer checks it against the exact immutable backend before downtime.

The separate `Ignite.Migrations` executable has no HTTP host, Hangfire workers or service
credentials. Prepared commands are `build-manifest`, `describe <manifest>`, `inspect`,
`apply <manifest>`, `adopt <manifest>` and `settle`. Database operations take bounded strict
JSON on stdin and emit only bounded metadata or fixed errors. `apply` requires exact
image/source metadata and prior state, rejects pending manual steps and stale retries,
and verifies the target inside the transaction. `adopt` only admits an explicitly reviewed
baseline-only release and cannot be used as a fallback after `apply` fails.

`settle` is deliberately **not read-only**: after the controller proves its owned migration
writer has stopped and holds the deployment lock, it can open the existing database for
SQLite's native interrupted-transaction recovery, check integrity and inspect history.
It never creates a missing database, runs pending SQL or restores an older backup. A real
process-kill fixture forces a hot rollback journal: `inspect` refuses it, and only explicit
`settle` restores readable committed state. The controller must never hide this operation
inside a read-only check or race it against an orphaned writer.

These prepared interfaces are not authorization to run against production. Offline
integration verification and the exact approved operator/database transition must precede
publication of the new protocol on main.

## Packaged startup and contained execution

The image contains `/app/migration-catalogue.json` and the CLI at
`/app/migrations/Ignite.Migrations.dll`. API and CLI publish into separate directories:
sharing one output directory can overwrite different resolved dependency versions and break
the application. The notice inventory covers both published dependency graphs, preserving
distinct versions and rejecting conflicting identities for the same package/version.

`DatabaseStartup.initialize` replaces ad hoc `EnsureCreated`/startup DDL. Development can
create a new journaled file or upgrade valid existing history; it cannot silently adopt an
old unjournaled database. In production, `Database:RequireExisting` cannot be disabled.
The packaged descriptor must match the embedded source plan, and read-only readiness must
verify complete history and the exact target before infrastructure registration, Hangfire
storage initialization or HTTP startup. Startup does not apply pending SQL, reconstruct the
schema by replaying history, repair drift, adopt a legacy database or implicitly settle a
hot rollback journal. Explicit settlement remains a controller recovery operation after
writer shutdown. Once readiness succeeds, startup maintains WAL and enables foreign keys
on application connections. Relative development file paths are normalized; memory/URI
startup databases are not supported.

`MigrationTool` is a container adapter, not release authorization. Its caller must first
verify the signed release, immutable backend identity, source metadata, approved physical
volume and durable deployment intent. It accepts only an immutable local image ID and
fixed `inspect`, `apply`, `adopt` or `settle` commands against `/data/ignite.db`. It passes no
runtime service credentials, uses no network, runs as UID/GID 999, and confines writes to
the existing data mount and bounded temporary storage. Inspection mounts data read-only.

The adapter bounds stdin/output and execution time, CPU, memory, process count, temporary
storage and individual file size. These are not an aggregate filesystem quota or a waiver
of backup budgets/freshness. Ownership labels, exact image/command/user/mount identity and
stopped-state checks govern cleanup. A client timeout explicitly stops the owned container
before removing it; a new controller instance can perform the same cleanup after a crash.
Unknown ownership or extra mounts stop cleanup rather than touching another container.
Neither a clean process exit nor a successful cleanup is proof of migration outcome: the
controller must still inspect durable history before admitting images.

## Signed dependency compatibility (not activated)

Schema-v2 records require both `hangfire_sha256` and `migration_engine_sha256`. The
publisher copies three bounded regular metadata files from the exact unstarted backend
image: its catalogue descriptor, API dependencies and independently published CLI
`/app/migrations/Ignite.Migrations.deps.json`. Neither metadata extraction nor release
creation runs the backend or receives production service credentials.

The engine identity binds the CLI target framework and the resolved package versions,
NuGet SHA-512 content and dependency edges reachable from DbUp, the Microsoft SQLite
provider, all SQLitePCLRaw packages (including native assets) and FSharp.Core. Missing
required native packages, duplicate identities and unresolved/inconsistent edges fail.
Unrelated packages outside that closure do not affect this identity. This complements,
not replaces, source/operating-contract checks and actual image verification; it is not
a declaration that arbitrary runtime or package upgrades are compatible.

`validate_release` accepts migration metadata only with an explicit
`MigrationDependencyPolicy` containing independently reviewed engine and Hangfire pins.
A boolean opt-in alone is insufficient. A changed identity or a schema-v1 downgrade is
refused; never derive the policy pins from the incoming release to make it pass. The
per-attempt transition journal retains both identities. A schema-v1 operator still supplies
no migration policy and refuses schema-v2 releases. The reviewed schema-v2 operator supplies
the pinned identities explicitly, requires a matching versioned ledger and separately
verifies the pinned host configuration contract. No policy or ledger upgrades happen on
ordinary polls, status or candidate checks.

## Durable database-transition journal (not activated)

`migration_plan.py` validates complete prior history/schema and the immutable candidate
catalogue before forming a transition. Applied identifiers, checksums and delivery classes
must remain an identical prefix; pending manual steps and a different target for an
unchanged catalogue are refused. Legacy adoption needs the separately approved exact hash
and a baseline-only candidate. Target history must preserve all prior timestamps.

`MigrationTransition` records bounded private `migration.json` evidence in the existing
artifact-specific attempt directory. Preparation binds it to the authenticated release's
artifact, source, backend image, contract, engine/Hangfire identities and catalogue summary. The
caller still owns signature/policy verification, the global deployment lock, physical
volume/configuration checks and actual encrypted backup/restore verification. A per-attempt
lock supplements, but does not replace, global deployment serialization.

Before SQL, the journal requires fresh verified recovery evidence within the existing
budgets, reserves 180 seconds of the five-minute freshness window, rechecks quiescence and
exact before metadata, then fsyncs migration intent. Success requires the writer stopped
and an independent inspection; a process return value alone is not a commit receipt.
Expired recovery after migration cannot produce an image-admission success. The outer
controller must recheck freshness and runtime compatibility before each admission.

| Durable state | Meaning |
| --- | --- |
| `prepared` | Bound plan; no migration execution authorized yet |
| `migration_started` | Intent persisted before possible SQL; never replay on restart |
| `verified` | Exact expected database observed; not application health or deployment commit |
| `recovery_started` | Stop all known writers before explicit native settlement and inspection |
| `unchanged` | Exact before schema/history retained; outer controller must still prove prior-image compatibility |
| `committed` | Target history/schema committed; never treat as prior-image rollback permission |
| `uncertain` / `blocked` | Unexpected state or incomplete recovery; stop for manual handling |

Committed, uncertain and blocked recovery outcomes latch rather than repeatedly mutating
on polls. An unchanged observation is rechecked if recovery is requested again. The journal
neither switches images nor restores a database. The existing image-only driver refuses
any attempt containing this journal instead of accidentally applying its old rollback path.
The schema-v2 outer ledger dispatches explicitly to this path; schema-v1 state never does.

## Coordinated updater path (not activated)

Schema-v2 ledger state preserves active release, replay high-water order and failed-digest
fences, adding reviewed migration policy and the last committed catalogue summary.
`Deployment.upgrade_migrations` is an explicit idle-ledger, exact-state-fingerprint operation
for the separately reviewed activation procedure; it is never invoked by polling or the
installer. It rejects pending work, stale evidence, repeated conversion and invalid pins.
The fingerprint is SHA-256 of sorted, compact JSON from `status()`, not an authorization
in itself. Save private pre-transition evidence in the approved procedure.

Normal execution verifies/pulls first, binds actual immutable catalogue and both dependency
graphs, records quiescing intent, stops the known backup daemon and backend, then verifies
fresh encrypted backup and isolated restore of the stopped state. Data-consumer checks
reject unexpected writable volume/overlapping bind consumers, including stopped containers.
Unknown bind aliases must resolve within a bounded probe; unresolvable writable binds and
unknown nonlocal/option-backed volumes fail closed rather than assuming isolation.
Only existing inspected physical paths are bound into migration and backup tooling; no
new data/state volumes are created. Host configuration, auxiliary identities, UID/mode/inode,
space budgets and retained bind anchors remain guarded.

The backup helper is stopped before owned plaintext cleanup, including recovery from an
interrupted attached command. Migration intent is durable before CLI execution. Database
state and backup freshness are checked again before backend and dependent image admission.
Only complete image health, runtime preservation and matching database evidence can commit
the new active release/catalogue. A committed ledger retries cleanup without re-migrating.

Any post-quiescence interruption first stops known writers and classifies the database.
Only exact unchanged history/schema with compatible prior catalogue may enter one durable
image-only rollback. Committed adoption/expansion followed by health failure leaves writers
stopped for a forward fix; uncertain/blocked outcomes and interrupted rollback latch for
manual handling. No database restore or SQL replay is a recovery fallback. A read-only
`Deployment.check` holds the same global deployment lock and never calls recovery.

The installer accepts an explicit private `--migration-policy` file only when its host hash
and already upgraded ledger match the immutable bundle. It still refuses replacement of a
different policy/operator/unit and never starts/enables services. The publisher in this
branch requests schema-v2 records. Therefore merging before the separately approved
operator/ledger/adoption procedure is ready would block the existing v1 updater; keep this
draft unmerged until that transition is reviewed.

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

The image-verification workflow also runs real, network-isolated container fixtures:
an unadopted synthetic database must refuse startup without creating Hangfire storage;
explicit adoption must let the actual packaged API become healthy. A separate test-only
writer image holds an actual native SQLite transaction or pauses after commit. Killing the
controller proves its daemon container is still running; a new adapter must stop/reap that
container before settlement. Timeout, uncommitted rollback and commit-before-controller-death
are verified separately. The fixture executable is never copied into a published app image.

Run with `IGNITE_MIGRATION_FIXTURE_IMAGE=<fresh-backend-image>` and
`IGNITE_MIGRATION_WRITER_FIXTURE_IMAGE=<test-only-writer-image>` when invoking
`python3 -m unittest discover -s scripts -p test_migration_startup.py -v`.
Build the latter using `scripts/fixtures/Dockerfile.migration-writer` and an explicit
`BACKEND_IMAGE` build argument. Fixtures create/remove only uniquely labelled synthetic
volumes and containers, expose no host port and pass no runtime credentials.

Additional real file-backed SQLite/process tests exercise the durable transition journal:
killed uncommitted and committed writers, no replay after restart, concurrent exclusion,
unknown history, failed writer shutdown, backup bounds/expiry and failed durable writes.
Their synthetic backup receipts test admission policy, not actual encrypted backup I/O.

Outer-ledger tests cover explicit upgrade/fence preservation, baseline adoption, committed
schema plus health failure, compatible no-op rollback, killed migration, cleanup restart,
policy mismatch and interrupted rollback. External Docker-seam tests cover the actual
runtime orchestration, metadata binding, unexpected writer refusal, admission and rejection
of incompatible rollback. Installer tests use the real checksum-pinned signer binary but
fixture system commands, proving installation does not enable/start units.

These offline tests do not establish live R2 access, the current production baseline,
real schema-v2 publication or activation. Those require the approved production procedure. Keep existing signing,
image/security/notice gates, backup credentials/retention/budgets and deployment fences.
