#!/usr/bin/env bash
# Save current tmux layout + CC session IDs to a snapshot file
# Usage: cc snapshot

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

SNAPSHOT_DIR="$HOME/.claude/snapshots"
mkdir -p "$SNAPSHOT_DIR"

projects_dir=$(get_projects_dir)

exec python3 "$CURRENT_DIR/snapshot_restore.py" snapshot "$SNAPSHOT_DIR" "$projects_dir"
