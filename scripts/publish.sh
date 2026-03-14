#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$REPO_ROOT/publish-config.json"

if [ ! -f "$CONFIG" ]; then
    echo "Error: publish-config.json not found at $CONFIG"
    exit 1
fi

# Parse project entries from config using python3 (more portable than jq)
projects=$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    config = json.load(f)
for p in config['projects']:
    print(f\"{p['source']}|{p['target']}|{p['entry']}\")
" "$CONFIG")

if [ -z "$projects" ]; then
    echo "No projects configured in publish-config.json"
    exit 0
fi

while IFS='|' read -r source target entry; do
    src_dir="$REPO_ROOT/_source/$source"
    tgt_dir="$REPO_ROOT/projects/$target"

    # Check if source directory exists and has real content (not just .gitkeep)
    real_files=$(find "$src_dir" -not -name '.gitkeep' -not -path "$src_dir" 2>/dev/null | head -1)
    if [ -z "$real_files" ]; then
        echo "SKIP: $source (source directory empty or missing)"
        continue
    fi

    mkdir -p "$tgt_dir"
    rsync -av --delete --exclude='.gitkeep' "$src_dir/" "$tgt_dir/"
    echo "PUBLISHED: $source -> projects/$target (entry: $entry)"
done <<< "$projects"

echo "Done."
