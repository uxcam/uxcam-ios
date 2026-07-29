#!/bin/bash
set -euo pipefail

readonly MAX_TRACKED_BYTES=$((5 * 1024 * 1024))
readonly FORBIDDEN_PATTERN='\.(a|framework|xcframework|zip)$'

failure=0
while IFS= read -r -d '' file; do
  size="$(wc -c < "$file" | tr -d '[:space:]')"
  if (( size > MAX_TRACKED_BYTES )); then
    echo "error: tracked file exceeds 5 MiB: $file ($size bytes)" >&2
    failure=1
  fi
  if [[ "$file" =~ $FORBIDDEN_PATTERN ]]; then
    echo "error: binary distribution file must not be tracked: $file" >&2
    failure=1
  fi
done < <(git ls-files -z)

if (( failure != 0 )); then
  exit 1
fi

tracked_bytes="$(git ls-files -z | xargs -0 wc -c | tail -1 | awk '{print $1}')"
echo "Tracked working-tree size: ${tracked_bytes:-0} bytes"
