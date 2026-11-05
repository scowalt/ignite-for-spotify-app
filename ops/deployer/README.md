# Guarded deployment implementation

The schema-v2 path is active after the separately approved cold-WAL recovery, fresh
verified backup/restore and actual-timer baseline adoption. Automatic publishing/polling
are restored. The earlier failed artifact and original blocked evidence remain fenced
and audited; the already-used prior-service restart was not repeated. Historical success
is not permission to replay recovery helpers, reset history or clear failed-release fences.
Current operations and ledger paths are in the
[guarded delivery runbook](../../docs/operations/guarded-continuous-delivery.md).
The installer deliberately installs disabled units; any new installation still requires
its own preflight and controlled verification before activation.

## Transaction interface

`scripts/deployment_transaction.py` exposes `Deployment(root)`:

- `bootstrap(active, contract_sha256)` explicitly creates the first ledger, only
  after the installer independently verifies the existing runtime. It never replaces
  an existing ledger. The initial legacy publication may have no signed artifact;
  its source/images/order must come from the already-approved baseline evidence.
- `run(verified_release_or_none, runtime)` owns the exclusive lock and the entire
  transaction. Call it with `None` before fetching another release so interrupted
  work can recover even if registry/GitHub access is unavailable. Recovery also takes
  priority if a new candidate was supplied. Return codes are fixed, value-redacted.
- `status()` reads bounded, strict, private state. `active` means last committed,
  verified image set, not a claim that an interrupted runtime currently matches it.
- `attempt(artifact_digest)` reads retained completed-attempt evidence, including
  prior/candidate identities, failure phase and exact recovery receipt.

Private owner-only directories and files, exclusive flock, bounded strict JSON,
no-follow regular-file reads, atomic replacement and file/directory fsync protect
state. Missing/corrupt/unknown state is not silently initialized. A separate replay
high-water order survives rollback. Failed digests stay fenced. A rollback-started
record requires operator recovery; automatic polling cannot attempt a second rollback.
Cleanup after a committed deployment can be retried without deploying again.

Accepted attempt directories are named by the verified artifact digest. Runtime
adapters may retain non-secret preflight/rollback evidence there. `result.json` is
owned by the transaction core and is not an adapter scratch file. Plaintext database
copies and temporary tooling must be removed before any image mutation; all receipt
fields are allowlisted and bounded before they can enter the ledger. State and attempt
evidence must not contain secrets, rendered environment/configuration or user records.

## External runtime adapter contract

The adapter supplies these operations. Their implementation must use bounded commands
and fixed, redacted failures; the core deliberately never persists exception text.

| Operation | Required behavior |
|---|---|
| `preflight(release, prior, workspace)` | Inspect/pull/verify only; do not pause or recreate live services. Verify existing identities, exact candidates, contract/configuration, UID/platform, storage headroom and inactive Watchtower. Persist owned non-secret baseline and rollback evidence before returning. |
| `backup(workspace)` | Revalidate baseline/backup idleness, pause only the backup daemon, create a new bounded encrypted snapshot and verify its exact isolated restore. Never init/prune/unlock unknown storage or restore live data. Return the allowlisted recovery receipt. Cleanup ownership must remain discoverable if the process dies. |
| `cleanup(workspace)` | Idempotently stop/remove only owned temporary tooling and plaintext; preserve baseline/override/audit evidence. It must work after process death without relying on in-memory container IDs. Never broadly delete a workspace or other containers. |
| `switch_backend(release, workspace)` | Update only backend with no build/pull/dependency recreation; return only after exact image, readiness, account, database inode/ownership and invariant checks succeed. |
| `switch_dependents(release, workspace)` | Update only backup/frontend to the same release, with bounded health checks. |
| `verify(images, workspace)` | Verify the exact complete healthy set and unchanged database/mounts/Caddy/Alloy/Watchtower/configuration, including preserved backup access. No mutation. |
| `rollback(prior, workspace)` | One bounded image-only recovery; retain unchanged original containers and restart only a stopped known original backup when possible. Refuse unrecognized drift. Never restore a database, recreate volumes or restart unrelated services. |

The core requires the new snapshot to be within the transaction's time interval,
restored successfully, within the 256 MiB input / 1 GiB scratch / 512 MiB additional
remote budgets, and at most five minutes old immediately before image mutation.
The adapter must independently enforce the actual storage and identity facts, including
3 GiB free headroom; receipt validation is not provider or restore proof by itself.

Preflight refusal or interruption only abandons/cleans that attempt. It cannot
"roll back" over an unrecognized live runtime. Once backup/mutation may have begun,
recovery is recorded durably before the single recovery attempt. If rollback or cleanup
cannot be proven safe, stop and report the fixed outcome; do not weaken the guards.

## Active schema-v2 migration path

See [database migration operations](../../docs/operations/database-migrations.md) for the
full policy, native interface and transition journal. Schema-v1 state and policy continue
to use only the image-only path; neither is silently converted.

Schema-v2 state adds a reviewed host-contract/engine/Hangfire/legacy-baseline policy and
last committed catalogue summary. An explicit exact-idle-state upgrade preserves active,
high-water and failed-release fences. Candidate preflight verifies actual immutable image
metadata and dependency content before quiescing. The outer ledger persists intent before
stopping backup/backend and obtaining a fresh stopped-state backup/isolated restore.
`MigrationTransition` then owns durable SQL intent and unchanged/committed/uncertain outcome
evidence. It cannot admit images or commit a deployment on its own.

