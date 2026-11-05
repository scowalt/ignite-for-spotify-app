# Guarded continuous delivery

> Migration-aware schema-v2 delivery is active after the separately approved cold-WAL
> recovery and baseline adoption on 2026-11-05. The timer and automatic publishing are
> enabled again. The original failed artifact remains fenced, with its blocked evidence
> and audited manual-resolution receipt preserved. Never replay that attempt or its prior
> restart helper. The live ledger, not a historical source SHA below, selects current images.

The public repository is the sole maintained source and publisher. Its protected
main workflow publishes automatically after successful validation and all actual image,
source-map, secret and notice gates, without a separate production approval click.
Merging a green protected PR is the release decision, including Renovate auto-merges.
A versioned user-systemd updater on the existing
VPS deploys only a coherent, authenticated, successfully completed release.

Legacy Deploy workflow `218752864` stays disabled and Watchtower stays stopped. The
new updater is the only active update controller. Paseo remains retired. Published
per-image `latest` tags are not deployment authority.

## Sources of truth

On SSH host `ignite-for-spotify-2`, as user `scowalt`:

| Purpose | Authoritative location |
| --- | --- |
| Last committed verified release and interrupted transaction | `~/.local/state/ignite-deployer/state.json` |
| Installed operator version/contract/repository identity | `~/.local/state/ignite-deployer/policy.json` |
| Reviewed operator bundle | `~/.local/lib/ignite-deployer/current` → immutable source-SHA directory |
| Current attempt/active image override | `~/.local/state/ignite-deployer/<artifact digest without sha256:>/candidate.compose.json` |
| Prior image override and bounded private preflight evidence | Same attempt directory: `prior.compose.json`, `runtime.json`, `result.json` |
| Database transition and exceptional manual-resolution evidence | Same attempt directory: `migration.json`; separately reviewed `manual-resolution.json` where applicable |
| Sole polling unit | `ignite-deployer.timer` / `ignite-deployer.service` in the user manager |

Use the ledger's artifact digest to find the matching override; do not guess a path
from current Git main or reuse the old cutover override. `active` means the last
successfully committed image set. During failed/interrupted work, inspect the transaction
and actual runtime before assuming containers match that set.

The production Compose checkout remains intentionally pinned at the reviewed
`4ef6b03` configuration under `~/Code/ignite-for-spotify-app`. Application image versions
come from the signed release and ledger, not this checkout's Git HEAD. The old
`~/Code/ignite-for-spotify-2/docker` remains only the explicit Compose project-directory
and bind-path anchor. Preserve it, the Caddyfile/Alloy sources and physical volumes.
The installed operator version is reviewed separately; release records never deliver
executable operator code or upgrade that bundle.

## Ordinary operation

1. Merge through the existing protected source workflow. Owner-authored merges use
   explicit expected-head and `scowalt@gmail.com` controls; other contributors retain
   their identities.
2. Successful main validation enters the `production` publishing job automatically.
   The environment retains its main-only deployment policy and scoped inputs, but
   has no required reviewer. Only its named scoped upload secret and short-lived
   signing identity are used. No production Doppler/runtime/database credential
   belongs in public/fork CI.
3. The publisher scans/pushes all three images, builds a small single-platform metadata
   record, signs/verifies its immutable digest and promotes one pointer. The consumer
   also checks the matching workflow completed successfully. Partial/failed publication
   cannot authorize a deployment.
4. The timer polls after boot and five minutes after the preceding invocation ends.
   An unchanged committed artifact is a no-op without another workflow API lookup.
   A new artifact receives full trust/source/run/contract validation.
5. Before image mutation, the updater verifies current identities/configuration,
   existing volumes/data, source/platform/UID compatibility and storage headroom. It
   quiesces backup and backend writers, creates a new encrypted snapshot and verifies
   its exact isolated restore. The v2 transition validates the applied catalogue prefix,
   executes only eligible pending SQL, then independently verifies history/schema before
   image admission. An unchanged catalogue executes no migration. Owned plaintext/tooling
   is removed before image changes; planned downtime includes these stopped-state steps.
