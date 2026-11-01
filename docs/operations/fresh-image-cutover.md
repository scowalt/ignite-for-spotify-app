# Fresh-image first release and rollback

**Prepared procedure, not executed. Production approval is separate.** This repository
has no production secrets or enabled publisher yet. Do not run the generic README
update commands to perform this migration.

## Invariants

- New image namespace: `ghcr.io/scowalt/ignite-for-spotify-app`.
- Existing Compose project: **`ignite-for-spotify`**. Always pass it explicitly.
- Keep `ignite-for-spotify_ignite-data`, `ignite-for-spotify_backup-state`,
  `ignite-for-spotify_caddy-data`, and `ignite-for-spotify_caddy-config` unchanged.
- Keep database paths, require-existing policy, backup repository/host/tag and
  credentials unchanged. No `compose down`, volume recreation, database migration,
  backup initialization, secret rotation or DNS change is part of this procedure.
- Only backend, backup and frontend image references change during the app cutover.
  Preserve the running Caddy/Alloy bind sources and the old checkout they refer to
  until a separate configuration-path handover is reviewed. Do not recreate the
  entire stack from a different checkout directory.

## Release-readiness evidence

The existing required `backup` check aggregates the synthetic backup/restore tests
and all three release-image verification jobs. A failed/skipped image job produces
an explicit failing aggregate check; no branch-protection settings are changed.

Image verification uses the same fixed HIGH/CRITICAL and secret policy as publishing,
checks shipped notice-file coverage, and also scans the frontend production lockfile.
It builds only disposable local/hosted-runner images and never logs in or pushes to
GHCR. The actual credentialed release build is scanned again before **any** push;
verification builds without production frontend variables are not the exact future
release digest.

Each image includes application/dependency scope and its component notice manifest
under `/usr/share/licenses/ignite`. Browser notices are also served from
`/third-party-licenses/manifest.json`. Review license/source obligations for the exact
release components, including the documented tr46 SPDX-text supplement. Mechanical
coverage checks are not a legal opinion; preserve upstream copyrights and source
availability where required. No broad license waiver is implied by green CI.

## Required operator decisions and preflight

1. Approve the exact source commit and release scope. Backend application source was
   already at the exported baseline during inspection; frontend and backup were
   older. This first release therefore includes the intervening authorization-error
   fix, dependency updates and cleanup, plus the approved security updates—not just
   a repository rename. Recheck current deployed revisions before acting.
2. Confirm all writers/publishers and controller locations. Drain/fence the original
   GitHub publisher and any other identified release path before enabling the new
   one. Do not create another Watchtower/controller or assume an undiscovered
   controller has been retired. Preserve in-flight work and private evidence.
3. Record current immutable image references and mount/health metadata privately.
   Verify rollback images remain available and the new backend's effective UID/GID
   is compatible with the existing data-volume ownership; do not fix a mismatch
   with a blanket chown. Existing shell/agent sessions and dirty checkouts must be
   preserved and coordinated, not reset or overwritten.
4. Provision only explicitly approved environment variables/credentials. Do not copy
   the broad production Doppler token into the public repository. Protect the
   production environment and trusted-main path before setting the publish-enable
   variable. Keep Renovate/controller activation a separate approval.
5. Verify fresh package access without granting this public repo access to legacy
   package history. GitHub warns that public-repo package grants may also allow fork
   reads. Images must contain no production data/secrets regardless of private flags.
6. Ensure backups are healthy and no snapshot/restore is in progress, using approved
   process/health metadata only. Preserve off-host repository identity; do not query
   user rows or read backup contents merely for this check.

## Approved first-release sequence

After explicit authorization, run the new workflow for the approved main commit.
Do not bypass gates, branch protection or environment approval. All images must be
built/scanned before publishing; multi-image registry pushes are not atomic.
Publishing into the new namespace does not by itself change the running old-image
containers.

Before any service change, obtain all three new registry digests and verify the
production Docker client can read/pull those exact images using approved existing
access. If access fails, stop; do not silently rotate credentials or broaden package
permissions. Keep legacy packages and their access controls intact.

Set `BACKEND_IMAGE`, `BACKUP_IMAGE` and `FRONTEND_IMAGE` to the new **digest-pinned**
references in the approved operator environment. Hydrate runtime configuration only
through the approved secure mechanism. Never print, save or upload the full rendered
Compose environment. Validate through a pipe:

```bash
docker compose -p ignite-for-spotify -f "$COMPOSE_FILE" config --format json \
  | python3 "$PUBLIC_CHECKOUT/scripts/verify-production-config.py" --require-digests
```

This command only validates identity/mount invariants; it does not deploy. Ensure
pipeline failures are propagated by the operator shell. Do not let secret injection
overwrite the approved image-reference variables after validation.

With the old publisher fenced and the agreed updater coordination in place, perform
only the separately approved app-service change using the same configuration and
project. Do not run a whole-stack `pull`/`up` or use `--force-recreate` indiscriminately.
The app-service commands, only after that approval and preflight, are:

```bash
docker compose -p ignite-for-spotify -f "$COMPOSE_FILE" up -d --no-deps \
  --wait --wait-timeout 120 backend
docker compose -p ignite-for-spotify -f "$COMPOSE_FILE" up -d --no-deps \
  --wait --wait-timeout 180 backup frontend
```

Stop on a failed health wait rather than continuing automatically. Verify the exact
running image digests, preserved physical mounts, backend/frontend readiness and
backup continuity. A successful build alone is not deployment evidence.
Re-enable only the agreed single updater path after successful verification.

Once stable, normal development and publishing must use this public repository only.
Complete BB/checkouts/open-work, bot/controller and infrastructure-ownership migration;
publication and this first deployment alone do not complete those other handovers.

## Rollback

Rollback requires an approved availability-recovery decision. Use the privately
recorded prior **registry digests**, not mutable legacy `latest` tags or a guessed
local image ID. The prior baseline is not thereby security-approved.

Set all three app image overrides to the approved legacy digest references, keeping
all project, volume, database, credential, backup and proxy settings unchanged. The
validator permits this only in explicit rollback mode:

```bash
docker compose -p ignite-for-spotify -f "$COMPOSE_FILE" config --format json \
  | python3 "$PUBLIC_CHECKOUT/scripts/verify-production-config.py" --rollback
```

Keep publishers/updaters fenced while restoring the approved references and verifying
health/mounts. Do not auto-enable both publishers, roll back database contents, delete
volumes, prune shared image caches or erase failure evidence. Stop for operator input
if the invariants or rollback-image availability cannot be established.
