#!/usr/bin/env bash
set -euo pipefail

# Cookidoo Recipe Exporter
# Exports all saved recipes from cookidoo.es to a JSON file

# Check for required environment variables
if [[ -z "${COOKIDOO_USERNAME:-}" ]]; then
    echo "Error: COOKIDOO_USERNAME environment variable must be set" >&2
    exit 1
fi

if [[ -z "${COOKIDOO_PASSWORD:-}" ]]; then
    echo "Error: COOKIDOO_PASSWORD environment variable must be set" >&2
    exit 1
fi

# Run the exporter using uvx
# --from . installs from current directory
uvx --from . cookido-agent
