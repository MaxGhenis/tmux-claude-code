#!/usr/bin/env bash
# Interactive session browser using fzf

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/variables.sh"

main() {
	local projects_dir
	projects_dir=$(get_projects_dir)
	local claude_bin
	claude_bin=$(get_claude_binary)
	local claude_flags
	claude_flags=$(get_claude_flags)

	if ! command -v fzf >/dev/null 2>&1; then
		display_message "fzf required for browse — install with: brew install fzf"
		return 1
	fi

	local selected
	selected=$(CLAUDE_PROJECTS_DIR="$projects_dir" \
		python3 "$CURRENT_DIR/session_search.py" list --limit 50 --format=fzf | \
		fzf --ansi --reverse --delimiter='\t' --with-nth=2 \
			--header="Select session (enter=resume, esc=cancel)" \
			--preview="CLAUDE_PROJECTS_DIR='$projects_dir' python3 '$CURRENT_DIR/session_search.py' preview {1}" \
			--preview-window=right:50%:wrap)

	if [[ -z "$selected" ]]; then
		return 0
	fi

	local session_id="${selected%%	*}"
	local launch_dir
	launch_dir=$(CLAUDE_PROJECTS_DIR="$projects_dir" \
		python3 "$CURRENT_DIR/session_search.py" dir "$session_id")

	[[ ! -d "$launch_dir" ]] && launch_dir="$HOME"

	local cmd="env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT $claude_bin --resume '$session_id' $claude_flags; exec zsh"

	if ! tmux split-window -c "$launch_dir" "$cmd" 2>/dev/null; then
		tmux new-window -c "$launch_dir" "$cmd"
	fi
	tmux select-pane -T "resumed"
	tmux select-layout tiled
}
main "$@"
