# Infrastructure ownership and adoption

**Definitions prepared; no live backend initialization, import or apply performed.**
Run infrastructure from the public source checkout, but keep the two ownership roots
separate. New source ownership does not require renaming existing operational identities.

| Root | Resources | R2 state key in existing `opentofu-state` bucket |
| --- | --- | --- |
| `infra/` | Old private repository, its protection/default branch, existing DNS and backup bucket | `ignite-for-spotify/terraform.tfstate` (unchanged) |
| `infra/public-source/` | Existing public repository/default branch, protected production environment, main-only deployment policy, disabled publish flag | `ignite-for-spotify-app/github.tfstate` (new, separate state) |

The public root has no Cloudflare provider, DNS, server, backup or legacy-repository
resources. The existing root retains its resource addresses, inputs, outputs and backend.
Never change `infra/`'s `repository_name` to the public name or copy/move its state into
the new root. Its repository outputs intentionally continue to identify the legacy repo.
Both roots' maintained source now lives in the public repository.

## Offline validation

Use OpenTofu 1.13.2 and the committed public-root provider lock. The former minimum
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

## Proposed protected production environment

After separate approval, the desired environment has:

- Exact branch policy `main`, not all protected branches and not a matching tag.
- Reviewer Scott Walters (GitHub user ID 1100550), with admin bypass disabled.
- Self-review permitted so a sole owner can approve their manually initiated release;
  approval is still required. Revisit this policy explicitly if another reviewer joins.
- Repository publish-enable variable explicitly `false`.

No secret/client values are defined or fetched by this root. Later secure provisioning
may set only reviewed production client variables, the existing-SQLite confirmation
and the source-map credential/flag. Keep runtime credentials, broad Doppler tokens and
secret values out of code, plans, public logs and Terraform state. Never silently reuse
a broader incident-management credential for source-map uploads.

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

4. The environment/policy/publish variable were absent at preparation time. Recheck now:
   import any that already exist rather than treating absence in this document as current.
   Environment import ID is `ignite-for-spotify-app:production`; deployment-policy import
   is `ignite-for-spotify-app:production:<verified-policy-id>`; Actions-variable import is
   `ignite-for-spotify-app:PRODUCTION_PUBLISHING_ENABLED`. Import does not authorize apply.
5. Review a private plan. Expected effects after successful imports are only the approved
   new environment, exact main policy and false publish flag. Stop for repository
   replacement, unexpected setting updates, deletes, legacy resources, secrets or any
   other drift. Do not use broad `ignore_changes` or targeted apply to hide it. Obtain
   approval for the exact plan before apply; recheck policy and disabled publishing after.
6. Keep publishing false until the separately approved exclusive-publisher handover.
   Enabling it later requires an explicit reviewed desired-state change **and** approved
   apply, after the old publisher is fenced/drained. Ad-hoc changes would drift from the
   committed false value. Do not enable Renovate/Paseo as a provisioning side effect.

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