6. Backend updates and passes bounded readiness/identity checks before backup/frontend.
   Only the three app services change, using explicit digests and no builds, tag pulls
   or dependency recreation. Commit the active set only after complete verification.

The owner approved removal of the extra environment-review step after the migration.
TASK-41 records the narrow IaC change and its live verification. No workflow, signing
identity, scoped secret or branch protection is removed. Passing CI is not proof of
business correctness; without the extra pause, a green merged regression can reach
production. Reviewed, bounded automatic structural expansions can use this same delivery
path without another production approval click. Destructive/manual migrations, unbounded
backfills, engine/Hangfire or safety-contract changes, infrastructure operations and operator
upgrades still require separately reviewed procedures. See [migration policy](database-migrations.md).

Inspect status without loading runtime secrets:

```sh
/usr/bin/python3 "$HOME/.local/lib/ignite-deployer/current/scripts/ignite-deploy.py" status
systemctl --user status ignite-deployer.timer ignite-deployer.service
journalctl --user -u ignite-deployer.service --since today
```

An explicit read-only candidate check uses the existing Doppler selection:

```sh
doppler run --project ignite-for-spotify --config prd -- \
  /usr/bin/python3 "$HOME/.local/lib/ignite-deployer/current/scripts/ignite-deploy.py" check
```

Check refuses an interrupted transaction; it cannot perform recovery under a read-only
name. Workflow metadata uses the existing owner-private GHCR credential, checked to
have exactly `read:packages`, against the fixed public repository endpoint. No new
credential, repository/write permission or token copy into CI/state was introduced.
Unexpected storage/scope or provider failure blocks deployment; it never permits a
CI-status bypass. Routine idle polls do not repeat workflow API requests.

## Failure and recovery

- `rolled_back`: one bounded image-only rollback verified the prior set. The failed
  artifact stays fenced; polling does not retry it. The replay high-water order remains.
- `manual_recovery`: stop and inspect. A rollback already started cannot be retried
  automatically. Current containers may differ from the last committed ledger set.
  Committed or uncertain database changes require a forward fix, never an incompatible
  old image or automatic live restore. A child's `verified` phase is database evidence,
  not proof that the outer image deployment committed.
- `cleanup_required`: the transaction remains durable. Cleanup may be retried without
  repeating a committed deployment or backup. Preserve evidence and unknown files.
- `verification_or_operation_failed`: no raw provider/secret-bearing output is emitted.
  Inspect bounded private evidence to distinguish trust, identity, configuration,
  quota, access and capacity failures. A healthy build alone is not deployment proof.

To pause new ticks, disable only this owned timer:

```sh
systemctl --user disable --now ignite-deployer.timer
```

This does not justify killing a running transaction. Inspect the service and durable
phase before an availability-recovery decision. Fence new publication through the
repository variable when necessary and record the reason. Source policy desires true;
a later IaC apply must not silently remove an emergency fence.

No automatic database restore, repository initialization/pruning/unlocking, volume
recreation, broad chown, image pruning or unrelated-service restart is permitted.
Preserve old image digests and encrypted recovery evidence. Missing/corrupt state is
not automatically bootstrapped. Manual retry/recovery or a contract/operator change
requires a scoped reviewed procedure, not hand-editing the ledger to make it green.

## Budgets and compatibility

Snapshot input is limited to 256 MiB, local scratch to 1 GiB and additional remote
storage per operation to 512 MiB, with 3 GiB free disk retained. Image preflight adds
conservative pull/unpack checks. These estimates are not quotas or hard billing caps.
Do not increase budgets or prune recovery material automatically.

Known Compose/database-startup compatibility inputs are fingerprinted. A changed
contract blocks automatic deployment for manual migration review. This is a guard,
not proof that arbitrary application business-data changes are backward-compatible;
source review still owns that promise. Production startup requires complete exact history;
missing, reordered or changed applied SQL is not silently repaired. SQLite page/file limits
are not aggregate WAL, temporary-file or filesystem quotas. Backup covers only `ignite.db`,
not provider-owned Hangfire storage or cookies.

