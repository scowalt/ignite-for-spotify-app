# Infrastructure ownership and adoption

**Runtime cutover is complete, but publishing remains intentionally fenced.**
Source policy desires true while the live flag is false; do not apply merely to
remove this recorded safety drift. Publisher/updater activation needs separate review. Committed
configuration alone is not proof of live values or deployment. Run infrastructure from
the public source checkout, but keep the two ownership roots separate. New source
ownership does not require renaming existing operational identities.

| Root | Resources | R2 state key in existing `opentofu-state` bucket |
| --- | --- | --- |
| `infra/` | Old private repository, its protection/default branch, existing DNS and backup bucket | `ignite-for-spotify/terraform.tfstate` (unchanged) |
| `infra/public-source/` | Public repository/default branch, protected environment/main-only policy, reviewed publisher flag and four release variables | `ignite-for-spotify-app/github.tfstate` (new, separate state) |

The public root has no Cloudflare provider, DNS, server, backup or legacy-repository
resources. The existing root retains its resource addresses, inputs, outputs and backend.
Never change `infra/`'s `repository_name` to the public name or copy/move its state into
the new root. Its repository outputs intentionally continue to identify the legacy repo.
Both roots' maintained source now lives in the public repository.

## Offline validation

Use OpenTofu 1.13.2 and the committed public-root provider lock. Native S3 state
locking is encoded in the backend. Existing installations must retain the same key
and locking during any separately authorized reinitialization. The former minimum
`1.16.4` was unsatisfiable with the latest published OpenTofu release at verification;
only that minimum was corrected in the legacy root. Its backend/resources are unchanged.

From the repository root, with cloud/GitHub credentials absent:

```sh
tofu -chdir=infra/public-source init -backend=false -input=false -lockfile=readonly
tofu -chdir=infra/public-source fmt -check -recursive
tofu -chdir=infra/public-source validate
tofu -chdir=infra/public-source test
```

Provider installation accesses the public registry; mock-provider plan tests make no
GitHub/cloud API calls. CI never runs a real plan, import or apply and has no production
credentials. The existing required `backup` aggregate also gates this validation.
Mock success is not evidence that a live plan is empty or that credentials can administer
GitHub. Never reuse the test mock state as real state.

## Existing policy: preserve, do not weaken on import

The public repository is **ID 1441388195**, `scowalt/ignite-for-spotify-app`, public,
with default branch `main`. The data-source guard refuses a different ID, visibility
or default branch. The repository resource matches the reviewed merge settings:
auto-merge and automatic branch deletion remain off. It and the environment/default
branch/policy have destruction guards; deletion from configuration still requires
plan review and is not authorized by these guards.

Current main protection is recorded in `public-source/main-protection.json`:
strict `backend`, `frontend`, `backup`, with `backup` bound to GitHub Actions app
15368, conversation resolution, and no force pushes/deletions. The controller remains
non-required. The pinned provider cannot manage this **exact** user-owned policy:
its GraphQL resource models context names only, while its REST resource retains
app bindings but rejects non-organization owners. Consequently, this root does not
import/create a weaker branch-protection resource or replace it with a ruleset.
Retain existing settings and verify the declarative policy before and after adoption:

```bash
set -euo pipefail
test "$(gh api repos/scowalt/ignite-for-spotify-app --jq .id)" = 1441388195
gh api repos/scowalt/ignite-for-spotify-app/branches/main/protection \
  | python3 scripts/verify-public-main-protection.py
test "$(gh api repos/scowalt/ignite-for-spotify-app/actions/permissions/workflow \
  --jq '(.default_workflow_permissions == "read" and .can_approve_pull_request_reviews == false)')" = true
```

This validator is read-only and prints no supplied values on failure. A policy mismatch
requires review, not an automatic rewrite. Repository workflow-token defaults are also
outside the pinned provider's resource support; preserve their existing read-only/no-PR-
approval setting and do not mistake `github_actions_repository_permissions` (allowed
Actions) for a workflow-token-permission resource.

## Protected production environment

The separately approved setup was applied and verified with:

- Exact branch policy `main`, not all protected branches and not a matching tag.
- Reviewer Scott Walters (GitHub user ID 1100550), with admin bypass disabled.
- Self-review permitted so a sole owner can approve their manually initiated release;
  approval is still required. Revisit this policy explicitly if another reviewer joins.
- Repository publish-enable variable still desires `true` from the completed approved
  publication retry, but the live variable is intentionally `false`. Both publishers
  and the existing Watchtower remain paused after the completed runtime cutover.
  Preserve these fences until a separate continuing-CD/activation decision; no apply
  or activation is implied by desired-state drift.

### Release-input staging

`release-inputs.tf` owns exactly four environment variables:

| Variable | Approved value/source |
| --- | --- |
| `VITE_POSTHOG_KEY` | Existing browser key from app Doppler `prd` |
| `VITE_SENTRY_DSN` | Public DSN from isolated GlitchTip project **8**, organization `ignite-for-spotify-app-frontend` |
| `LOCAL_SQLITE_CUTOVER_COMPLETE` | `true`, confirming the existing verified deployment; never a request to rerun migration |
| `GLITCHTIP_SOURCEMAPS_ENABLED` | `true`, effective only when the separately gated publisher runs |

The two required Terraform inputs are `frontend_posthog_key` and
`frontend_sentry_dsn`. Supply them through a private process environment. They are
**public browser values** and are stored in private state, but are marked sensitive
for plan-output redaction. Missing/non-public analytics keys, wrong DSN hosts and
legacy project DSNs are rejected. CI tests supply only synthetic values; CI does
not fetch real inputs.

The operator/API upload credential is different: it remains managed in Doppler and
is securely transferred as environment secret `GLITCHTIP_AUTH_TOKEN`, outside Terraform.
There is deliberately no plaintext-token input/resource in this root. Keep runtime
credentials, broad Doppler/incident tokens and operator secret values out of code,
plans, logs and Terraform state. Use only the dedicated non-admin identity's
`project:releases` token for the isolated organization.

Keep the old publisher's inputs unchanged. In particular, do not set the generic
Doppler `VITE_SENTRY_DSN` while it can still be injected into old-repository builds.
The new environment receives project 8's value directly from reviewed GlitchTip
metadata. Staging these inputs neither uploads maps nor publishes/deploys images.

## Later adoption — separate authorization required

1. Verify current repo ID, settings, protection and disabled publishing using read-only
   APIs. Inventory resource addresses in the **existing** state privately through the
   approved mechanism. Stop if any new-repository resource is already managed there
   or in Mission Control; do not dual-manage it or move unrelated state.
2. Approve backend/credential access and establish the new state key without changing
   the legacy key, bucket or state. Use existing approved credentials without displaying
   them. Initialization is a live state-access operation, not the offline CI command.
3. Import the already-existing objects into the new root; never attempt to recreate them:

   ```sh
   tofu -chdir=infra/public-source import github_repository.app ignite-for-spotify-app
   tofu -chdir=infra/public-source import github_branch_default.main ignite-for-spotify-app
   ```

4. The public repository/default branch, environment/policy and false publish flag
   were adopted/applied in this handover. Recheck actual state before any import;
   do not recreate them. For additional already-existing values, use the provider's
   documented import identity rather than overwriting unmanaged configuration.
   Environment import ID is `ignite-for-spotify-app:production`; deployment-policy import
   is `ignite-for-spotify-app:production:<verified-policy-id>`; Actions-variable import is
   `ignite-for-spotify-app:PRODUCTION_PUBLISHING_ENABLED`. Import does not authorize apply.
5. Review a private plan. Initial adoption permitted only the environment, main policy
   and false publishing flag. The separately approved CI-staging extension permits only
   four release-variable additions from the sources above, plus the dedicated secret
   transfer outside Terraform. Stop for repository replacement, unexpected setting
   updates, deletes, legacy resources, operator credentials in Terraform, or other drift.
   Do not use broad `ignore_changes` or targeted apply to hide it. Execute
   only the exact approved changes; obtain a new review for any additional effect.
   Recheck values privately, protections and disabled publishing after provisioning.
6. The separately approved first-publication extension permits only the publication
   flag change from false to true, after old Deploy workflow 218752864 is fenced/drained.
   It does not authorize running-container cutover. Verify the exact run/head before
   required owner environment approval. On a failed gate/upload/access check, fence the
   new flag false and stop, leaving the old publisher fenced. Record emergency drift;
   a later apply must not silently restore publication before a reviewed recovery.
   Do not enable Renovate/Paseo as a provisioning side effect.

No first release, deployed digest, backup continuity or complete operational migration
is claimed by these definitions. Continue with the [application cutover](../docs/operations/fresh-image-cutover.md)
only after its distinct prerequisites and approval.

## Provider/tool evidence

- [OpenTofu 1.13.2 release](https://github.com/opentofu/opentofu/releases/tag/v1.13.2).
- [Repository](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/docs/resources/repository.md),
  [default branch](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/docs/resources/branch_default.md),
  [environment](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/docs/resources/repository_environment.md)
  and [deployment policy](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/docs/resources/repository_environment_deployment_policy.md)
  at pinned provider 6.13.0.
- [REST protection owner check](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/github/resource_github_branch_protection_v3.go)
  and [organization guard](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/github/util.go);
  [GraphQL context-only representation](https://github.com/integrations/terraform-provider-github/blob/v6.13.0/github/util_v4_branch_protection.go).
