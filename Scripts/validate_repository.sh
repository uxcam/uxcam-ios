#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

python3 Scripts/release.py validate-manifests
python3 -m unittest discover -s Tests -v
swift package dump-package >/dev/null
Scripts/check_repository_size.sh
