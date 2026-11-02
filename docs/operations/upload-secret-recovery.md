# Upload-secret delivery recovery

The first publication run reached source-map injection but the upload step received
an empty `SENTRY_AUTH_TOKEN` and returned 401. Registry login and all image pushes
were skipped. Both publishers were fenced; desired new publication is false too.
No publication retry or live upload was authorized by this recovery.

## Protected comparison

Temporary diagnostics used normal required-owner approval, the same main-only
`production` environment and the same existing secret. Jobs had no workflow-token
permissions, checkout/action dependencies, upload/registry/service commands or
credential outputs beyond constant presence status.

| Run | Direct environment | Reusable without mapping | Declared reusable |
| --- | --- | --- | --- |
| [41484155322](https://github.com/scowalt/ignite-for-spotify-app/actions/runs/41484155322), `b952036` | Present | Absent | Absent without mapping |
| [41486334373](https://github.com/scowalt/ignite-for-spotify-app/actions/runs/41486334373), `f98579b` | Present | Absent | Present with single-name mapping |

Only the explicit caller mapping changed between comparisons. Declaration alone did
not deliver the environment secret. The mapped job received it without a repository-level
copy, broad inheritance, credential replacement or scope change.

[GitHub documents this contract](https://docs.github.com/en/actions/sharing-automations/reusing-workflows#using-inputs-and-secrets-in-a-reusable-workflow):
the caller must pass the secret name even if its value exists only in the environment;
the called job's environment value takes precedence. Omitting the mapping silently
resolves the secret to an empty string. A required declaration catches omission of
the caller's name but does not validate its runtime value.

## Maintained repair and verification limits

The CI caller now maps only `GLITCHTIP_AUTH_TOKEN`, and the publisher declares that
name required. The existing protected environment remains the value's owner. An early
configuration guard rejects an empty credential when source maps are enabled, before
frontend build or upload. Tests exercise the actual guard body with synthetic
present/absent values and enforce the exact caller/callee contract. The pinned
source-map protocol fixture remains credential-free and unchanged.

Temporary diagnostic workflows and their temporary safety tests were removed after
evidence capture. History and recorded results remain available. No credential values,
hashes or lengths were emitted by the probes; no re-provisioning was needed.

The comparisons verify the secret-delivery boundary, not actual GlitchTip authentication,
artifact processing or symbolication. Both publishers remain fenced. Publication retry
requires separate approval, exact-head validation and the normal environment review.
Keep the isolated token's scope, environment protections and existing runtime unchanged.
