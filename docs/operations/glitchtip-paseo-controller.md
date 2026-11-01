# GlitchTip Paseo Controller Operations

## Boundaries

The controller is a **local user service**, outside Docker and the production Ignite
application. It watches only GlitchTip projects 1 and 2. GitHub auto-merge is the only
merge action: existing protected-`main` CI (`backend` and `frontend`) decides whether a
remediation PR merges. Do not add this CI job as required or change branch protection as
part of controller rollout.

The committed `ignite-glitchtip-paseo-controller.service` is an **observe gate**. It
executes the read-only compatibility report at service start; it does not launch a Paseo
workspace, agent, PR, or any remediation mutation. The separate
`ignite-glitchtip-paseo-controller-dispatch.service` and one-minute `.timer` templates
are committed but disabled by default. Keep dispatch disabled until its separate
operational approval.

## Local configuration

From the controller directory, create the untracked local file and preserve the safe
empty cleanup table until cutover is approved:

```sh
cp config/controller.example.toml config/controller.toml
chmod 600 config/controller.toml
```

`state_directory` is under `XDG_STATE_HOME`; for the user unit it is
`~/.local/state/ignite-glitchtip-paseo-controller`. Older local configurations that omit
the dispatch fields remain safely disabled and work for `report`. Before setting
`dispatch_enabled = true`, add `workspace_root` as an explicit XDG-state path containing a
dedicated controller-owned clone; it is never inferred from the checkout that runs the
controller. Do not place state, a Doppler token, or literal credentials in this repository.

The hardened dispatch unit intentionally shares the existing local Paseo daemon using the
non-secret values `PASEO_HOME=%h/.paseo` and `PASEO_HOST=127.0.0.1:6767`. It makes only
that Paseo home writable, in addition to the controller state and dedicated workspace;
it does not make the user's whole home writable. The controller never starts, restarts, or
stops the daemon. The daemon must already be running on that loopback address with the
same Paseo home.

Doppler configuration is **`prd`**, not `prod`. The service receives its secrets only
through `doppler run`. The configuration identifies capabilities, never values. Do not
put tokens in service overrides, environment files, agent prompts, status output, or
journal messages.

## Observe

Before installing or enabling the unit, run the deterministic fixture gate:

```sh
cd automation/glitchtip-paseo-controller
uv run --locked --python 3.14 glitchtip-paseo-controller report \
  --config config/controller.example.toml --fixtures tests/fixtures \
  --capability glitchtip_api_token --capability github_automation_token
```

A live observe check is read-only. It requires Doppler but never launches a workspace.
Its GitHub credential needs protected-branch policy and ruleset read access only: the
observe gate does not fetch individual check runs and does not require the GitHub Checks
permission. Branch protection and GitHub auto-merge remain authoritative for CI:

```sh
doppler run --project ignite-for-spotify --config prd -- \
  uv run --locked --python 3.14 glitchtip-paseo-controller report \
  --config config/controller.toml --live \
  --capability-env glitchtip_api_token=GLITCHTIP_API_TOKEN \
  --capability-env github_automation_token=GITHUB_AUTOMATION_TOKEN
```

Confirm the output reports the pinned GlitchTip URL, projects 1 and 2, protected-branch
CI contexts and rulesets, expected Paseo/Pi capabilities, and `Dispatch: disabled`.

## Enable the local observe service

Only after legacy cutover has a successful, verified result and both observe gates pass:

```sh
mkdir -p ~/.config/systemd/user
cp systemd/ignite-glitchtip-paseo-controller.service \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ignite-glitchtip-paseo-controller.service
```

The unit assumes the checkout is `%h/src/ignite-for-spotify-2`; adjust `WorkingDirectory`
and `ConditionPathExists` in a local override if needed. Do not edit the committed unit
for a machine-specific checkout. It sets a restrictive umask, preserves state only under
XDG, and writes non-secret report output to the user journal.

This step installs/enables only the read-only gate. It is not authorization to enable
dispatch, change GitHub policy, or rely on the non-required controller CI job as a merge
requirement.

## Dispatch preflight and explicit enablement

Dispatch has two independent gates: the untracked configuration must set
`controller.dispatch_enabled = true`, and every invocation must include both `--once`
and `--enable-dispatch`. The former is a persisted operator policy; the latter prevents
an accidental command or timer invocation from mutating external state. A normal
`report` command cannot dispatch.

Before enabling the timer, an operator must verify the observe report, the dedicated
workspace clone, both named capability mappings, the durable database backup, and the
existing local Paseo daemon. Use the same deployment values as the hardened service:

```sh
PASEO_HOME="$HOME/.paseo" PASEO_HOST=127.0.0.1:6767 paseo daemon status --json
```

If the daemon is unavailable, an active dispatch job fails with the explicit
`PASEO_DAEMON_UNAVAILABLE` code; dispatch never attempts to start it. Run one intentional
tick first:

