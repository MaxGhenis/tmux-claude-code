#!/usr/bin/env bash
# Status bar: count active Claude Code panes.
# Runs on every status refresh, and refreshes can overlap when runs are
# slow — so serve from a short cache behind a single-flight lock, and
# scan the process table once (one ps) instead of pgrep-per-pane.

CACHE_TTL="${CLAUDE_STATUS_CACHE_TTL:-10}"
CACHE="${TMPDIR:-/tmp}/tmux-claude-code-status.$UID"
LOCK="$CACHE.lock"

now=$(date +%s)

cached_ts=0
cached_out=""
if [[ -f "$CACHE" ]]; then
	{ IFS= read -r cached_ts; IFS= read -r cached_out; } < "$CACHE" 2>/dev/null
	[[ "$cached_ts" =~ ^[0-9]+$ ]] || cached_ts=0
fi

emit() {
	[[ -n "$1" ]] && printf '%s\n' "$1"
}

# Fresh enough — serve the cache.
if (( now - cached_ts < CACHE_TTL )); then
	emit "$cached_out"
	exit 0
fi

# Single-flight: if another instance is already computing, serve stale.
if ! mkdir "$LOCK" 2>/dev/null; then
	lock_ts=$(stat -f %m "$LOCK" 2>/dev/null || echo 0)
	if (( now - lock_ts < 60 )); then
		emit "$cached_out"
		exit 0
	fi
	# Stale lock (a previous run died) — steal it.
	rmdir "$LOCK" 2>/dev/null
	if ! mkdir "$LOCK" 2>/dev/null; then
		emit "$cached_out"
		exit 0
	fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# Count panes running claude directly, or with a direct child named
# claude — same semantics as pgrep -P <pane_pid> -x claude, but from a
# single process-table pass shared by every pane.
out=$(
	{
		# Space separator: tmux (3.6+) replaces control chars, including
		# tab, with _ in expanded format output.
		tmux list-panes -a -F '#{pane_pid} #{pane_current_command}' 2>/dev/null
		printf -- '---\n'
		ps -axo ppid=,comm=
	} | awk '
		/^---$/ { in_ps = 1; next }
		!in_ps {
			sp = index($0, " ")
			if (sp == 0) next
			pid = substr($0, 1, sp - 1)
			cmd = substr($0, sp + 1)
			if (!(pid in pane)) pane[pid] = cmd
			next
		}
		{
			line = $0
			sub(/^[ \t]+/, "", line)
			if (line !~ /^[0-9]+[ \t]/) next
			sp = match(line, /[ \t]/)
			ppid = substr(line, 1, sp - 1)
			comm = substr(line, sp + 1)
			sub(/^[ \t]+/, "", comm)
			n = split(comm, parts, "/")
			if (parts[n] == "claude") child[ppid] = 1
		}
		END {
			count = 0
			for (p in pane)
				if (pane[p] == "claude" || (p in child)) count++
			if (count > 0) printf "CC:%d\n", count
		}
	'
)

printf '%s\n%s\n' "$now" "$out" > "$CACHE"
emit "$out"

{
	SNAP_DIR="$HOME/.claude/snapshots"
	LAST="$SNAP_DIR/.last_auto"
	INTERVAL=${CLAUDE_SNAPSHOT_INTERVAL:-300}
	PREV=0
	[ -f "$LAST" ] && PREV=$(cat "$LAST" 2>/dev/null || echo 0)
	if [ $((now - PREV)) -ge "$INTERVAL" ]; then
		echo "$now" > "$LAST"
		"$(dirname "$0")/snapshot.sh" >/dev/null 2>&1
	fi
} &
disown 2>/dev/null || true
