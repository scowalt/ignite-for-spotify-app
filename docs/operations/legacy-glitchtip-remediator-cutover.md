# Legacy GlitchTip Remediator Cutover

## Stop conditions

This is a one-time production operator runbook, not a development command. Do **not**
run cleanup from a shared checkout, CI, an agent, or before the replacement's fixture and
live read-only observe checks have passed.

The repository intentionally contains no legacy artifact IDs, markers, paths, or enabled
cutover configuration. Exact legacy inventory is deferred until an operator can verify it
against the old remediator. An empty or disabled configuration is correct and must remain
so until then.

Stop and verify the legacy service manually before any apply command. Record its actual
service name, `systemctl --user status` result, and the time it stopped in the change
record. The cleanup command requires `--legacy-service-stopped` as an explicit
acknowledgement, but the flag cannot prove the service stopped; the operator verification
is still mandatory.

## Build the exact manifest

Create the ignored `automation/glitchtip-paseo-controller/config/controller.toml` from
the example. Enable `[legacy_cleanup]` only when every target is known. It must contain:

- one durable marker **line** copied verbatim from the legacy PR body;
- a finite `repositories` allowlist of exact `owner/repository` names;
- one artifact table per exact repository, PR number, branch, registration path, and
  workspace path; and
- a `local_root` that bounds every registration/workspace path.

Artifact paths are relative to `local_root`. Globs, `..`, absolute artifact paths,
repository prefixes, and wildcard branches are rejected. `local_root`, every path below
it, the registration file, and the workspace must be non-symlinks; `/` and paths outside
the root are rejected.

For each artifact, preserve a local JSON registration with exactly this shape, replacing
only the documented placeholder values with the already-inventoried values:

```json
{
  "schema_version": 1,
  "marker": "<exact one-line durable marker>",
  "repository": "owner/repository",
  "pull_request": 123,
  "branch": "exact/legacy-branch",
  "workspace_path": "/absolute/local_root/workspaces/exact-workspace"
}
```

The remote PR must be open, have the same repository, number, branch, and an entire line
that equals `marker`. A substring, a marker with a suffix, an unmarked PR, a missing
branch, an altered registration, or extra registration fields is a skip, not a deletion.

## Inventory (dry run)

From the controller directory, use the shared GitHub automation capability through
Doppler `prd`. This operation only reads configured PR/branch evidence and local paths:

```sh
doppler run --project ignite-for-spotify --config prd -- \
  uv run --locked --python 3.12 glitchtip-paseo-controller legacy-cleanup \
  --config config/controller.toml \
  --capability-env github_automation_token=GITHUB_AUTOMATION_TOKEN
```

Require `eligible=N`, `skipped=0`, and `ready=yes`. Save the displayed
`DELETE-LEGACY-CLEANUP-...` confirmation token with the inventory output. If any target
is skipped or unavailable, stop. Correct the evidence manually; never loosen a marker,
path, allowlist, or branch match to make a target eligible.

## Apply once

After independently stopping and verifying the legacy service, repeat the exact inventory
from the same reviewed configuration. Then an authorized human may run:

```sh
doppler run --project ignite-for-spotify --config prd -- \
  uv run --locked --python 3.12 glitchtip-paseo-controller legacy-cleanup \
  --config config/controller.toml \
  --capability-env github_automation_token=GITHUB_AUTOMATION_TOKEN \
  --apply --legacy-service-stopped \
  --confirm DELETE-LEGACY-CLEANUP-EXACT_TOKEN_FROM_DRY_RUN
```

Apply closes each exact open PR and deletes its exact branch through the injected GitHub
client. It re-reads every PR/branch and requires all configured remote targets to be
absent (closed PR plus absent branch) **before it removes any associated local workspace
or registration**. It then verifies those local paths are absent.

A remote error or an uncertain re-read blocks local deletion for all eligible targets and
returns `cutover_enabled=no`. Do not delete local data by hand to work around this state.
Keep the controller paused, retain the failed output and backup, and investigate the
specific remote target before a new dry run.

## Completion and rollback posture

Only a result with `complete=yes` and `cutover_enabled=yes`, followed by a clean live
observe report, permits enabling the local observe unit. Keep the old service stopped;
do not restart it during rollback experimentation.

There is no automatic rollback after a confirmed remote closure/branch deletion. Before
apply, back up the controller SQLite state and archive the exact inventory/apply outputs.
If later dispatch fails, pause the controller, inspect durable jobs and preserved Paseo/PR
evidence, and use explicit job retry only after diagnosis. Auto-merge remains CI-only;
this cutover neither changes GitHub policy nor gives the automation credential bypass
rights.
