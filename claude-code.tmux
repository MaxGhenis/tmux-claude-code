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

main() {
	set_new_session_binding
	set_named_session_binding
	set_resume_binding
	set_browse_binding
	setup_status_interpolation
}
main
