"""Tests for restore()."""

import json
import sys
from unittest.mock import patch, call

import pytest

from conftest import FAKE_UUID, FAKE_UUID2, make_pane, make_completed_process
from snapshot_restore import restore


def write_snapshot(path, panes):
    """Write a snapshot file with given panes."""
    data = {"timestamp": "2025-01-01T00:00:00", "panes": panes}
    path.write_text(json.dumps(data))
    return path


class TestRestore:
    """Restore creates windows, splits panes, sends resume commands."""

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_sends_resume_command_to_idle_pane(self, mock_tmux, mock_panes, tmp_path):
        sf = write_snapshot(tmp_path / "latest.json", [
            {"window": "claude", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
        ])

        # list-windows shows the window exists
        mock_tmux.return_value = make_completed_process("claude\t1\n")
        # After window setup, get_pane_list returns an idle pane
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, pane_id="%5", command="zsh"),
        ]

        restore(str(tmp_path), "/unused", snapshot_file=str(sf))

        # Find the send-keys call
        send_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "send-keys"]
        assert len(send_calls) == 1
        args = send_calls[0][0]
        assert args[2] == "%5"  # pane_id
        assert f"--resume '{FAKE_UUID}'" in args[3]
        assert "cd /Users/max" in args[3]

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_creates_missing_window(self, mock_tmux, mock_panes, tmp_path):
        sf = write_snapshot(tmp_path / "latest.json", [
            {"window": "work", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
        ])

        # list-windows: "work" doesn't exist, only "claude" does
        mock_tmux.return_value = make_completed_process("claude\t1\n")
        mock_panes.return_value = [
            make_pane(window="work", pane=0, pane_id="%10", command="zsh"),
        ]

        restore(str(tmp_path), "/unused", snapshot_file=str(sf))

        # Should have called new-window
        new_win_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "new-window"]
        assert len(new_win_calls) == 1
        assert "-n" in new_win_calls[0][0]
        assert "work" in new_win_calls[0][0]

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_splits_panes_when_window_has_fewer(self, mock_tmux, mock_panes, tmp_path):
        sf = write_snapshot(tmp_path / "latest.json", [
            {"window": "claude", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
            {"window": "claude", "pane": 1, "session": FAKE_UUID2, "cwd": "/Users/max"},
        ])

        # Window "claude" exists with 1 pane, but we need 2
        mock_tmux.return_value = make_completed_process("claude\t1\n")
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, pane_id="%5", command="zsh"),
            make_pane(window="claude", pane=1, pane_id="%6", command="zsh"),
        ]

        restore(str(tmp_path), "/unused", snapshot_file=str(sf))

        split_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "split-window"]
        assert len(split_calls) == 1

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_skips_when_no_idle_pane(self, mock_tmux, mock_panes, tmp_path, capsys):
        sf = write_snapshot(tmp_path / "latest.json", [
            {"window": "claude", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
        ])

        mock_tmux.return_value = make_completed_process("claude\t1\n")
        # All panes are busy (running claude, not idle shells)
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, pane_id="%5", command="claude"),
        ]

        restore(str(tmp_path), "/unused", snapshot_file=str(sf))

        captured = capsys.readouterr()
        assert "SKIP" in captured.out
        # No send-keys calls
        send_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "send-keys"]
        assert len(send_calls) == 0

    def test_exits_on_empty_snapshot(self, tmp_path):
        sf = write_snapshot(tmp_path / "latest.json", [])

        with pytest.raises(SystemExit) as exc_info:
            restore(str(tmp_path), "/unused", snapshot_file=str(sf))
        assert exc_info.value.code == 1

    def test_exits_on_missing_snapshot(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            restore(str(tmp_path), "/unused")
        assert exc_info.value.code == 1

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_applies_claude_flags(self, mock_tmux, mock_panes, tmp_path):
        sf = write_snapshot(tmp_path / "latest.json", [
            {"window": "claude", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
        ])

        mock_tmux.return_value = make_completed_process("claude\t1\n")
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, pane_id="%5", command="zsh"),
        ]

        restore(str(tmp_path), "/unused", claude_flags="--dangerously-skip-permissions",
                snapshot_file=str(sf))

        send_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "send-keys"]
        assert "--dangerously-skip-permissions" in send_calls[0][0][3]

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_restores_multiple_sessions_across_windows(self, mock_tmux, mock_panes, tmp_path):
        sf = write_snapshot(tmp_path / "latest.json", [
            {"window": "claude", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
            {"window": "work", "pane": 0, "session": FAKE_UUID2, "cwd": "/Users/max/work"},
        ])

        mock_tmux.return_value = make_completed_process("claude\t1\nwork\t1\n")
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, pane_id="%5", command="zsh"),
            make_pane(window="work", pane=0, pane_id="%10", command="zsh"),
        ]

        restore(str(tmp_path), "/unused", snapshot_file=str(sf))

        send_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "send-keys"]
        assert len(send_calls) == 2
        # First session in claude window
        assert f"--resume '{FAKE_UUID}'" in send_calls[0][0][3]
        assert send_calls[0][0][2] == "%5"
        # Second session in work window
        assert f"--resume '{FAKE_UUID2}'" in send_calls[1][0][3]
        assert send_calls[1][0][2] == "%10"

    @patch("snapshot_restore.get_pane_list")
    @patch("snapshot_restore.tmux")
    def test_uses_specific_snapshot_file(self, mock_tmux, mock_panes, tmp_path):
        # Create a specific snapshot, not at latest.json
        sf = tmp_path / "specific.json"
        write_snapshot(sf, [
            {"window": "claude", "pane": 0, "session": FAKE_UUID, "cwd": "/Users/max"},
        ])

        mock_tmux.return_value = make_completed_process("claude\t1\n")
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, pane_id="%5", command="zsh"),
        ]

        restore(str(tmp_path), "/unused", snapshot_file=str(sf))

        send_calls = [c for c in mock_tmux.call_args_list if c[0][0] == "send-keys"]
        assert len(send_calls) == 1
