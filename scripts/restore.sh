#!/usr/bin/env bash
# Restore CC sessions from a snapshot file
# Usage: cc restore [snapshot-file]
#
# Safety: if CC sessions are already running, skip restore to prevent
# the runaway pane-explosion bug (continuum restore → cc restore → doubles panes).

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

# Guard: don't restore if claude is already running in any pane
# pane_current_command may report as version number (e.g. "2.1.68") instead of "claude",
# so also check for running claude processes via ps
active_claude_panes=$(pgrep -f 'claude.*--resume' 2>/dev/null | wc -l | tr -d ' ')
if [[ "$active_claude_panes" -gt 0 ]]; then
    echo "cc restore: $active_claude_panes CC session(s) already running — skipping to prevent duplicates" >&2
    exit 0
fi

SNAPSHOT_DIR="$HOME/.claude/snapshots"
claude_bin=$(get_claude_binary)
claude_flags=$(get_claude_flags)
projects_dir=$(get_projects_dir)

exec python3 "$CURRENT_DIR/snapshot_restore.py" restore "$SNAPSHOT_DIR" "$projects_dir" "$claude_bin" "$claude_flags" "${1:-}"
