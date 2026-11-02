# GlitchTip source-map compatibility

The maintained application still uses GlitchTip; retirement of Paseo dispatch does
not retire SDK reporting or source maps. Production uses hidden maps, injects debug
IDs, uploads before deleting `.map` files from the frontend image input, and keeps
its existing best-effort upload behavior. The credentialed production upload is
still disabled/unexecuted during this preparation.

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
switching application services. The current upload step is best-effort, so a green
workflow alone is insufficient evidence. Stop for missing credentials, endpoint
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
