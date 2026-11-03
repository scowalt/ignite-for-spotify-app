# Runtime cutover plan: verified public images

**Historical cutover executed successfully on 2026-11-02.** Current deployments and
active overrides are governed by the [guarded delivery runbook](guarded-continuous-delivery.md),
not this completed one-shot procedure. The paused automation and override paths below
record the original cutover milestone, not the current operating state. All three
app services run the verified `4ef6b03` digests below. Public frontend, internal
readiness, backup health/access, source identity and preserved data/mount checks passed.
No image rollback was needed; Caddy and Alloy retained their identities and binds.

A separately approved, user-confirmed bucket-only R2 credential replacement restored
backup access. Only those two Doppler fields and backup credentials changed; the
repository, encryption password and other secrets remained unchanged. Fresh encrypted
backup, exact-ID verified restore and SQLite integrity checks passed within budget.
Temporary tooling, plaintext and the credential handoff file were removed.

The production source checkout is `/home/scowalt/Code/ignite-for-spotify-app`, pinned
to `4ef6b0380b2474be921fa46ae31b45ccab4782b8`. The active non-secret image override is
`/home/scowalt/.local/state/ignite-cutover-4ef6b03/images.compose.json`; the same directory
holds the rollback override and restricted execution evidence. Continue using the
explicit project/base-path controls below. Do not reuse completed one-shot phase helpers.

Watchtower is stopped and both publishers are fenced. Source policy still desires true
while the live publish flag is false: preserve that intentional drift until separately
approved activation. The procedure below records the approved scope, not permission to
repeat it. Continuing CD and the wider integration migration remain incomplete.

## Decision and boundaries

Use one guarded maintenance window to:

1. Prepare the public production checkout and persistent, non-secret digest overrides.
2. Pause the existing Watchtower and coordinate the existing backup daemon.
3. Create one fresh encrypted recovery snapshot and verify an isolated restore.
4. Recreate only backend, backup and frontend at the verified digests, with health gates.
5. Leave Watchtower stopped and both publishers fenced. If a service switch fails,
   perform at most one explicitly preapproved image-only rollback to the recorded old
   digests, then stop. Never restore the database automatically.

Expect a short interruption during app-container recreation; backup/restore checks
happen before that interruption. No zero-downtime guarantee is made. Caddy and Alloy
stay running. Preserve unknown processes, old checkouts/history, physical volumes,
credentials, DNS, ports and backup identity. No `compose down`, whole-stack update,
force recreation, volume removal, broad chown, image pruning, repository initialization,
retention change, database migration, credential rotation or controller activation.

## Verified release

