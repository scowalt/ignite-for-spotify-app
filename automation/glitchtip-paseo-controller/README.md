# GlitchTip Paseo Controller

A local Python 3.14 controller for the two Ignite GlitchTip projects. It keeps durable
job state outside the application deployment and treats GitHub auto-merge plus the
existing required `backend` and `frontend` CI checks as the only merge authority. It
never changes branch protection or adds a review gate.

The committed example is safe by default: it has no legacy targets,
`legacy_cleanup.enabled = false`, and `controller.dispatch_enabled = false`.

## Read-only observe gate

Use fixtures without secrets:

```sh
uv run --locked --python 3.14 glitchtip-paseo-controller report \
  --config config/controller.example.toml \
  --fixtures tests/fixtures \
  --capability glitchtip_api_token \
  --capability github_automation_token
```

For a local, live read-only health check, copy the example to the ignored
`config/controller.toml`, then let Doppler inject values only into the controller
process:

```sh
doppler run --project ignite-for-spotify --config prd -- \
  uv run --locked --python 3.14 glitchtip-paseo-controller report \
  --config config/controller.toml --live \
  --capability-env glitchtip_api_token=GLITCHTIP_API_TOKEN \
  --capability-env github_automation_token=GITHUB_AUTOMATION_TOKEN
```

`report` makes authenticated `GET` requests and fixed Paseo/Pi inspection calls only.
For GitHub, it reads protected-branch policy and rulesets; it does not fetch individual
check runs and does not require the GitHub Checks permission. GitHub branch protection
and auto-merge remain the sole CI merge authority. It lists unresolved issues and leaves
dispatch disabled; it never creates a workspace, agent, branch, PR, or issue mutation. See
[`docs/operations/glitchtip-paseo-controller.md`](../../docs/operations/glitchtip-paseo-controller.md)
for observe, enable, pause, and status procedures.

## Explicit dispatch tick

Dispatch is a separate mutating command. It requires all of the following:

- a dedicated, controller-owned Git clone at the explicit `controller.workspace_root`;
- `controller.dispatch_enabled = true` in the untracked local configuration; and
- both `dispatch --once` and `--enable-dispatch`, plus both capability mappings.

A tick baselines its first complete GlitchTip listing without launching existing issues,
records positive reactivations, resumes visible jobs, and launches at most **one** queued
job. It never retries automatically. `report` has no dispatch path and remains
read-only.

The controller passes `GITHUB_AUTOMATION_TOKEN` to the coding agent with Paseo's explicit
per-agent `--env GITHUB_AUTOMATION_TOKEN=...` option so it can commit, push, and open one
linked PR. The value is never placed in the prompt, static TOML, controller result/status
output, or logs. GitHub required CI and GitHub auto-merge
are the only merge authority. When GitHub positively reports that exact stored PR as
merged, the controller reads the current GlitchTip issue, makes its ordinary resolved
status update, then archives and cleans the registered resources. No conditional
concurrency endpoint or controller merge decision is used.

The dispatch service and one-minute timer templates are committed but disabled by
default. This change did not run live dispatch, use Doppler, install, or enable either
service; follow the operations runbook before any operator enablement.

## Guarded legacy cleanup

Do not populate `[legacy_cleanup]` until the operator has manually inventoried every
legacy target. A target is eligible only if all of the following exact values agree:

- allowlisted `owner/repository`, PR number, and branch;
- one complete marker line in the remote PR body (no prefix or substring matching);
- an existing local registration JSON file whose complete contents exactly match the
  configured marker, repository, PR, branch, and workspace path; and
- non-symlink registration and workspace paths below the configured local root.

The dry run only inventories. It prints a configuration-bound confirmation token:

```sh
doppler run --project ignite-for-spotify --config prd -- \
  uv run --locked --python 3.14 glitchtip-paseo-controller legacy-cleanup \
  --config config/controller.toml \
  --capability-env github_automation_token=GITHUB_AUTOMATION_TOKEN
```

Only after the legacy service has been stopped and independently verified by an
operator may a human run the command shown in the cutover runbook with all of:
`--apply`, `--legacy-service-stopped`, and the exact dry-run `--confirm` token. Remote
PR closure and branch deletion must both succeed and be re-read as absent before the
controller removes *any* associated local registration or workspace. A remote error,
a marker mismatch, an unsafe path, or a failed absence check leaves cutover disabled.

See [`docs/operations/legacy-glitchtip-remediator-cutover.md`](../../docs/operations/legacy-glitchtip-remediator-cutover.md).

## Secrets and child processes

Doppler is the only production secret source and is configured as `prd`. The static
TOML names capabilities but contains no token values. Controller reports, job status, operation logs, and remediation prompts must not contain secret values. The
dispatch runtime gives its Paseo launch exactly the shared `GITHUB_AUTOMATION_TOKEN` with
Paseo's explicit per-agent `--env` option; it does not copy ambient controller credentials
or render the token. It intentionally preserves the non-secret `PASEO_HOME` and
`PASEO_HOST` values so the hardened dispatch service can use its existing local daemon.
That service sets `PASEO_HOME=%h/.paseo`, `PASEO_HOST=127.0.0.1:6767`, and permits writes
only to that Paseo home, not all of `%h`; it never starts the daemon. The older
`preflight.build_child_environment` helper remains credential-free for read-only contract
testing.

## Development checks

```sh
uv lock --check
uv run --python 3.14 python -m unittest discover -s tests -v
uv run --python 3.14 ruff check .
uv run --python 3.14 ruff format --check .
uv run --python 3.14 pyright src
uv run --locked --python 3.14 glitchtip-paseo-controller report \
  --config config/controller.example.toml --fixtures tests/fixtures \
  --capability glitchtip_api_token --capability github_automation_token
git diff --check
```
