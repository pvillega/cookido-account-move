#!/usr/bin/env bash
set -euo pipefail

# Cookidoo Collection Organizer
# Flattens two-level Spanish collections to single-level English
# and removes auto-suggested recipes from custom lists
#
# Usage:
#   ./run-organize.sh <export-file.json> [--dry-run] [--region REGION]
#
# Environment variables required:
#   COOKIDOO_USERNAME  - Cookidoo account email
#   COOKIDOO_PASSWORD  - Cookidoo account password
#
# Optional environment variables:
#   COOKIDOO_REGION    - Region code (es, de, fr, it, uk, us). Default: es

# Check for required environment variables
missing_vars=()

if [[ -z "${COOKIDOO_USERNAME:-}" ]]; then
    missing_vars+=("COOKIDOO_USERNAME")
fi

if [[ -z "${COOKIDOO_PASSWORD:-}" ]]; then
    missing_vars+=("COOKIDOO_PASSWORD")
fi

if [[ ${#missing_vars[@]} -gt 0 ]]; then
    echo "Error: Missing required environment variables:" >&2
    for var in "${missing_vars[@]}"; do
        echo "  - $var" >&2
    done
    echo "" >&2
    echo "Set these in your .envrc.local file or export them before running." >&2
    exit 1
fi

# Check for export file argument
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <export-file.json> [--dry-run]" >&2
    echo "" >&2
    echo "Arguments:" >&2
    echo "  export-file.json  Path to JSON export from cookido-agent" >&2
    echo "  --dry-run         Preview changes without modifying Cookidoo" >&2
    echo "" >&2
    echo "This script will:" >&2
    echo "  1. Flatten collections: 'Verano > Pescados' -> 'Seafood'" >&2
    echo "  2. Remove [Managed] Ideas sencillas recipes from custom lists" >&2
    echo "  3. Delete old two-level collections" >&2
    exit 1
fi

# Run the organizer using uvx
exec uvx --from . cookido-organizer "$@"
