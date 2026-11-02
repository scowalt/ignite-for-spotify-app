# GlitchTip source-map compatibility

The maintained application still uses GlitchTip; retirement of Paseo dispatch does
not retire SDK reporting or source maps. Production uses hidden maps, injects debug
IDs, and uploads before deleting `.map` files from the frontend image input.
When source-map uploading is enabled, a failed upload now fails the publisher before
any image push. This fail-closed behavior is part of the approved first-publication
handover. A successful publication is still not a runtime deployment.

## Isolated frontend target

The upload workflow targets organization `ignite-for-spotify-app-frontend`, project
slug `ignite-for-spotify-frontend` (project ID **8**). The protected environment's
`VITE_SENTRY_DSN` must reference that project. Legacy frontend project 1 and backend
project 2 remain in `scowalt`; their history and identities are unchanged.

The dedicated API-only identity has no password login, staff/superuser status or
legacy-organization membership. Its token grants only `project:releases`, which the
inspected GlitchTip 6.2.6 upload endpoints accept. The token's issuing identity belongs
only to the new organization, containing only project 8. Preserve this invariant:
teams do not provide project isolation within a GlitchTip organization.

Credential and routing staging do not activate the new DSN in running production.
Enable publication only through the approved exclusive-publisher handover, and
verify actual upload success for the exact release run. Operator read tooling can opt into the new org:

```sh
GLITCHTIP_ORG=ignite-for-spotify-app-frontend scripts/glitchtip list --project 8
```

This uses the separate operator credential, not the CI upload token. Default CLI
queries still target `scowalt`. Mission Control's single-org reader is a separate
integration follow-up; no claims are made that it already includes the new target.

## Protected credential delivery

The CI caller explicitly passes only `GLITCHTIP_AUTH_TOKEN`; the reusable publisher
requires that name in its `workflow_call` contract and still binds `production` on
its job. The value remains an environment secret, with existing approval and main-only
policy. Do not copy it to repository scope or use broad `secrets: inherit`.

[GitHub requires explicit forwarding even for environment-only secrets](https://docs.github.com/en/actions/sharing-automations/reusing-workflows#using-inputs-and-secrets-in-a-reusable-workflow).
A declaration alone silently receives an empty value when the caller omits the
mapping. `required: true` enforces the caller's name, not runtime nonempty presence.
The release-configuration step separately rejects an empty credential when source
maps are enabled, before building the frontend or attempting any upload.

Protected presence-only comparisons verified direct delivery, failure without caller
mapping, and successful delivery after adding only the named mapping. See
[the recovery evidence](upload-secret-recovery.md). The credential was not rotated,
re-provisioned or broadened. These checks do not establish live GlitchTip upload success.

## Pinned command and no-finalization requirement

The deploy workflow pins `@sentry/cli@3.8.2` and invokes:

```sh
npx --yes @sentry/cli@3.8.2 sourcemaps inject frontend/dist
npx --yes @sentry/cli@3.8.2 sourcemaps upload frontend/dist
```

These are dedicated debug-ID artifact-bundle commands, without a release name or
release-finalization command. **Version 3.8.2 does not accept `--no-finalize` on
`sourcemaps upload`.** Adding that flag would fail argument parsing, not make the
upload safer. The workspace's intent to avoid release finalization is met by this
non-finalizing command path, verified below; no production upload command change
was necessary. Do not substitute `releases new/finalize` or add a release environment
variable as an unrelated migration step.

## Credential-free evidence and regression test

The upstream release binary was checked against its published SHA-256 digest; its
version/help and command source were inspected. `scripts/test_sourcemap_protocol.py`
also runs the exact workflow command arguments against a disposable loopback fixture,
with an isolated home, synthetic source/map, dummy authentication and CI-like metadata.
It verifies debug-ID injection, a real chunk payload and exactly these request surfaces:

- GET organization chunk-upload options.
- POST organization artifact-bundle assembly.
- POST fixture chunk upload.

All other fixture endpoints, including PUT/release finalization, reject requests.
Assertions reject release metadata or additional requests. No real GlitchTip host,
credential, event, user source or production state is accessed. The fixture server
uses an OS-assigned loopback port and is stopped after the test; it is not a shared
development server.

The frontend CI job installs the pinned tool in runner-temporary storage and runs
the protocol test. Other script-test runs still enforce the exact workflow commands
but skip the binary-dependent fixture unless `SENTRY_CLI_EXECUTABLE` is provided:

```sh
SENTRY_CLI_EXECUTABLE=/absolute/path/to/sentry-cli \
  python3 -m unittest discover -s scripts -p test_sourcemap_protocol.py -v
```

This proves the pinned client's no-finalization behavior against the supported
artifact-bundle contract. It does **not** prove the deployed GlitchTip version,
project/organization routing or production credential accepts those requests.
At the separately approved first release, verify actual upload success before
switching application services. A successful upload command alone does not prove
server-side processing or symbolication. Stop for missing credentials, endpoint
incompatibility or upload failure rather than silently removing observability.

## Primary sources

- [Pinned command parser/execution](https://github.com/getsentry/sentry-cli/blob/3.8.2/src/commands/sourcemaps/upload.rs):
  supported arguments and artifact upload, without a finalize operation.
- [Pinned file-upload implementation](https://github.com/getsentry/sentry-cli/blob/3.8.2/src/utils/file_upload.rs):
  standalone artifact assembly and chunk upload.
- [Upstream protocol tests](https://github.com/getsentry/sentry-cli/blob/3.8.2/tests/integration/sourcemaps/upload.rs).
- [GlitchTip JavaScript source-map documentation](https://glitchtip.com/sdkdocs/javascript/#source-maps)
  currently recommends its own CLI. A tool switch is not implied by this preparation;
  this repository retains and tests its existing pinned Sentry client. Live compatibility
  remains a first-release verification surface.