The migration runtime additionally supplies `quiesce`, `require_quiesced`,
`inspect_database`, `inspect_stopped_database`, `migrate_database`, `stop_migration_writer`,
`stop_database_writers` and `settle_database`. All use reviewed existing mounts and bounded
owned tooling. It inventories writable Docker data consumers, preserves auxiliaries and
configuration, and stops the owned backup tool before deleting plaintext. Backend and
dependent admission independently recheck database evidence and backup freshness.

Stopped inspections and quiesced backups explicitly handle sidecar-free WAL files without
relaxing read-only mounts. They may select an immutable URI only after proven writer
quiescence and absence of all SQLite sidecars; live readers retain normal WAL semantics.
See the database migration runbook for the conditions and native regression coverage.

Only unchanged, compatible database state allows one prior-image rollback. Committed or
uncertain outcomes never start an incompatible image; failed rollback and manual holds
latch. `check` holds the global deployment lock and cannot invoke recovery. Schema-v2
status/polling require the operator policy and ledger to agree exactly.

`install-deployer.py --migration-policy <private-reviewed-file>` validates the already
upgraded ledger and the immutable bundle/retained host configuration. It neither upgrades
state nor replaces a different operator, policy or unit, and never enables services.
The file contains only the four reviewed migration-policy hashes. The maintained publisher
uses v2 records. Changed operator/safety/dependency contracts still require separately reviewed
activation; routine eligible migrations use the installed policy without a new approval click.

## Recovery and signature adapters

`deployment_backup.py` ports the proven no-init/no-prune SQLite/Restic procedure.
Its temporary containers have a dedicated `ignite.deployer-tool` ownership label;
cleanup discovers that identity after process loss and checks the exact writable
scratch bind before deletion. Unknown/ambiguous ownership is refused. Only required
Docker and backup environment names reach child processes. The runtime adapter should
use the prior, known-good backup image for pre-deployment recovery, not assume a new
candidate backup implementation is already operationally compatible.

Credential-free Docker fixtures exercise a live WAL-mode synthetic database, new local
encrypted repository, exact-ID verified restore, missing-repository refusal and
restart cleanup. Fixture initialization is limited to temporary local repositories;
the production helper contains no initialization/pruning path. CI runs these fixtures
on its isolated hosted runner after building the backup image, with no production
credentials or network. Local rootless runs set `DOCKER_HOST` and
`IGNITE_BACKUP_FIXTURE_IMAGE` explicitly.

`release_signature.py` invokes a checksum-pinned Cosign executable with the fixed
immutable record reference and exact issuer/workflow/repository/ref/source policy.
It suppresses raw subprocess output and does not inherit runtime secrets or Cosign
trust overrides. Its invocation tests use an external executable fixture; these do
not prove live keyless signing/registry compatibility. The record loader authorizes the publisher before pulling, bounds the manifest, reads
only an immutable digest, then validates source-bound signature and successful workflow
evidence. It reads a bounded Docker image export in memory without creating/starting an
artifact container or extracting archive files onto the host.

## Driver and installation

`ignite-deploy.py` provides `bootstrap`, `status`, `check` and `once`. It requires a
private policy and an immutable reviewed operator bundle directory whose name matches
the policy source SHA. Bootstrap verifies the explicitly supplied existing baseline
without deploying; it never overwrites state. Check refuses interrupted transactions
rather than mutating under a read-only command. Once recovers old work before fetching
new release authority. Once compares the immutable registry pointer to the last
committed artifact before making workflow API calls: an unchanged verified release is
a no-op, not a repeated anonymous API request. New artifacts and explicit checks still
require full signature/source/successful-workflow verification. Workflow metadata uses
the existing owner-private GHCR credential, verified to have only `read:packages`,
against the fixed public-repository GitHub API endpoint. This avoids shared anonymous
rate exhaustion without a new credential, repository/write permission, CI secret or
stored token copy. Missing/unexpected credential storage or scope fails closed. Fixed outcome codes
suppress raw provider/credentialed errors.

`install-deployer.py` installs only an absent or exactly matching policy, bundle link
and user units. It verifies the pinned signer and systemd unit syntax but does not
start/enable either unit. The service uses existing project-scoped Doppler hydration;
no production secret enters GitHub or a new plaintext service configuration. The timer
runs one oneshot updater after boot and five minutes after the prior invocation finishes.

`deployment_runtime.py` preserves the existing source checkout, old bind anchor,
project/physical volumes, private configuration and data inode/ownership. A private,
domain-specific configuration HMAC uses the existing Restic password to compare
credential-bearing configuration across process restarts without storing its values or
a new key. The runtime uses only the prior known-good backup image for recovery proof.
All live auxiliary binds are checked; rollback first rejects unknown image/configuration
drift, then restores only changed/missing app containers or resumes the known original
backup. Existing physical volumes must already exist; no initialization/volume creation
is intended. Running backup repository access is rechecked with a bounded read.

Image preflight requires 5 GiB free before pulls, at most 1 GiB summed compressed layer
sizes and four times that size plus 3 GiB free as conservative unpack headroom. After
pulls and backup, 3 GiB must remain free. These estimates/budget checks are not filesystem
quotas or hard billing caps. Do not increase them or prune images/history automatically.

## Verification

The transaction tests use the real filesystem, locks and process-kill behavior with
an external runtime fixture. They cover durable success, concurrency, interrupted and
failed updates, cleanup retries, preflight drift, backup proof budgets/freshness,
failed-release fencing and evidence retention. They do not prove Docker, Restic, R2,
GitHub, Cosign, systemd or production compatibility by themselves. Separate native
fixtures and controlled live evidence now establish those paths for the installed
operator; the current runbook records them. Repeat relevant verification for a changed
operator/contract rather than treating historical evidence as blanket approval.
