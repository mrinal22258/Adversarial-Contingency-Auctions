#!/usr/bin/env bash
set -euo pipefail

# Double-Blind Review Release Packager
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Building double-blind review release archive..."
python3 "${REPO_ROOT}/tools/make_release.py" "$@"
