# Public repository handover

**Status: prepared, not activated.** The intended authoritative repository is
`scowalt/ignite-for-spotify-app`. Until an explicitly approved operational cutover,
the existing private repository and production deployment remain unchanged.

The destination must become the only home for ongoing development, issues and pull
requests, dependency updates, automated remediation, GitHub Actions CI and production
publishing. This is not a permanent public mirror. The old private repository retains
historical evidence only after handover. Do not copy its Git ancestry, database
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
  now aggregates backup tests and all three non-publishing release-image checks; it
  runs even when a dependency fails and fails closed. No branch-protection setting
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
  `LOCAL_SQLITE_CUTOVER_COMPLETE=true` must reflect the already-verified deployment,
  not trigger a new database migration. Missing values fail the publishing job.
- Optional source-map upload requires `GLITCHTIP_SOURCEMAPS_ENABLED=true` and the
  environment-scoped `GLITCHTIP_AUTH_TOKEN`. Maps are removed from the frontend
  image input even if upload fails. Keep logs/artifacts free of sensitive data.
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
5. Migrate the in-repo GlitchTip/Paseo controller deliberately. Its allowlist accepts
   only the new repository; old/fork targets are rejected. Before starting it, pause
   the old dispatcher, inventory in-flight jobs/PR associations and preserve state.
   Do not rewrite pending jobs to the new repo or replay old jobs blindly. Review
   generated public PR content for private error/session data. Install/repoint the
   existing controller rather than create a duplicate. Legacy cleanup remains an
   unrelated opt-in action, not a way to retire this controller.
6. Reconcile infrastructure ownership separately. `infra/main.tf` still describes
   the old private repository and its existing state may also manage DNS/backups.
   **Do not apply it with a changed repository name.** Prepare reviewed, separate
   new-repository resources/state ownership; preserve the old repository resource,
   DNS, server and backup bucket. The new repository must ultimately own the
   maintained infrastructure definitions, not depend on ongoing old-repo changes.
7. Record current deployed image digests and backup/readiness evidence using an
   explicitly approved live inspection. Fence old publishers and drain/cancel any
   authorized in-flight release runs before enabling the new publisher. Updating
   a Watchtower-consumed tag is a deployment, not a harmless setup test.
8. Complete the [first-release and rollback procedure](fresh-image-cutover.md),
   provision only approved environment access, and authorize one release from the
   validated new-repository commit. Verify new-package pulls before changing image
   references, then verify deployed digests, readiness and data/backup continuity. Do not recreate volumes,
   rerun the SQLite cutover, change DNS or rotate credentials as a side effect.
9. Confirm all development entrypoints, bots, controller, infrastructure workflow,
   CI and CD now point to the public repository, with no active writer/publisher on
   the old repository. Keep the latter private for history. Archiving it is optional
   and requires separate approval. Remove temporary staging resources only when
   their evidence is preserved; do not delete shared caches or other projects' work.

The handover is complete only after the final item is evidenced. A passing local
candidate, a public repo, or a first successful build alone is not completion.
