#!/usr/bin/env bash

get_tmux_option() {
	local option="$1"
	local default_value="$2"
	local option_value
	option_value=$(tmux show-option -gqv "$option")
	if [ -z "$option_value" ]; then
		echo "$default_value"
	else
		echo "$option_value"
	fi
}

set_tmux_option() {
	local option="$1"
	local value="$2"
	tmux set-option -gq "$option" "$value"
}

display_message() {
	tmux display-message "$1"
}

get_claude_binary() {
	get_tmux_option "$claude_binary_option" "$default_claude_binary"
}

get_claude_flags() {
	get_tmux_option "$claude_flags_option" "$default_claude_flags"
}

get_projects_dir() {
	get_tmux_option "$claude_projects_dir_option" "$default_claude_projects_dir"
}

# Detect if a pane is running Claude Code
# Uses three signals: command name, child process, content markers
is_claude_pane() {
	local pane_id="$1"

	# Signal 1: pane_current_command is "claude" or starts with a version number
	local cmd
	cmd=$(tmux display -t "$pane_id" -p '#{pane_current_command}' 2>/dev/null)
	if [[ "$cmd" == "claude" ]]; then
		return 0
	fi

	# Signal 2: child process named "claude"
	local pane_pid
	pane_pid=$(tmux display -t "$pane_id" -p '#{pane_pid}' 2>/dev/null)
	if [[ -n "$pane_pid" ]] && pgrep -P "$pane_pid" -x "claude" >/dev/null 2>&1; then
		return 0
	fi

	# Signal 3: content-based fallback
	local content
	content=$(tmux capture-pane -t "$pane_id" -p -S -10 2>/dev/null)
	if echo "$content" | grep -qE '(bypass permissions|⏵⏵|esc to interrupt|Context left until)'; then
		return 0
	fi

	return 1
}
