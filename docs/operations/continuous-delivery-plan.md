# Guarded continuous delivery handover

The owner approved completion of the remaining migration. Implementation/activation
is in progress; the current digest-pinned runtime remains healthy, and the existing
Watchtower and both publishers stay paused until this design is verified end to end.

## Release authority

The protected GitHub publisher remains the only producer. Fork/PR validation stays
read-only. Existing owner approval, main-only environment restriction, source-map
upload and image/security/notice gates remain mandatory.

After all three application images pass their gates and are pushed, publish a small
OCI release-record artifact in the fresh namespace. Its JSON binds exactly:

- Schema version and fixed repository identity.
- Full source commit, CI run ID/attempt/number.
- Reviewed deployment/schema compatibility fingerprint.
- Exactly backend, backup and frontend immutable registry references.

The artifact contains no credentials, application data or executable program. Publish
an immutable revision/run reference first, sign its digest using short-lived GitHub
OIDC and pinned Cosign, verify it, and only then promote one release pointer. Application
`latest` tags are not deployment authority. A failed or partial multi-image push must
never promote the pointer. Recheck current main before promotion so stale builds do
not overwrite newer release authority.

Only the protected publisher gains `id-token: write`; no static signing key or broader
repository-content credential is introduced. Cosign verification retains digest
claims, certificate/transparency-log checks, exact GitHub issuer and trusted reusable
workflow identity, repository/ref and source SHA. No insecure verification bypass.

The consumer additionally requires the matching public CI run to be completed and
successful. A visible pointer from a still-finishing workflow is deferred, not deployed.
The run must belong to repository ID 1441388195 and workflow ID 403197563, use trusted
main push/manual events and match every recorded run/source identifier.

## One updater, not another competing controller

Install one project-owned user-systemd watchdog on the existing VPS. The user manager
is already running with lingering enabled, so no global login policy change is needed.
Keep Watchtower stopped and preserve its configuration/history. The watchdog refuses
to deploy if that legacy updater is running and uses an exclusive deployment lock.

Use existing Docker registry access and approved production secret hydration; keep
runtime/backups/operator credentials off GitHub runners and out of logs/argv/state.
The watchdog does not execute deployment code downloaded from a release record.
Its installed operator implementation and policy are reviewed/versioned separately.

A release whose Compose, database-startup/schema or deployment compatibility contract
changes is blocked for manual review. Image-only automation is not blanket permission
for future schema/configuration migrations. Preserve the project, physical volumes,
retained Caddy/Alloy binds, require-existing database, credentials and all other runtime
settings. No whole-stack up, initialization, pruning, arbitrary cleanup or broad chown.

## Deployment transaction

1. Resolve one immutable release-record digest, validate its bounded schema, signature
   and successful trusted-run evidence. Reject wrong namespaces, missing components,
   unexpected contract, stale/replayed order or a previously failed release.
2. Capture current identities and durable active/rollback references. Pull/inspect the
   exact new images without starting them; require source/revision/platform and backend
   account compatibility. Prepare secret-redacted configuration and verify invariants.
3. Create a fresh encrypted backup and exact-ID isolated restore proof using the tested
   no-init/no-prune procedure and explicit existing storage budgets. Preserve repository
   identity/encryption password. Remove owned plaintext/tooling on every handled exit.
4. Recreate backend first, then backup/frontend, without builds, tag pulls or dependency
   recreation. Verify exact digests, health/readiness/static response and unchanged
   data/mounts/Caddy/Alloy. Atomically record the active set only after all checks pass.
5. On a failed mutation, perform one bounded image-only rollback to the previous set;
   never restore the database automatically. Fence that release and stop on recovery
   failure. An interrupted transaction must not be blindly retried after restart.

Durable attempt records distinguish validation, recovery proof, mutation, verification,
rollback and cleanup. Once an accepted release attempt fails, further mutation needs
an explicit operator retry/recovery action; timer polling must not repeat backups or
failed rollouts indefinitely. Waiting for CI completion is not such a mutation attempt.
Emit only fixed reason codes and non-sensitive release/state metadata to status/journal
outputs. Preserve old images and evidence needed for recovery.

## Verification surfaces

The preapproved test interfaces are:

- Release validation: bounded/strict JSON, trust/source/run binding, exact coherent
  digests, contract mismatch and replay/failure fencing. This does not prove provider
  or cryptographic compatibility by itself.
- Deployment transaction: realistic external Docker/registry/API/storage adapters,
  durable restart/partial-failure behavior, backups, health gates and one-shot rollback.
  Internal implementation structure is not the test contract.

Use vertical red/green slices, real synthetic SQLite/Restic fixtures and actual pinned
crypto/transport compatibility tests. Before enabling the timer, verify a controlled
signed release from the protected workflow, production read/verification access and a
bounded guarded deployment against the healthy baseline. Only then enable the new
publisher/updater; recheck that legacy publication and Watchtower remain disabled.

## Tool and primary-source evidence

Cosign v3.1.4 was downloaded from its upstream release and its binary checksum verified.
Its actual CLI supports exact certificate issuer/identity, GitHub workflow repository,
ref and source SHA verification flags. Production already has Docker/buildx and a
working user-systemd manager; Cosign is not installed/activated there yet.

- [Sigstore container signing](https://docs.sigstore.dev/cosign/signing/signing_with_containers/)
- [Sigstore verification](https://docs.sigstore.dev/cosign/verifying/verify/)
- [Cosign v3.1.4](https://github.com/sigstore/cosign/releases/tag/v3.1.4)
- [GitHub OIDC claims and reusable workflow identity](https://docs.github.com/en/actions/reference/security/oidc)
- [Fulcio GitHub identity implementation](https://github.com/sigstore/fulcio/blob/main/pkg/identity/github/principal.go)
- [Existing guarded runtime and recovery record](runtime-cutover-plan.md)

Keyless signing/registry compatibility is not yet claimed until the controlled live
workflow test passes. No new deployment automation is active merely because this plan
or its validation module exists.
