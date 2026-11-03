# Dependency automation handover

The maintained source is `scowalt/ignite-for-spotify-app`. Legacy private history,
checkouts and dependency branches are preserved. The reviewed updates merged through
public PR #12, after which legacy PRs #276/#236 were closed as superseded. The old
repository's main `renovate.json` stays disabled; private retirement PR #280 removed
only its invalid `bunInstall` option. No history was rewritten or old publisher reactivated.

## Maintained policy

- Use the existing Mend Renovate integration through the new repository config.
  Hosted access and an enabled scan were verified on November 3, 2026; see the
  run and bot-authored dashboard evidence below. No new installation or broader
  repository permissions were needed.
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

The observed legacy inventory contained those two dependency PRs and configuration
warning issue #279 (not an ordinary dependency dashboard). They were dispositioned
with handover comments; the warning's invalid option was corrected while keeping
Renovate disabled. The private retirement PR passed all required checks; its existing
retired controller job remains non-required and was not activated or opportunistically
repaired. No private ancestry, old data-bearing file or unrelated work was copied.

Hosted coverage is verified by [Mend job d877cbee-0047-424e-a676-d99925459dd9](https://developer.mend.io/github/scowalt/ignite-for-spotify-app/-/job/d877cbee-0047-424e-a676-d99925459dd9),
completed November 3, 2026 at 13:00:46 UTC using Renovate `44.204.0`. The run reported
`result: done`, `status: onboarded`, `enabled: true`, and `onboarded: true`, detected
161 dependency entries, and emitted no warning/error-level log messages. Renovate
created [Dependency Dashboard #17](https://github.com/scowalt/ignite-for-spotify-app/issues/17).
The dashboard confirms major updates awaiting approval, scheduled grouped non-major
updates, and detection of both source-built Restic/Caddy version-and-commit pairs.
No approval or schedule bypass was requested. The xUnit deprecation advisory is a
normal dependency follow-up, not an integration failure.

The two October 31 jobs marked `DONE` were not sufficient evidence: the latest of
those reported `disabled-by-config` and skipped the repository. A fresh scan was
requested through the existing portal's **Actions → Run Renovate scan** after the
enabled configuration reached main. Legacy configuration and disabled publishing
were independently rechecked and remain inactive. No credentials, App permissions,
publisher settings, production services or private history changed during this check.

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

TASK-39 records completion of live bot verification and legacy work disposition.
