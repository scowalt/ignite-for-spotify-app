#!/bin/sh
set -eu

modfile=$1
shift

for pin in "$@"; do
  module=${pin%@*}
  pinned=${pin#*@}
  upstream=$(go list -m -f '{{.Version}}' "$module")
  newest=$(printf '%s\n%s\n' "$upstream" "$pinned" | sort -V | tail -n 1)
  if [ "$newest" != "$pinned" ]; then
    echo "$module pin $pinned would downgrade upstream $upstream; remove the pin" >&2
    exit 1
  fi
done

go get -modfile="$modfile" "$@"
