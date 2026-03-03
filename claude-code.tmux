#!/usr/bin/env bash
# tmux-claude-code: manage Claude Code sessions in tmux
# https://github.com/MaxGhenis/tmux-claude-code

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/scripts/helpers.sh"
source "$CURRENT_DIR/scripts/variables.sh"

set_new_session_binding() {
	local key
	key=$(get_tmux_option "$new_session_key_option" "$default_new_session_key")
	tmux bind-key "$key" run-shell \
		"env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT '$CURRENT_DIR/scripts/new_session.sh'"
}

set_named_session_binding() {
	tmux bind-key C command-prompt -p "name:" \
		"run-shell \"env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT '$CURRENT_DIR/scripts/new_session.sh' '%%'\""
}

set_resume_binding() {
	local key
	key=$(get_tmux_option "$resume_key_option" "$default_resume_key")
	tmux bind-key "$key" command-prompt -p "resume keyword:" \
		"run-shell \"env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT '$CURRENT_DIR/scripts/resume_session.sh' '%%'\""
}

set_browse_binding() {
	local key
	key=$(get_tmux_option "$browse_key_option" "$default_browse_key")
	tmux bind-key "$key" display-popup -w 90% -h 80% -E \
		"env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT '$CURRENT_DIR/scripts/browse_sessions.sh'"
}

setup_status_interpolation() {
	local status_right
	status_right="$(get_tmux_option "status-right" "")"
	local script="#($CURRENT_DIR/scripts/status.sh)"
	if ! [[ "$status_right" == *"status.sh"* ]]; then
		set_tmux_option "status-right" "${script} ${status_right}"
	fi
}

setup_auto_snapshot() {
	# Auto-snapshot every 5 minutes via tmux timer
	# Uses a background hook that checks elapsed time
	local interval
	interval=$(get_tmux_option "@claude_snapshot_interval" "300")
	local script="$CURRENT_DIR/scripts/snapshot.sh"
	# Set a periodic hook (fires every 60s on any client activity)
	# Only actually snapshots if interval has elapsed
	tmux set-hook -g pane-focus-in \
		"run-shell -b 'SNAP_DIR=\"$HOME/.claude/snapshots\"; INTERVAL=$interval; LAST=\"\$SNAP_DIR/.last_auto\"; NOW=\$(date +%s); if [ -f \"\$LAST\" ]; then PREV=\$(cat \"\$LAST\"); else PREV=0; fi; if [ \$((NOW - PREV)) -ge \$INTERVAL ]; then echo \$NOW > \"\$LAST\"; \"$script\" > /dev/null 2>&1; fi'"
}

main() {
	set_new_session_binding
	set_named_session_binding
	set_resume_binding
	set_browse_binding
	setup_status_interpolation
	setup_auto_snapshot
}
main
