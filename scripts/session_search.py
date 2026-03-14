#!/usr/bin/env python3
"""Search Claude Code session transcripts.

Usage:
    session_search.py search <keywords...>   # Find best session matching keywords
    session_search.py list [--limit N]       # List recent sessions
    session_search.py list --format=fzf      # List in fzf-compatible format
    session_search.py preview <session_id>   # Show conversation excerpt
    session_search.py dir <session_id>       # Print working directory for session
"""
import json, os, glob, sys, time, re, subprocess


PROJECTS_DIR = os.environ.get(
    "CLAUDE_PROJECTS_DIR", os.path.expanduser("~/.claude/projects")
)


# ---------------------------------------------------------------------------
# Path decoding
# ---------------------------------------------------------------------------

def decode_project_path(encoded):
    """Decode project folder name to real path via greedy directory matching."""
    raw = encoded.lstrip("-")
    parts = raw.split("-")
    path = "/"
    i = 0
    while i < len(parts):
        matched = False
        for j in range(len(parts), i, -1):
            candidate = os.path.join(path, "-".join(parts[i:j]))
            if os.path.isdir(candidate):
                path = candidate
                i = j
                matched = True
                break
        if not matched:
            path = os.path.join(path, parts[i])
            i += 1
    return path


def get_cwd_from_jsonl(filepath):
    """Extract cwd from early JSONL records."""
    try:
        with open(filepath) as f:
            for i, line in enumerate(f):
                if i > 10:
                    break
                obj = json.loads(line)
                cwd = obj.get("cwd")
                if cwd and os.path.isdir(cwd):
                    return cwd
    except Exception:
        pass
    return None


def get_session_dir(filepath):
    """Get working directory for a session.

    Cross-references the decoded folder name with the cwd field in the JSONL.
    """
    folder = os.path.basename(os.path.dirname(filepath))
    decoded = decode_project_path(folder)
    jsonl_cwd = get_cwd_from_jsonl(filepath)

    if jsonl_cwd and os.path.isdir(jsonl_cwd):
        return jsonl_cwd
    if os.path.isdir(decoded):
        return decoded
    return os.path.expanduser("~")


# ---------------------------------------------------------------------------
# Active session detection
# ---------------------------------------------------------------------------

def get_active_session_ids():
    ids = set()
    try:
        out = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "claude" in line and "--resume" in line:
                m = re.search(r"--resume[= ]*([a-f0-9-]+)", line)
                if m:
                    ids.add(m.group(1))
    except Exception:
        pass
    for f in glob.glob(os.path.join(PROJECTS_DIR, "*/*.jsonl")):
        if time.time() - os.path.getmtime(f) < 120:
            ids.add(os.path.basename(f).replace(".jsonl", ""))
    return ids


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

def should_skip(msg):
    s = msg.strip()
    if "Claude Code v" in msg[:500] or s.startswith("continue"):
        return True
    if s.startswith("<teammate-message"):
        return True
    if len(s) < 3:
        return True
    return False


def extract_user_messages(filepath, limit=5):
    """Extract first N real user messages from a session."""
    messages = []
    try:
        with open(filepath) as f:
            for line in f:
                obj = json.loads(line)
                if obj.get("type") != "user":
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content if isinstance(c, dict)
                    )
                content = str(content).strip()
                if should_skip(content):
                    continue
                messages.append(content)
                if len(messages) >= limit:
                    break
    except Exception:
        pass
    return messages


def extract_preview(filepath, max_turns=4):
    """Extract a conversation preview (user + assistant turns)."""
    lines = []
    try:
        with open(filepath) as f:
            for raw in f:
                obj = json.loads(raw)
                role = obj.get("type")
                if role not in ("user", "assistant"):
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content if isinstance(c, dict) and c.get("text")
                    )
                content = str(content).strip()
                if role == "user" and should_skip(content):
                    continue
                if not content:
                    continue
                label = "You" if role == "user" else "CC"
                # Truncate long messages
                if len(content) > 200:
                    content = content[:200] + "..."
                lines.append(f"{label}: {content}")
                if len(lines) >= max_turns:
                    break
    except Exception:
        pass
    return lines


# ---------------------------------------------------------------------------
# Session listing
# ---------------------------------------------------------------------------

def get_all_sessions():
    """Return list of (filepath, session_id, mtime) sorted by recency."""
    sessions = []
    for f in glob.glob(os.path.join(PROJECTS_DIR, "*/*.jsonl")):
        # Skip subagent files
        if "/subagents/" in f:
            continue
        sid = os.path.basename(f).replace(".jsonl", "")
        mtime = os.path.getmtime(f)
        sessions.append((f, sid, mtime))
    sessions.sort(key=lambda x: x[2], reverse=True)
    return sessions


def format_age(mtime):
    delta = time.time() - mtime
    if delta < 60:
        return "now"
    if delta < 3600:
        return f"{int(delta/60)}m ago"
    if delta < 86400:
        return f"{int(delta/3600)}h ago"
    return f"{int(delta/86400)}d ago"


