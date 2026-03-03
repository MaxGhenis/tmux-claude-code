#!/usr/bin/env bash
# CLI wrapper for tmux-claude-code
# Install: ln -sf ~/tmux-claude-code/cc ~/bin/cc

# Resolve symlinks to find the real plugin directory
PLUGIN_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || realpath "${BASH_SOURCE[0]}")")" && pwd)"

if [[ -z "$TMUX" ]]; then
	echo "Error: not inside a tmux session" >&2
	exit 1
fi

source "$PLUGIN_DIR/scripts/helpers.sh"
source "$PLUGIN_DIR/scripts/variables.sh"

case "$1" in
	resume)
		shift
		exec "$PLUGIN_DIR/scripts/resume_session.sh" "$@"
		;;
	list)
		shift
		CLAUDE_PROJECTS_DIR="$(get_projects_dir)" \
			exec python3 "$PLUGIN_DIR/scripts/session_search.py" list "$@"
		;;
	browse)
		shift
		exec "$PLUGIN_DIR/scripts/browse_sessions.sh" "$@"
		;;
	snapshot)
		shift
		exec "$PLUGIN_DIR/scripts/snapshot.sh" "$@"
		;;
	restore)
		shift
		exec "$PLUGIN_DIR/scripts/restore.sh" "$@"
		;;
	clean)
		shift
		# Kill idle shell panes (not in meta window)
		killed=0
		while IFS= read -r line; do
			pane_id="${line%%:*}"
			rest="${line#*:}"
			win="${rest%%:*}"
			cmd="${rest##*:}"
			if [[ "$cmd" =~ ^(zsh|bash)$ ]] && [[ "$win" != "meta" ]]; then
				echo "Killing idle pane $pane_id in $win"
				tmux kill-pane -t "$pane_id"
				((killed++))
			fi
		done < <(tmux list-panes -a -F '#{pane_id}:#{window_name}:#{pane_current_command}')
		echo "Killed $killed idle pane(s)"
		;;
	detect)
		shift
		# List panes with CC detection
		while IFS= read -r line; do
			pane_id="${line%%:*}"
			rest="${line#*:}"
			if is_claude_pane "$pane_id"; then
				echo "  CC  $rest"
			else
				echo "  --  $rest"
			fi
		done < <(tmux list-panes -a -F '#{pane_id}:#{pane_index} #{pane_current_command} #{pane_title}')
		;;
	"")
		exec "$PLUGIN_DIR/scripts/new_session.sh" "$@"
		;;
	*)
		# Anything else is a name for the new session
		exec "$PLUGIN_DIR/scripts/new_session.sh" "$@"
		;;
esac
