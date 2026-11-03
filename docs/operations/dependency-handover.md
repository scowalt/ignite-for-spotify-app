# Dependency automation handover

The maintained source is `scowalt/ignite-for-spotify-app`. Legacy private history,
checkouts and pending dependency PRs are preserved until their public replacements
are validated. The old repository's main `renovate.json` already has `enabled: false`;
retirement does not require rewriting its history or reactivating its publisher.

## Maintained policy

- Enable the existing Mend Renovate integration through the new repository config.
  Actual installation/run evidence is still required; valid JSON alone does not
  demonstrate that the App can access the repository.
- Keep minor/patch grouping and automerge through protected pull requests, with major
  updates held for dependency-dashboard approval.
- Use `platformAutomerge: false`: Renovate performs its own checked PR merge instead
  of requiring a change to the repository's existing disabled native auto-merge setting.
  Required checks/conversation resolution remain authoritative. Other contributors,
  including the bot, retain their own identities.
- Keep infrastructure-provider/module updates manual by disabling the Terraform manager
  through a package rule. Retained Watchtower and shared Alloy changes remain manual;
  Watchtower must not be revived by a dependency PR.
- Extract source-built Restic/Caddy version and commit pairs from the actual comment-free
  `ARG` declarations. The former comment-annotation matcher could not see these files.
  Keep the Caddy source and base-image versions grouped, and derive its compiled version
  string from the same argument rather than a second literal.

## Transferred open work

Legacy PR #276 requests PostHog `^1.434.15`. The public update preserves that range and
resolves exactly `1.434.15`, without reverting the previously reviewed DOMPurify/Solid
security upgrades or changing unrelated lock entries.

Legacy PR #236 requests Trivy action commit
`d2a0b60797ff03db6132bd4e2b293f9b37081297`. Its default scanner version changed upstream;
the public transfer explicitly keeps scanner `v0.72.0`, matching the independently
verified image workflow. This is an action-implementation update, not an unreviewed
scanner-policy/version migration. All actual image/security/notice gates stay mandatory.

The observed legacy open inventory contains those two Renovate PRs and one Renovate
dashboard. Close/supersede them only after the new path's replacement/run evidence is
recorded. Do not copy private ancestry, old data-bearing files or unrelated work.

## Validation evidence and sources

Renovate `44.206.2` native strict configuration validation passed. Its credential-free
local extract run found both source-built dependencies using the real regex manager;
no lookup/update/push was performed. The missing-GitHub-token warning is expected in
that deliberately credential-free extraction test, not proof of installed App access.
Frontend tests, frozen install, type checking and build passed. Existing unrelated
reactivity/build warnings were not hidden or opportunistically changed.

- [Renovate configuration options](https://docs.renovatebot.com/configuration-options/):
  platform automerge, protected PR automerge and package rules.
- [Custom regex manager](https://docs.renovatebot.com/modules/manager/regex/).
- [GitHub tags datasource](https://github.com/renovatebot/renovate/blob/main/lib/modules/datasource/github-tags/index.ts):
  tag-commit lookup and release digests.
- [Reviewed Trivy action](https://github.com/aquasecurity/trivy-action/blob/d2a0b60797ff03db6132bd4e2b293f9b37081297/action.yaml):
  explicit version input and changed default.

TASK-39 remains the completion record for live bot evidence and legacy work disposition.
