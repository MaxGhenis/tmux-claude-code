#!/usr/bin/env bash
# Create a new Claude Code pane

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

main() {
	local name="${1:-$(date +%H%M%S)}"
	local working_dir="${2:-$HOME}"

	# Safety: refuse to create more panes if window already has too many
	local max_panes=20
	local current_panes
	current_panes=$(tmux list-panes | wc -l | tr -d ' ')
	if [ "$current_panes" -ge "$max_panes" ]; then
		tmux display-message "Too many panes ($current_panes >= $max_panes), refusing to create more"
		return 1
	fi

	local claude_bin
	claude_bin=$(get_claude_binary)
	local claude_flags
	claude_flags=$(get_claude_flags)

	local cmd="env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT $claude_bin $claude_flags; exec zsh"

	# Split after the last pane in the window; fall back to new-window if no space
	local last_pane
	last_pane=$(tmux list-panes -F '#{pane_index}' | tail -1)
	if ! tmux split-window -t "${last_pane}" -c "$working_dir" "$cmd" 2>/dev/null; then
		tmux new-window -n "$name" -c "$working_dir" "$cmd"
	fi
	tmux select-pane -T "$name"
	tmux select-layout tiled
}
main "$@"