Source revision: `4ef6b0380b2474be921fa46ae31b45ccab4782b8`.
Release run: [41491892742](https://github.com/scowalt/ignite-for-spotify-app/actions/runs/41491892742).

| Service | Immutable image under `ghcr.io/scowalt/ignite-for-spotify-app/` |
| --- | --- |
| backend | `backend@sha256:51beddd2ed0cfba81f04cd43fbfaa7b0888744a84457a01b444727badedb4800` |
| backup | `backup@sha256:ab1fdcbd8751b38be2de98af5df2a81fe5ead611c3af900df07ad56e119ece87` |
| frontend | `frontend@sha256:7b5552579ffa93b582de5633aca57ed4d06dda8f664f43059e0adcd1814142d1` |

All three passed actual release-image security/notice gates and production pull,
source/revision and linux/amd64 identity checks. Backend UID/GID 999/999 matches the
existing data directory/database. An unstarted inspection container was removed.
GlitchTip accepted the isolated frontend source-map bundle; server-side processing
and end-to-end symbolication are not yet independently proven.

Read-only planning on 2026-11-02 additionally found:

- All 33 selected backend source/configuration files match deployed revision
  `502843683cb4e85392f3ea0766ed4472cc026ae7`; this release introduces no new backend
  schema-migration source. Frontend/backup include already-reviewed intervening changes.
- Hydrated public Compose configuration passed the production validator. Its three
  app services have no changed managed environment values or removed runtime overrides.
  Comparison occurred only in private production-side memory; no values were printed/saved.
- With the existing old `docker` directory as `--project-directory`, all Caddy/Alloy/
  Watchtower bind paths match. Compose version was 5.1.3.
- Database size was 71,483,392 bytes, mode 0600, UID/GID 999/999; free space was about
  16.2 GB. Refresh these facts before acting.
- The new production checkout path is absent. Watchtower targets exactly the three
  app containers, polls every 30 seconds and enables image cleanup. Backup-on-start is false.

## A. Preflight and operating checkout

Keep old Deploy disabled and new publication false throughout. The source publication
policy currently desires true; do not run a live IaC apply during this cutover.

Refresh exact container/image/mount/health/network metadata, backup activity, disk
headroom and availability of the privately recorded immutable rollback images.
Stop for an unrecognized writer/updater, changed secret/configuration, image identity,
backup activity or other unexplained drift. Do not interrupt unknown shell/agent processes.

Create `/home/scowalt/Code/ignite-for-spotify-app` only if still absent, from the public
repository, pinned to the source revision above. Do not reset/overwrite an existing
checkout or copy private ancestry. Preserve `/home/scowalt/Code/ignite-for-spotify-2`.

Use the public Compose file with these explicit controls:

- Project: `ignite-for-spotify`.
- Project directory/base path: `/home/scowalt/Code/ignite-for-spotify-2/docker`.
- Base file: `/home/scowalt/Code/ignite-for-spotify-app/docker/docker-compose.prod.yml`.
- Empty dotenv file (`--env-file /dev/null`); use explicit production Doppler selection.
- A persistent private operator override containing **only** the three literal digest
  image references. Keep a separate immutable rollback override. No secrets or rendered
  Compose configuration may be written into either file.

The old directory is only the retained relative-bind anchor, not source authority.
This preserves the live Caddyfile and Alloy bind sources. Assert exact physical
volumes: `ignite-for-spotify_ignite-data`, `ignite-for-spotify_backup-state`,
`ignite-for-spotify_caddy-data`, `ignite-for-spotify_caddy-config`.

Repeat the private hydrated comparison immediately before service changes. Require
`verify-production-config.py --require-digests` plus exact unaffected bind/network/
port/environment checks; its existing validator alone does not check every bind.
Secret injection must not override the approved digest references. Abort on a delta,
without printing values or silently accepting updated credentials.

## B. Fresh recovery point, without init or prune

Stop the known Watchtower instance without deleting/replacing it. Ensure no backup or
restore is active, then pause the old backup daemon to prevent its cron from overlapping.
Do not stop the backend for the online snapshot/restore check.

Do **not** blindly invoke `backup-once`: the current wrapper initializes on a failed
repository check and prunes on Sundays. Do not use the current restore wrapper's
`latest` selection or print table counts. Use an audited, bounded operation instead:

1. Run only the verified backup tooling image in a short-lived owned container, using
   the unchanged existing bucket-scoped credentials through private process transport.
   Mount live data read-only and a newly created restricted scratch directory read/write.
   Do not mount application data writable or expose a web port.
2. Require a successful read of the existing Restic repository configuration. On failure,
   stop; there is no `init`, migration or credential fallback.
3. Create a consistent SQLite backup of only `ignite.db`, with restrictive permissions,
   using a read-only source connection. Validate it without emitting record contents.
4. Upload one encrypted snapshot with the existing `ignite-production` host and
   `ignite-database` tag. Capture its exact snapshot ID, not `latest`. No forget/prune.
5. Restore only that snapshot's `ignite.db` into a separate empty restricted directory,
   using the pinned Restic client's `restore --verify`, then require SQLite integrity
   check `ok`. Never target the live volume. No dump, sample rows, tokens or plaintext
   file content may reach chat, logs, Git, CI artifacts or another machine.
6. Record non-sensitive snapshot/verification metadata. Update the existing success
   marker atomically only after successful backup verification. Remove only owned
   plaintext scratch/tooling; retain the encrypted recovery snapshot.

Approved operation budgets, refreshed before starting:

- Snapshot input at most **256 MiB**; stop if the database exceeds this bound.
- Local scratch at most **1 GiB**, retaining at least **3 GiB** filesystem headroom.
- At most **512 MiB additional R2 storage** for this operation, checked against available
  repository/object-size metadata. No new bucket/storage tier or retention policy.

These checks are not a hard billing cap. If size/accounting cannot be established or
exceeds the reviewed bounds, stop rather than expanding budgets or deleting history.
The existing legacy retention policy is not migrated by this operation.

If this phase fails, do not switch app images. Restore the old backup daemon's normal
operation if it was paused, leave updater/publisher fences in place and report the blocker.
Never leave scheduled backups disabled silently.

## C. Bounded service switch

With recovery proof complete and configuration revalidated, use the explicit project,
base directory, public file and digest override above. Use cached verified images:
`--no-build --pull never --no-deps`, with a graceful shutdown allowance.

1. Recreate backend only, with `--wait --wait-timeout 120`. Verify its exact digest,
   required-existing database path, ownership, preserved volume and readiness HTTP 200.
2. Only after backend passes, recreate backup and frontend with
   `--wait --wait-timeout 180`. Backup-on-start remains false; the existing fresh success
   marker/state is preserved, and there is only one scheduled backup daemon.
3. Verify all three exact image digests, source/revision/platform identity, applicable
   health checks, frontend response/static artifacts and backend readiness. The new
   frontend DSN becomes active here; legacy backend reporting stays unchanged.
4. Compare physical mounts/data identity and all unaffected settings. Caddy/Alloy IDs,
   start times and bind paths must remain unchanged. Inspect only bounded, redacted
   diagnostic metadata if a check fails; do not dump production logs or user records.

Only app services are recreated. No new updater/controller, DNS operation, database
restore, schema update or full-stack operation is part of this switch.

## D. Failure and image-only rollback authorization

The owner approved at most one image-only rollback if a service change fails:
use the pre-recorded old immutable digests, same project/mounts/environment, no builds,
no dependency recreation, and `verify-production-config.py --rollback`. Restore the
previous app-service set as needed, then verify health and preserved mounts once.
Keep publishers and Watchtower fenced.

No database file restore, sidecar deletion, ownership repair, retrying deployment or
unrelated service operation is automatic. If the old images also fail health, stop
with evidence and request a distinct availability/data-recovery decision. Preserve
snapshots, rollback images and failed-attempt evidence.

## E. Handoff and continuing CD

On success, leave Watchtower stopped and both publishers fenced. Record the durable
active digest override, observed running digests, recovery snapshot, health and unchanged
Caddy/Alloy evidence. No extra publication run or source-map upload is needed.

This establishes the new runtime image authority, **not continuing automatic CD**.
A digest-pinned first deployment is not a complete updater handover. Watchtower's
upstream is archived; do not silently upgrade, replace, duplicate or reactivate it.
A separate plan must cover coordinated multi-image releases, pre-deployment backups,
rollback and publisher activation before automatic updates resume. Paseo stays retired.

## Primary sources and related material

- [Compose CLI base-path and explicit project-directory behavior](https://docs.docker.com/reference/cli/docker/compose/).
- [Compose up: no-deps, no-build, pull never and wait controls](https://docs.docker.com/reference/cli/docker/compose/up/).
- [Restic exact-snapshot restore and include semantics](https://restic.readthedocs.io/en/stable/050_restore.html).
- [Pinned Restic restore implementation/verify flag](https://github.com/restic/restic/blob/6aa3a516ce654808a1f28f9fa21e9b7c8e6e90bf/cmd/restic/cmd_restore.go).
- [Watchtower cleanup/polling/monitor-only semantics](https://containrrr.dev/watchtower/arguments/).
- [Watchtower upstream](https://github.com/containrrr/watchtower), GitHub API `archived=true` observed 2026-11-02.
- [Fresh-image runbook](fresh-image-cutover.md), [backup/recovery runbook](sqlite-backup-recovery.md),
  [source-map delivery evidence](upload-secret-recovery.md).

Selected read-only planning evidence is retained privately in this thread's
`runtime-cutover-plan-evidence/`; it contains no rendered secret configuration or database contents.
