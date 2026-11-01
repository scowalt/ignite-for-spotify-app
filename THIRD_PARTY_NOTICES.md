# Third-party notices and distribution review

The root MIT license covers original Ignite code and custom artwork. It does not
relicense dependencies, third-party content, trademarks or services.

## Dependency evidence

- [`third-party/dependency-inventory.json`](third-party/dependency-inventory.json)
  records locally installed dependency versions, declared terms, primary package
  URLs and which packaged notice files were found.
- [`third-party/DEPENDENCY_LICENSES.txt`](third-party/DEPENDENCY_LICENSES.txt)
  preserves the notice/license files found in those public packages. Individual
  texts retain their own copyrights and terms. This collection is not a declaration
  that the whole application or every dependency is MIT.
- `frontend/bun.lock` and the controller's `uv.lock` retain the upstream dependency
  identities. The inventory is build-platform-specific; it does not replace those
  locks or a release-specific SBOM. Test/build tooling is included for transparency.
- Some packages declare an SPDX expression or upstream license URL without shipping
  a notice file in the inspected package. An empty `notice_files` entry records that
  gap; it does not establish absence of a license or a redistribution prohibition.
  Retrieve the appropriate upstream license/copyright notices for any such component
  actually redistributed, and review bundled subcomponents separately.

## Important terms

| Component | Declared terms | Treatment |
|---|---|---|
| Hangfire.Core / Hangfire.AspNetCore 1.8.25 | LGPL-3.0-or-later; alternatively qualifying commercial terms | No commercial entitlement is assumed. Preserve LGPL/GPL texts and upstream notices; review library-source and combined-work/relinking obligations for actual distributed assemblies/images. |
| Hangfire.Storage.SQLite 0.4.3 | MIT, copyright RaisedApp | Retain the upstream license notice. |
| caniuse-lite | CC-BY-4.0 | Retain data attribution; this dependency is not covered by Ignite's MIT license. |
| DOMPurify | MPL-2.0 OR Apache-2.0 | Upstream offers alternatives; meet the selected option's conditions for the distributed form. |
| argparse | Python-2.0 | Retain its upstream license and notices. |
| PostHog browser SDK | Apache-2.0 AND MIT | Preserve the included third-party notices as well as the wrapper's declared terms. |

The current .NET build emits separate dependency assemblies; it does not configure
single-file publishing or trimming. That observation is not a legal conclusion
about satisfying LGPL requirements for every distribution. Do not remove required
license notices using the source comment policy; legal notices have their own
review mechanism.

Primary Hangfire terms: [package](https://www.nuget.org/packages/Hangfire.Core/1.8.25),
[license choices](https://github.com/HangfireIO/Hangfire/blob/v1.8.25/LICENSE.md),
[LGPL](https://github.com/HangfireIO/Hangfire/blob/v1.8.25/COPYING.LESSER),
[GPL](https://github.com/HangfireIO/Hangfire/blob/v1.8.25/COPYING).

## Release-image notice evidence

All app images carry the original-code license and this document under
`/usr/share/licenses/ignite`. Their `components` directory contains actual shipped
Go/.NET component manifests, copied package/upstream license texts, and source
references. Go manifests are derived from the compiled binary, not every downloaded
build dependency; the effective module files and Go toolchain license are retained.
.NET manifests follow the published `deps.json` and supplement missing package
texts from pinned upstream source commits. SQLitePCLRaw 2.1.12 uses its verified
upstream v2.1.12 commit, including its Apache/SQLite notices.

The frontend also serves `third-party-licenses/manifest.json` and its notice files,
covering the conservative production Bun graph. For `tr46@0.0.3`, upstream declares
MIT but ships no standalone license file at its recorded source commit. Exact SPDX
MIT standard terms are supplied, with original package-author metadata and an
explicit note; no new copyright holder/year is invented. This is documented
supplementation, not a claim that a missing file proves absent licensing.

`verify-images.yml` builds without secrets or registry writes and checks the
existing fixable HIGH/CRITICAL and secret gates, plus notice-file coverage. A
separate frontend lockfile check covers JavaScript that binary-image scanning may
not identify after bundling. Public artifacts contain filtered component and
notice inventories, not raw image environment/history or secret findings.
Mechanical checks and scanner license labels are not legal compatibility opinions.

## Release-owner obligations

The Dockerfiles rebuild Caddy and restic with explicitly adjusted Go dependencies.
The resulting Go modules, .NET runtime/native dependencies and base OS packages
must be inventoried for the actual release image/digest, with required notices and
source/access obligations preserved. The installed-source inventory above is **not**
a complete image-license audit. Public source does not require making existing
production images public. Do not change package visibility as a side effect of the
repository migration.

No live Spotify/CustomsForge catalogs, artwork, cookies, user records or CDLC/music
are licensed by this repository's MIT license or included as an authorized data
redistribution. API/service terms and trademark rights remain separate.
