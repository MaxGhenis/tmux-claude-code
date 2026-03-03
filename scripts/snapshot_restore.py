#!/usr/bin/env python3
"""Snapshot and restore CC sessions across tmux panes."""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def tmux(*args):
    return run(["tmux", *args])


def get_pane_list():
    """Get all tmux panes with metadata."""
    r = tmux(
        "list-panes", "-a", "-F",
        "#{window_name}\t#{pane_index}\t#{pane_id}\t#{pane_pid}\t#{pane_current_command}"
    )
    panes = []
    for line in r.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 5:
            panes.append({
                "window": parts[0],
                "pane": int(parts[1]),
                "pane_id": parts[2],
                "shell_pid": int(parts[3]),
                "command": parts[4],
            })
    return panes


def get_session_id_from_lsof(pid):
    """Find the CC session ID by checking which JSONL file the process has open."""
    r = run(["lsof", "-p", str(pid), "-Fn"])
    for line in r.stdout.split("\n"):
        if line.startswith("n") and line.endswith(".jsonl"):
            path = line[1:]
            # Skip subagent files
            if "/subagents/" in path:
                continue
            # Extract session ID from filename
            basename = os.path.basename(path)
            session_id = basename.replace(".jsonl", "")
            # Validate it looks like a UUID
            if re.match(r"^[a-f0-9-]{36}$", session_id):
                return session_id
    return None


def get_session_id_from_process(shell_pid):
    """Extract CC session ID from process tree."""
    r = run(["pgrep", "-P", str(shell_pid)])
    if r.returncode != 0:
        return None, None

    for cpid in r.stdout.strip().split("\n"):
        cpid = cpid.strip()
        if not cpid:
            continue
        r2 = run(["ps", "-p", cpid, "-o", "args="])
        args = r2.stdout.strip()
        if "claude" not in args:
            continue

        # Method 1: Extract --resume ID from args
        m = re.search(r"--resume\s+'?([a-f0-9-]+)", args)
        if m:
            return m.group(1), cpid

        # Method 2: Check open JSONL files via lsof
        session_id = get_session_id_from_lsof(cpid)
        if session_id:
            return session_id, cpid

        # Method 3: Check child processes of claude (node, etc.)
        r3 = run(["pgrep", "-P", cpid])
        if r3.returncode == 0:
            for grandchild in r3.stdout.strip().split("\n"):
                grandchild = grandchild.strip()
                if grandchild:
                    session_id = get_session_id_from_lsof(grandchild)
                    if session_id:
                        return session_id, cpid

        return None, cpid

    return None, None


def get_process_cwd(pid):
    """Get the cwd of a process (macOS)."""
    r = run(["lsof", "-p", str(pid), "-a", "-d", "cwd", "-Fn"])
    for line in r.stdout.split("\n"):
        if line.startswith("n/"):
            return line[1:]
    return None


def snapshot(snapshot_dir, projects_dir):
    """Save current layout to a snapshot file."""
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    panes = get_pane_list()
    entries = []
    seen_sessions = set()

    for p in panes:
        # Skip non-CC panes (idle shells)
        if p["command"] in ("zsh", "bash"):
            continue

        session_id, claude_pid = get_session_id_from_process(p["shell_pid"])

        # Get cwd
        cwd = None
        if claude_pid:
            cwd = get_process_cwd(claude_pid)
        if not cwd:
            cwd = get_process_cwd(p["shell_pid"])

        if session_id and session_id not in seen_sessions:
            seen_sessions.add(session_id)
            entries.append({
                "window": p["window"],
                "pane": p["pane"],
                "session": session_id,
                "cwd": cwd or str(Path.home()),
            })

    # Don't overwrite good snapshots with empty ones
    if not entries:
        print("No active CC sessions found — skipping snapshot to preserve last good state")
        return

    snapshot_file = snapshot_dir / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "panes": entries,
    }

    with open(snapshot_file, "w") as f:
        json.dump(data, f, indent=2)

    latest = snapshot_dir / "latest.json"
    latest.unlink(missing_ok=True)
    latest.symlink_to(snapshot_file)

    print(f"Saved {len(entries)} CC sessions to {snapshot_file}")


