#!/usr/bin/env python3
"""Apply a tmux pane organization plan.

Usage: organize.py --apply plan.json [--dry-run]

plan.json maps pane IDs to target window names:
  {"%123": "pe-us", "%456": "rf", ...}

Automatically:
- Creates missing windows
- Moves panes via join-pane
- Kills empty shell panes left behind
- Kills all-empty windows
- Renumbers windows 0-N with meta at 0
- Applies tiled layout to all windows
"""

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def tmux(*args):
    return run(["tmux", *args])


def get_session_name():
    r = tmux("display-message", "-p", "#{session_name}")
    return r.stdout.strip()


CC_MARKERS = re.compile(
    r"bypass|Brewed|Baked|Churned|Sautéed|Crunched|Cogitated|Effecting|"
    r"Context left|⏵⏵|esc to interrupt|auto-compact|Booping|Spinning|"
    r"Waddling|Synthesizing|Boondoggling|Cooked|Worked"
)


def pane_has_cc_content(pane_id):
    r = tmux("capture-pane", "-t", pane_id, "-p", "-S", "-20")
    return bool(CC_MARKERS.search(r.stdout))


def get_all_panes():
    r = tmux(
        "list-panes", "-a", "-F",
        "#{window_name}\t#{pane_id}\t#{pane_current_command}"
    )
    panes = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            panes.append({
                "window": parts[0],
                "pane_id": parts[1],
                "command": parts[2],
            })
    return panes


def apply_plan(plan, dry_run=False):
    """Apply a {pane_id: window_name} plan."""
    session = get_session_name()

    # Get current pane locations
    panes = get_all_panes()
    current_window = {p["pane_id"]: p["window"] for p in panes}

    # Determine moves needed
    moves = []
    for pane_id, target_window in plan.items():
        current = current_window.get(pane_id)
        if current is None:
            print(f"  SKIP {pane_id}: pane not found")
            continue
        if current != target_window:
            moves.append((pane_id, current, target_window))

    if not moves:
        print("No moves needed.")
    else:
        print(f"Moving {len(moves)} panes...")

        # Get existing windows
        r = tmux("list-windows", "-F", "#{window_name}")
        existing = set(r.stdout.strip().split("\n"))

        # Create missing target windows
        targets = set(plan.values())
        for win in sorted(targets - existing):
            if not dry_run:
                tmux("new-window", "-d", "-n", win)
            print(f"  Created window '{win}'")
            time.sleep(0.1)

        # Move panes
        moved = 0
        for pane_id, src, dst in moves:
            if dry_run:
                print(f"  {pane_id}: {src} -> {dst}")
                moved += 1
                continue
            target_spec = f"{session}:{dst}"
            result = tmux("join-pane", "-d", "-t", target_spec, "-s", pane_id)
            if result.returncode != 0:
                tmux("select-layout", "-t", target_spec, "tiled")
                result = tmux("join-pane", "-d", "-t", target_spec, "-s", pane_id)
            if result.returncode == 0:
                moved += 1
            else:
                print(f"  FAILED {pane_id} -> {dst}: {result.stderr.strip()}")
            time.sleep(0.05)

        print(f"  Moved {moved}/{len(moves)}")

    if dry_run:
        print("\n(dry run — skipping cleanup and renumber)")
        return

    # Clean up: kill empty shell panes (no CC content) in non-meta windows
    print("Cleaning empty panes...")
    panes = get_all_panes()
    by_window = defaultdict(list)
    for p in panes:
        by_window[p["window"]].append(p)

    killed_panes = 0
    for win, win_panes in by_window.items():
        if win == "meta":
            continue
        idle = [p for p in win_panes
                if p["command"] in ("zsh", "bash")
                and not pane_has_cc_content(p["pane_id"])]
        # Keep at least 1 pane per window
        for p in idle[:len(win_panes) - 1]:
            tmux("kill-pane", "-t", p["pane_id"])
            killed_panes += 1
    print(f"  Killed {killed_panes} empty pane(s)")

    # Kill all-empty windows
    print("Cleaning empty windows...")
    panes = get_all_panes()
    by_window = defaultdict(list)
    for p in panes:
        by_window[p["window"]].append(p)

    killed_windows = 0
    for win, win_panes in by_window.items():
        if win == "meta":
            continue
        if all(p["command"] in ("zsh", "bash") and not pane_has_cc_content(p["pane_id"])
               for p in win_panes):
            tmux("kill-window", "-t", f"{session}:{win}")
            killed_windows += 1
    print(f"  Killed {killed_windows} empty window(s)")

    # Renumber: meta=0, rest alphabetical 1..N
    print("Renumbering windows...")
    r = tmux("list-windows", "-F", "#{window_index}\t#{window_name}")
    windows = []
    for line in r.stdout.strip().split("\n"):
        if "\t" in line:
            idx, name = line.split("\t", 1)
            windows.append((int(idx), name))

    windows.sort(key=lambda x: (0 if x[1] == "meta" else 1, x[1]))
    moves_needed = [(old, new) for new, (old, name) in enumerate(windows) if old != new]

    if moves_needed:
        temp = 100
        for old, new in moves_needed:
            tmux("move-window", "-s", f"{session}:{old}", "-t", f"{session}:{temp + new}")
        for _, new in moves_needed:
            tmux("move-window", "-s", f"{session}:{temp + new}", "-t", f"{session}:{new}")
        print(f"  Renumbered {len(moves_needed)} window(s)")
    else:
        print("  Already in order")

    # Apply tiled layout to all windows
    r = tmux("list-windows", "-F", "#{window_index}")
    for idx in r.stdout.strip().split("\n"):
        tmux("select-layout", "-t", f"{session}:{idx.strip()}", "tiled")

    # Final state
    print("\nFinal layout:")
    r = tmux("list-windows", "-F", "  #{window_index}: #{window_name} (#{window_panes} panes)")
    print(r.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="Apply tmux pane organization plan")
    parser.add_argument("--apply", required=True, help="JSON file with {pane_id: window_name} plan")
    parser.add_argument("--dry-run", "-n", action="store_true")
    args = parser.parse_args()

    with open(args.apply) as f:
        plan = json.load(f)

    print(f"Plan: {len(plan)} panes across {len(set(plan.values()))} windows")
    apply_plan(plan, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