def shorten_path(path):
    home = os.path.expanduser("~")
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def extract_searchable_text(filepath, limit=500):
    """Extract searchable text: user msgs, assistant msgs, tool file paths."""
    parts = []
    try:
        with open(filepath) as f:
            for line in f:
                if len(" ".join(parts)) > limit * 20:
                    break
                obj = json.loads(line)
                role = obj.get("type")
                if role not in ("user", "assistant"):
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict):
                            if c.get("type") == "text":
                                t = c.get("text", "")[:300]
                                if not t.strip().startswith("<"):
                                    parts.append(t)
                            elif c.get("type") == "tool_use":
                                inp = c.get("input", {})
                                fp = inp.get("file_path", "") or inp.get("command", "")[:100] or inp.get("pattern", "") or ""
                                if fp:
                                    parts.append(fp)
    except Exception:
        pass
    return " ".join(parts)


def cmd_search(keywords, limit=0):
    kws = [kw.lower() for kw in keywords]
    active = get_active_session_ids()
    sessions = get_all_sessions()

    found = 0
    for filepath, sid, mtime in sessions:
        if sid in active:
            continue
        # Build searchable text: folder + user/assistant msgs + tool file paths
        folder = os.path.basename(os.path.dirname(filepath)).lstrip("-")
        searchable = (folder + " " + extract_searchable_text(filepath)).lower()
        if all(kw in searchable for kw in kws):
            launch_dir = get_session_dir(filepath)
            print(f"{filepath}\t{launch_dir}")
            found += 1
            if limit and found >= limit:
                break
    return 0 if found else 1


def cmd_list(limit=20, fmt="table"):
    active = get_active_session_ids()
    sessions = get_all_sessions()

    for filepath, sid, mtime in sessions[:limit]:
        status = "\033[32m●\033[0m" if sid in active else "\033[90m○\033[0m"
        age = format_age(mtime)
        cwd = shorten_path(get_session_dir(filepath))
        msgs = extract_user_messages(filepath, limit=1)
        first_msg = msgs[0][:60] if msgs else "(empty)"

        if fmt == "fzf":
            # fzf format: session_id <tab> display string
            plain_status = "*" if sid in active else " "
            print(f"{sid}\t{plain_status} {age:>8}  {cwd:<35}  {first_msg}")
        else:
            print(f"  {status}  {age:>8}  {cwd:<35}  {first_msg}")


def cmd_preview(session_id):
    # Find the session file
    for f in glob.glob(os.path.join(PROJECTS_DIR, "*/*.jsonl")):
        if "/subagents/" in f:
            continue
        if os.path.basename(f).replace(".jsonl", "") == session_id:
            cwd = shorten_path(get_session_dir(f))
            mtime = os.path.getmtime(f)
            age = format_age(mtime)
            print(f"Session: {session_id}")
            print(f"Project: {cwd}")
            print(f"Age:     {age}")
            print("─" * 50)
            for line in extract_preview(f, max_turns=8):
                print(line)
                print()
            return 0
    print(f"Session not found: {session_id}", file=sys.stderr)
    return 1


def cmd_dir(session_id):
    for f in glob.glob(os.path.join(PROJECTS_DIR, "*/*.jsonl")):
        if "/subagents/" in f:
            continue
        if os.path.basename(f).replace(".jsonl", "") == session_id:
            print(get_session_dir(f))
            return 0
    print(os.path.expanduser("~"))
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: session_search.py search [--limit N] <keywords...>", file=sys.stderr)
            sys.exit(1)
        limit = 0  # 0 = all results
        args = sys.argv[2:]
        if "--limit" in args:
            idx = args.index("--limit")
            limit = int(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        elif any(a.startswith("--limit=") for a in args):
            for i, a in enumerate(args):
                if a.startswith("--limit="):
                    limit = int(a.split("=")[1])
                    args = args[:i] + args[i + 1:]
                    break
        sys.exit(cmd_search(args, limit=limit))

    elif command == "list":
        limit = 20
        fmt = "table"
        for arg in sys.argv[2:]:
            if arg.startswith("--limit"):
                limit = int(arg.split("=")[1]) if "=" in arg else int(sys.argv[sys.argv.index(arg) + 1])
            if arg == "--format=fzf":
                fmt = "fzf"
        cmd_list(limit=limit, fmt=fmt)

    elif command == "preview":
        if len(sys.argv) < 3:
            print("Usage: session_search.py preview <session_id>", file=sys.stderr)
            sys.exit(1)
        sys.exit(cmd_preview(sys.argv[2]))

    elif command == "dir":
        if len(sys.argv) < 3:
            print("Usage: session_search.py dir <session_id>", file=sys.stderr)
            sys.exit(1)
        sys.exit(cmd_dir(sys.argv[2]))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
