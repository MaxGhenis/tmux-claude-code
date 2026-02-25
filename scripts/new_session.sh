#!/usr/bin/env bash
# Create a new Claude Code pane

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

main() {
	local name="${1:-$(date +%H%M%S)}"
	local working_dir="${2:-$HOME}"
	local claude_bin
	claude_bin=$(get_claude_binary)
	local claude_flags
	claude_flags=$(get_claude_flags)

	local cmd="env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT $claude_bin $claude_flags; exec zsh"

	# Try split-window first; fall back to new-window if no space
	if ! tmux split-window -c "$working_dir" "$cmd" 2>/dev/null; then
		tmux new-window -n "$name" -c "$working_dir" "$cmd"
	fi
	tmux select-pane -T "$name"
	tmux select-layout tiled
}
main "$@"