def restore(snapshot_dir, projects_dir, claude_bin="claude", claude_flags="", snapshot_file=None):
    """Restore sessions from a snapshot."""
    snapshot_dir = Path(snapshot_dir)

    if snapshot_file:
        sf = Path(snapshot_file)
    else:
        sf = snapshot_dir / "latest.json"

    if not sf.exists():
        print(f"No snapshot found at {sf}", file=sys.stderr)
        print("Run 'cc snapshot' first to save your layout.", file=sys.stderr)
        sys.exit(1)

    with open(sf) as f:
        data = json.load(f)

    panes_to_restore = data["panes"]
    if not panes_to_restore:
        print("Snapshot is empty — nothing to restore.", file=sys.stderr)
        sys.exit(1)

    print(f"Restoring from: {sf}")
    print(f"Timestamp: {data['timestamp']}")
    print(f"Sessions: {len(panes_to_restore)}")
    print()

    # Group by window
    by_window = {}
    for p in panes_to_restore:
        by_window.setdefault(p["window"], []).append(p)

    # Get current windows
    r = tmux("list-windows", "-F", "#{window_name}\t#{window_panes}")
    existing = {}
    for line in r.stdout.strip().split("\n"):
        if "\t" in line:
            name, count = line.split("\t")
            existing[name] = int(count)

    # Ensure windows exist, create panes via split-window
    for win_name, win_panes in by_window.items():
        needed = len(win_panes)
        if win_name not in existing:
            tmux("new-window", "-d", "-n", win_name)
            existing[win_name] = 1
            print(f"Created window '{win_name}'")

        for _ in range(needed - existing.get(win_name, 0)):
            tmux("split-window", "-t", win_name, "-d")
            time.sleep(0.15)
        tmux("select-layout", "-t", win_name, "tiled")

    # Get fresh pane listing
    current_panes = get_pane_list()

    # Build available idle panes per window
    idle_by_window = {}
    for p in current_panes:
        if p["command"] in ("zsh", "bash"):
            idle_by_window.setdefault(p["window"], []).append(p)

    restored = 0
    failed = 0

    for entry in panes_to_restore:
        win = entry["window"]
        session_id = entry["session"]
        cwd = entry.get("cwd", str(Path.home()))

        # Get an idle pane in this window
        idle = idle_by_window.get(win, [])
        if not idle:
            print(f"SKIP   {win}:{entry['pane']} {session_id[:8]} — no idle pane")
            failed += 1
            continue

        pane = idle.pop(0)

        # Build resume command
        parts = [f"cd {cwd}"]
        cmd = f"{claude_bin} --resume '{session_id}'"
        if claude_flags:
            cmd += f" {claude_flags}"
        parts.append(cmd)
        full_cmd = " && ".join(parts)

        tmux("send-keys", "-t", pane["pane_id"], full_cmd, "Enter")
        print(f"OK     {win}:{pane['pane']} → {session_id[:8]}")
        restored += 1
        time.sleep(0.5)  # Stagger to avoid fork-pressure segfault

    print(f"\nRestored {restored} sessions ({failed} skipped)")


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "snapshot":
        snapshot(sys.argv[2], sys.argv[3])
    elif action == "restore":
        snapshot_dir = sys.argv[2]
        projects_dir = sys.argv[3]
        claude_bin = sys.argv[4] if len(sys.argv) > 4 else "claude"
        claude_flags = sys.argv[5] if len(sys.argv) > 5 else ""
        snapshot_file = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else None
        restore(snapshot_dir, projects_dir, claude_bin, claude_flags, snapshot_file)
