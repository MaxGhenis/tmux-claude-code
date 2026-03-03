#!/usr/bin/env bash
# Restore CC sessions from a snapshot file
# Usage: cc restore [snapshot-file]

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

SNAPSHOT_DIR="$HOME/.claude/snapshots"
claude_bin=$(get_claude_binary)
claude_flags=$(get_claude_flags)
projects_dir=$(get_projects_dir)

exec python3 "$CURRENT_DIR/snapshot_restore.py" restore "$SNAPSHOT_DIR" "$projects_dir" "$claude_bin" "$claude_flags" "${1:-}"