```sh
cd automation/glitchtip-paseo-controller
# Only after updating the untracked local config to dispatch_enabled = true.
doppler run --project ignite-for-spotify --config prd -- \
  uv run --locked --python 3.14 glitchtip-paseo-controller dispatch \
  --config config/controller.toml --once --enable-dispatch \
  --capability-env glitchtip_api_token=GLITCHTIP_API_TOKEN \
  --capability-env github_automation_token=GITHUB_AUTOMATION_TOKEN
```

A tick establishes its first-run baseline without dispatching pre-existing issues,
observes positive issue reactivation, reconciles current jobs, and launches no more
than one queued job. It has no auto-retry path. Errors from external parsing, API, or
command calls become visible failed jobs when a job exists; no issue is resolved or
resources cleaned unless GitHub reports the exact linked PR as merged.

GitHub required CI plus GitHub auto-merge is the only merge authority. After that merged
outcome, the controller reads the current GlitchTip issue and uses GlitchTip's ordinary
status update endpoint to resolve it; it does not use conditional-concurrency APIs. The
controller passes the shared `GITHUB_AUTOMATION_TOKEN` to the Paseo agent with its explicit
per-agent `--env GITHUB_AUTOMATION_TOKEN=...` option, never in the agent prompt, logs,
controller output, or static configuration.

The dispatch timer remains disabled until this deliberate proof succeeds. To install its
templates, copy both files to `~/.config/systemd/user/`, reload systemd, and have an
operator explicitly enable the timer. No live dispatch, Doppler access, service install,
or service enablement was performed while adding these templates.

## Pause and status

Pause dispatch without touching application containers or GlitchTip. Disable and stop the
timer, then stop any already-running dispatch service and verify it is inactive:

```sh
systemctl --user disable --now ignite-glitchtip-paseo-controller-dispatch.timer
systemctl --user stop ignite-glitchtip-paseo-controller-dispatch.service
if systemctl --user is-active --quiet ignite-glitchtip-paseo-controller-dispatch.service; then
  echo "dispatch service is still active; do not continue" >&2
  exit 1
fi
```

Pausing the controller prevents future ticks only. Already-detached Paseo agents are not
stopped automatically. An operator must inspect them with the same `PASEO_HOME` and
`PASEO_HOST`, match each one to durable job state, and explicitly run `paseo stop AGENT_ID`
where stopping it is intended.

The observe service is separate and may be paused independently:

```sh
systemctl --user disable --now ignite-glitchtip-paseo-controller.service
```

Inspect its last health check:

```sh
systemctl --user status ignite-glitchtip-paseo-controller.service
journalctl --user -u ignite-glitchtip-paseo-controller.service -n 100 --no-pager
```

Inspect durable jobs without credentials or agent execution:

```sh
cd automation/glitchtip-paseo-controller
DB="${XDG_STATE_HOME:-$HOME/.local/state}/ignite-glitchtip-paseo-controller/state.db"
uv run --locked --python 3.14 glitchtip-paseo-controller status --database "$DB"
uv run --locked --python 3.14 glitchtip-paseo-controller list --database "$DB"
```

A failed job remains visible and unresolved. It does not retry, rebase, resolve the
GlitchTip issue, or delete its evidence automatically. Once an operator has investigated,
the explicit retry command is the only retry path:

```sh
uv run --locked --python 3.14 glitchtip-paseo-controller retry --database "$DB" JOB_ID
```

## Backup and recovery

Before copying the SQLite state, pause dispatch as above: disable and stop the dispatch
timer, stop the dispatch service, and verify that service is inactive. Create a dated
backup outside the checkout and verify it:

```sh
systemctl --user disable --now ignite-glitchtip-paseo-controller-dispatch.timer
systemctl --user stop ignite-glitchtip-paseo-controller-dispatch.service
if systemctl --user is-active --quiet ignite-glitchtip-paseo-controller-dispatch.service; then
  echo "dispatch service is still active; do not back up" >&2
  exit 1
fi
sqlite3 "$DB" ".backup '${DB}.backup-$(date +%Y%m%d%H%M%S)'"
sqlite3 "$DB" "PRAGMA integrity_check"
```

Do not re-enable the timer until an operator has inspected the backup, durable jobs, and
any detached Paseo agents. Detached agents are not stopped by the pause procedure; inspect
and explicitly stop them where appropriate before resuming dispatch.

Do not delete an active workspace, PR, branch, or database to "retry" it. Preserve the
failure evidence, take a backup, and use the explicit `retry` command only after the
root cause is understood.

## Cutover warning

Legacy cleanup is a separate, human-supervised one-time action. It is not run by this
service. Follow the [legacy cutover runbook](legacy-glitchtip-remediator-cutover.md);
leave controller enablement paused if any cleanup target is skipped, any remote operation
fails, or absence verification is incomplete.
