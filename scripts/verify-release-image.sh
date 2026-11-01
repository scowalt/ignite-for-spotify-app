#!/bin/sh
set -eu
component="${1:?component required}"
image="${2:?local image required}"
output="${3:?report directory required}"
case "$component" in backend|frontend|backup) ;; *) exit 2 ;; esac
case "$image" in
  "ignite-verify-$component:"*|"ghcr.io/scowalt/ignite-for-spotify-app/$component:"*) ;;
  *) printf '%s\n' 'Unexpected image namespace.' >&2; exit 2 ;;
esac
mkdir -p "$output"
private=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/ignite-image-check.XXXXXX")
container=
cleanup() {
  if [ -n "$container" ]; then docker rm --volumes "$container" >/dev/null; fi
}
trap cleanup EXIT
if ! trivy image --quiet --image-src docker --scanners secret --format json \
  --output "$private/secrets.json" --exit-code 1 "$image"; then
  printf '%s\n' 'Secret scan failed; no raw findings or image reports are published.' >&2
  exit 1
fi
if ! trivy image --quiet --image-src docker --scanners vuln --ignore-unfixed \
  --severity HIGH,CRITICAL --format json --output "$private/vulnerabilities.json" \
  --exit-code 1 "$image"; then
  printf '%s\n' 'Fixable HIGH/CRITICAL vulnerability gate failed; reproduce privately.' >&2
  exit 1
fi
trivy image --quiet --image-src docker --format cyclonedx --output "$private/sbom.json" "$image"
container=$(docker create --network none --read-only --entrypoint /bin/true "$image")
mkdir -p "$private/notices"
docker cp "$container:/usr/share/licenses/ignite/." "$private/notices/"
if [ "$component" = frontend ]; then
  mkdir -p "$private/frontend-notices"
  docker cp "$container:/srv/third-party-licenses/." "$private/frontend-notices/"
fi
python3 scripts/verify-image-reports.py "$component" "$image" "$private" "$output"
printf '%s\n' "$component: security gates and component notice-file checks passed."
