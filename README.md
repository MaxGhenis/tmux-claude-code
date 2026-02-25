# tmux-claude-code

Manage [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions in tmux. Search past conversations by keyword, resume them in the right directory, and browse sessions interactively.

## Features

- **`prefix-c`** — New Claude Code pane (or `prefix-C` for a named one)
- **`prefix-C-r`** — Resume a session by keyword (searches transcript content)
- **`prefix-C-b`** — Browse all sessions with fzf preview
- **`cc list`** — List recent sessions with status (active/inactive)
- **`cc detect`** — Show which panes are running Claude Code
- **Status bar** — Active CC session count in your tmux status line

### Session search

The killer feature: search across all your Claude Code session transcripts by keyword. It checks the first few user messages of every session, excludes currently active ones, resolves the correct working directory, and opens a new pane with `claude --resume`.

```
cc resume nextladder proposal    # finds and resumes the matching session
cc resume fix ctc phaseout       # keyword search across all transcripts
```

### Smart pane detection

Correctly identifies Claude Code in tmux panes even when `pane_current_command` reports `zsh` (common when CC is launched via `zsh -c "claude ...; exec zsh"`). Uses a three-tier approach:

1. Check `pane_current_command`
2. Check child processes via `pgrep`
3. Content-based fallback (CC prompt markers)

## Install

### With [TPM](https://github.com/tmux-plugins/tpm) (recommended)

Add to `~/.tmux.conf`:

```tmux
set -g @plugin 'MaxGhenis/tmux-claude-code'
```

Then press `prefix-I` to install.

### Manual

```bash
git clone https://github.com/MaxGhenis/tmux-claude-code ~/.tmux/plugins/tmux-claude-code
```

Add to `~/.tmux.conf`:

```tmux
run-shell ~/.tmux/plugins/tmux-claude-code/claude-code.tmux
```

### CLI wrapper (optional)

For shell access to `cc` commands:

```bash
ln -sf ~/.tmux/plugins/tmux-claude-code/cc ~/bin/cc
```

## Configuration

All options have sensible defaults. Add to `~/.tmux.conf` to customize:

```tmux
# Key bindings
set -g @claude_code_new_key 'c'        # prefix-c: new session
set -g @claude_code_resume_key 'C-r'   # prefix-C-r: resume by keyword
set -g @claude_code_browse_key 'C-b'   # prefix-C-b: fzf browser

# Claude binary and flags
set -g @claude_code_binary 'claude'
set -g @claude_code_flags '--dangerously-skip-permissions'

# Session data location (usually auto-detected)
set -g @claude_code_projects_dir "$HOME/.claude/projects"
```

## How it works

- Sessions are stored as JSONL files in `~/.claude/projects/`. Each project directory encodes the working directory in its folder name.
- `cc resume` searches these files for keyword matches, decodes the project path (cross-referencing the JSONL `cwd` field), and opens `claude --resume <id>` in the correct directory.
- When the current tmux window is full (can't split), it automatically falls back to creating a new window.
- All pane creation uses `env -u CLAUDECODE` to prevent Claude Code from detecting a nested session.

## Dependencies

- tmux 3.2+ (for `display-popup`)
- Python 3.6+
- [fzf](https://github.com/junegunn/fzf) (optional, for `cc browse` / `prefix-C-b`)

## License

MIT
