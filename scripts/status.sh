#!/usr/bin/env bash
# Status bar: count active Claude Code panes
# Must be fast — runs on every status refresh

# Count unique pane PIDs to avoid double-counting across linked sessions
seen_pids=""
count=0
while IFS=$'\t' read -r pane_id pane_pid cmd; do
	case "$seen_pids" in
		*":$pane_pid:"*) continue ;;
	esac
	seen_pids="$seen_pids:$pane_pid:"

	if [[ "$cmd" == "claude" ]]; then
		((count++))
		continue
	fi

	if [[ -n "$pane_pid" ]] && pgrep -P "$pane_pid" -x "claude" >/dev/null 2>&1; then
		((count++))
	fi
done < <(tmux list-panes -a -F '#{pane_id}	#{pane_pid}	#{pane_current_command}' 2>/dev/null)

if [[ "$count" -gt 0 ]]; then
	echo "CC:${count}"
fi
