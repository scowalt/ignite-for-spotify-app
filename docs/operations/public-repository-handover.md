# Public repository handover

**Status: migration complete, with the owner-accepted BB cached-remote limitation below.**
The development repository is `scowalt/ignite-for-spotify-app`; the owner's checkout
is `~/Code/ignite-for-spotify-app`. Production uses the protected publisher and sole
[guarded updater](guarded-continuous-delivery.md), verified through controlled and
timer-driven deployments. Legacy publishing and Watchtower remain inactive. Old
private history and uncommitted work are preserved. Hosted Renovate is verified by
an enabled, onboarded scan and bot-authored [Dependency Dashboard #17](https://github.com/scowalt/ignite-for-spotify-app/issues/17);
see [the dependency handover](dependency-handover.md) and TASK-39.

BB's project name, default source/path, active environment and actual Git origin
point to the maintained repository. Its stored `gitRemoteUrl` still names the old
private repository because the installed supported API has no setter. On November 3,
2026, the owner explicitly accepted this documented limitation to close TASK-40.
The cache was not corrected: no internal state patch, duplicate project or history
removal was performed. For additional-host clones, explicitly supply
`https://github.com/scowalt/ignite-for-spotify-app.git`, including the supported
`bb project source add --clone --remote-url` override rather than relying on the cache.
A future supported BB correction is separate maintenance, not an unfinished migration.

The destination is the only home for ongoing development, issues and pull
requests, dependency updates, GitHub Actions CI and production publishing.
Paseo-based remediation is excluded: the owner no longer uses Paseo. This is not a
permanent public mirror. The old private repository retains historical evidence only
after handover. Do not copy its Git ancestry, database
sidecars, PR refs, historical logs/artifacts, attachments or runtime state into this
repository.

## Source and licensing

Original code/custom artwork is MIT-licensed; dependency licenses remain separate.
See [third-party notices](../../THIRD_PARTY_NOTICES.md). Do not include live Spotify,
CustomsForge or user data, credentials, cookies or database files. Run
`python3 scripts/check-public-source.py` after staging changes. This path/mode guard
is not a secret scanner or a substitute for content review.

## CI and publishing boundaries

- `ci.yml` runs validation on main pushes, main PRs and manual dispatch. Public PR
  jobs use GitHub-hosted runners and a read-only token, with no inherited secrets.
- The publish job depends on successful backend, frontend, backup and public-source
  validation in that same workflow execution. The existing required `backup` context
  now aggregates backup tests, all three non-publishing release-image checks and
  credential-free infrastructure validation. It runs even when a dependency fails
  and fails closed. No branch-protection setting
  or controller requirement is changed.
- `deploy.yml` is reusable only; it has no independent push/dispatch trigger. Both
  caller and publisher require the exact destination repository, main, a push or
  manual event, and repository variable `PRODUCTION_PUBLISHING_ENABLED=true`.
  Leave that variable absent/false during setup and validation.
- Before setting it true, configure the `production` environment with reviewed
  protection/approval rules and main-only deployment restrictions. Merely naming
  an environment in YAML does not establish those protections.
- Publishing is serialized within the new repository. This does **not** serialize
  it with publishers in the old repository: disable and drain those first.
- All three images must pass their security gates before the first push. Pushing
  multiple image tags is not atomic; retain known-good digests for rollback.
  Secret scans write temporary JSON on the runner, not public logs or SARIF
  artifacts. A failed scan blocks publishing; reproduce it privately from the exact
  revision rather than attach a possibly sensitive report to a public issue.
- New image coordinates are
  `ghcr.io/scowalt/ignite-for-spotify-app/{backend,backup,frontend}`. Do not grant the
  public repository access to legacy private package history: GitHub warns that
  forks may also gain package access. Package visibility alone is not a fork-access
  boundary. Only inspected, secret-free artifacts with appropriate notices/source
  coverage may be published to the new namespace.
- Production Compose explicitly retains project name `ignite-for-spotify`, so its
  data/backup/proxy volumes retain their existing identities. All three app image
  references support digest overrides. Render and validate the configuration with
  `scripts/verify-production-config.py` before any separately approved deployment;
  the validator never deploys or prints environment values.
- No production Doppler token is needed by this workflow. Set only the reviewed
  public client variables `VITE_POSTHOG_KEY` and `VITE_SENTRY_DSN` in `production`.
  The four approved environment inputs are managed by the isolated IaC root; the
  upload secret is securely provisioned outside Terraform. `VITE_SENTRY_DSN` must
  use isolated frontend project 8, not legacy project 1. Keep old Doppler build
  inputs unchanged until the old publisher is fenced. `LOCAL_SQLITE_CUTOVER_COMPLETE=true`
  reflects the already-verified deployment, not a new database migration. Missing
  values fail the publishing job.
- Optional source-map upload requires `GLITCHTIP_SOURCEMAPS_ENABLED=true` and the
  environment-scoped `GLITCHTIP_AUTH_TOKEN`. Keep this enabled for the eventual
  operational handover unless the owner explicitly approves dropping source-map
  observability. Never substitute a broader incident-management token silently.
  Maps are removed from the frontend image input even if upload fails. See
  [isolated routing and pinned-tool compatibility](source-map-compatibility.md);
  the new token has only `project:releases` and no legacy-organization membership.
  No release finalization is performed. Keep logs/artifacts free of sensitive data.
- Actions cache keys/artifacts must never be a channel from untrusted PR execution
  into privileged release commands. Publishing checks out its own trusted revision
  and rebuilds; it does not execute a PR artifact.

## Full migration checklist (operator approval required)

1. Review the exact clean-root snapshot, dependency obligations and test evidence.
   Approve new-repository creation, push and publication; do not fork the private
   repository. Preserve the old repository, including unreviewed historical data,
   privately. Old evidence need not be deleted to publish this independent snapshot.
2. Configure equivalent main protection: strict `backend`, `frontend`, `backup`
   checks, conversation resolution and no force pushes/deletions. Keep the controller
   job non-required. Verify actual API/UI settings, not only successful Actions runs.
3. Move ongoing development entrypoints: contributor documentation, local checkout
   remotes, BB/project configuration and agent workspaces. Review outstanding old
   branches/PRs individually and replay approved changes onto the new root without
   merging old ancestry. Recreate needed issues without copying sensitive history.
   Update references to moved work and stop routine development in the old repo.
4. Configure Renovate/GitHub App repository selection, bot/webhook/integration
   targets and minimum required token access for the new repository. Confirm these
   operate only on the intended target. Disable old-repository automation as part
   of the coordinated handover, not during unrelated preparation.
5. Keep owner-retired Paseo dispatch inactive. Do not install a replacement or
   provision controller credentials. Retained code/tests are historical; cleanup
   of old services/state/history remains a separate action. GlitchTip SDK error
   reporting and source-map uploads remain maintained.
6. Reconcile infrastructure through [the adoption plan](../../infra/README.md).
   `infra/` retains the old private repository, DNS/backups and existing state key.
   `infra/public-source/` adopts the existing public repository in distinct state
   and owns its protected environment/release inputs. Publication is enabled only
   through the separately approved exclusive-publisher handover. **Never change
   the old root's repository name to simulate a move.** Preserve the exact existing
   public branch protection, including `backup`'s app binding: the pinned provider
   cannot model this policy for a user-owned repository, so a read-only policy
   guard verifies it without importing it into a weaker resource. No state
   ownership or environment provisioning is implied by committed definitions.
7. Record current deployed image digests and backup/readiness evidence using an
   explicitly approved live inspection. Fence old publishers and drain/cancel any
   authorized in-flight release runs before enabling the new publisher. Updating
   a Watchtower-consumed tag is a deployment, not a harmless setup test.
8. Complete the [first-release and rollback procedure](fresh-image-cutover.md),
   provision only approved environment access, and authorize one release from the
   validated new-repository commit. Verify new-package pulls before changing image
   references, then verify deployed digests, readiness and data/backup continuity. Do not recreate volumes,
   rerun the SQLite cutover, change DNS or rotate credentials as a side effect.
9. Confirm all development entrypoints, retained bots/integrations, infrastructure workflow,
   CI and CD now point to the public repository, with no active writer/publisher on
   the old repository. Keep the latter private for history. Archiving it is optional
   and requires separate approval. Remove temporary staging resources only when
   their evidence is preserved; do not delete shared caches or other projects' work.

The checklist is complete with the verification records in TASK-38 through TASK-40,
the linked operating runbooks, and the explicit owner-accepted BB limitation above.
A passing local candidate, a public repo, or a first successful build alone would
not have established completion.
