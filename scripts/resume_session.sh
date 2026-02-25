#!/usr/bin/env bash
# Resume a Claude Code session by keyword search

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

main() {
	local keyword="$*"
	if [[ -z "$keyword" ]]; then
		display_message "Usage: cc resume <keywords>"
		return 1
	fi

	local projects_dir
	projects_dir=$(get_projects_dir)
	local claude_bin
	claude_bin=$(get_claude_binary)
	local claude_flags
	claude_flags=$(get_claude_flags)

	local result
	result=$(CLAUDE_PROJECTS_DIR="$projects_dir" \
		python3 "$CURRENT_DIR/session_search.py" search $keyword)

	if [[ -z "$result" ]]; then
		display_message "No session found matching '$keyword'"
		return 1
	fi

	local session_file="${result%%	*}"
	local launch_dir="${result##*	}"
	local session_id
	session_id=$(basename "$session_file" .jsonl)

	if [[ ! -d "$launch_dir" ]]; then
		launch_dir="$HOME"
	fi

	local cmd="env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT $claude_bin --resume '$session_id' $claude_flags; exec zsh"

	# Try split-window first; fall back to new-window if no space
	if ! tmux split-window -c "$launch_dir" "$cmd" 2>/dev/null; then
		tmux new-window -n "$keyword" -c "$launch_dir" "$cmd"
	fi
	tmux select-pane -T "$keyword"
	tmux select-layout tiled
	display_message "Resumed: $session_id"
}
main "$@"