The existing scheduled-backup retention policy is preserved. The guarded deployment
path never invokes the legacy wrapper's init fallback or Sunday prune behavior.
Infrastructure state credentials in `mission-control/dev` are separate from application
backup credentials in `ignite-for-spotify/prd`; both remain scoped to their existing
buckets. Authentication values never belong in source, service units, logs or state.

## Verification record

The first v2 attempt stopped before adoption on a checkpointed, sidecar-free WAL file
mounted read-only. The compatible original services were restored once; no live data was
restored. TASK-46 added explicit stopped-state handling and native joined regression tests.
Under a separately approved TASK-44 procedure, a rehearsed metadata-only reconciliation
recorded the already-restored prior state and preserved its blocked sidecar, failed digest
and replay high-water. It did not repeat that restart or fabricate automated success.

Protected PR #27 merged the exact tested tree as `2fb52ca37f1266212584f643fc07afa32ab4425f`.
Full [CI 41963026186](https://github.com/scowalt/ignite-for-spotify-app/actions/runs/41963026186)
published the new signed release, order `[88,1]`; the reviewed `e3b6bd2` operator deployed
it through the actual timer. A fresh encrypted snapshot and exact isolated restore passed
all existing budgets before baseline-only adoption. Independent checks verified one immutable
baseline entry, unchanged application schema/file identities/mounts and auxiliaries, healthy
exact images and removed owned tooling/plaintext. No rollback was used for this attempt.
A subsequent actual no-op tick preserved the ledger and every container start time. The
intentional publishing/timer holds were then lifted. Raw operational evidence stays private;
these completed procedures are not reusable recovery commands.

The first guarded signed deployment used successful CI run `41569719775` at source
`883b869e3f512e97e368707dc2d8cc3ac118faf9`. Independent readback proved healthy exact
images, preserved database inode/ownership/mounts, unchanged Caddy/Alloy identities,
backup access and removal of owned tooling/plaintext. No rollback was used. Recovery
snapshot `4f22373e3d712512040bb8456bb858ea4079d40e19f8e39282f151277787b31e` was restored
and verified within budget. This is historical evidence, not a hardcoded current image
selection or permission to replay the completed operation.

A subsequent real timer-driven deployment from CI run `41574530594` committed source
`c3ee2e694a5b9078980056c4a58271c238fe6b4f` automatically. Independent checks again passed;
no rollback was used. Recovery snapshot
`3ac123f47bd369c328f2fc50ae76b2fa538a20d116a5fab69cd5f6efecdaa3b6` was restored/verified
within the same budgets. The final sole-publisher enablement was a reviewed flag-only
OpenTofu apply with unrelated state/settings preserved and a no-op follow-up plan.

The subsequent owner-approved automatic-publishing policy removed only the production
reviewer rule through a fresh full-root OpenTofu plan; all other settings and unrelated
state were preserved, and the follow-up plan was empty. GitHub canceled the publisher
already waiting on the deleted rule before any runner/steps started. A fresh full CI
[run 41648567265](https://github.com/scowalt/ignite-for-spotify-app/actions/runs/41648567265)
at source `6be9e16d475726d7975a7644a74e3565b956bd57` then published successfully with
no approval events. The existing timer deployed that signed release without a manual
deploy command. Exact healthy images, preserved data/mount/auxiliary identities,
unchanged operator/policy/units and removal of owned plaintext/tooling were verified.
Recovery snapshot `6bdf1020692a476c75e49d1bb221300f9dba5a37ff40986e10d151c6381e48ca`
restored exactly within budget; no rollback was used. TASK-41 records this evidence.
These identifiers are historical proof, not a replacement for the live ledger.

Isolated frontend debug-ID symbolication was verified with a uniquely labelled synthetic
event from a served source-mapped function span. It resolved to `Home.tsx`; only synthetic
events were inspected, and their groups were resolved. The legacy frontend/history and
backend projects remain intact; Mission Control reads both maintained organizations.

See [implementation/adapter contract](../../ops/deployer/README.md),
[dependency handover](dependency-handover.md), [infrastructure ownership](../../infra/README.md)
and the historical [runtime cutover](runtime-cutover-plan.md). TASK-38 through TASK-40
hold final activation, automation coverage, external limitations and completion evidence.
