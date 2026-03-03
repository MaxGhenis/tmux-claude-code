"""Tests for snapshot()."""

import json
from pathlib import Path
from unittest.mock import patch

from conftest import FAKE_UUID, FAKE_UUID2, FAKE_UUID3, make_pane
from snapshot_restore import snapshot


class TestSnapshot:
    """Snapshot captures CC panes, deduplicates, skips empty."""

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_captures_all_cc_panes(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, shell_pid=1000, command="claude"),
            make_pane(window="claude", pane=1, shell_pid=1001, command="claude"),
        ]
        mock_session.side_effect = [
            (FAKE_UUID, "2000"),
            (FAKE_UUID2, "2001"),
        ]
        mock_cwd.return_value = "/Users/max/project"

        snapshot(str(tmp_path), "/unused")

        latest = tmp_path / "latest.json"
        assert latest.exists()
        data = json.loads(latest.resolve().read_text())
        assert len(data["panes"]) == 2
        sessions = {p["session"] for p in data["panes"]}
        assert sessions == {FAKE_UUID, FAKE_UUID2}

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_deduplicates_same_session(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, shell_pid=1000, command="claude"),
            make_pane(window="claude", pane=1, shell_pid=1001, command="claude"),
        ]
        # Both panes resolve to the same session
        mock_session.return_value = (FAKE_UUID, "2000")
        mock_cwd.return_value = "/Users/max"

        snapshot(str(tmp_path), "/unused")

        data = json.loads((tmp_path / "latest.json").resolve().read_text())
        assert len(data["panes"]) == 1

    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_skips_idle_shells(self, mock_panes, mock_session, tmp_path):
        mock_panes.return_value = [
            make_pane(command="zsh", shell_pid=1000),
            make_pane(command="bash", shell_pid=1001),
        ]
        # Should never be called since both are idle shells
        mock_session.return_value = (FAKE_UUID, "2000")

        snapshot(str(tmp_path), "/unused")

        assert not (tmp_path / "latest.json").exists()

    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_empty_snapshot_preserves_good_symlink(self, mock_panes, mock_session, tmp_path):
        # Create a pre-existing "good" snapshot
        good_file = tmp_path / "good.json"
        good_data = {"timestamp": "2025-01-01T00:00:00", "panes": [{"session": FAKE_UUID}]}
        good_file.write_text(json.dumps(good_data))
        latest = tmp_path / "latest.json"
        latest.symlink_to(good_file)

        # Now snapshot finds no CC panes
        mock_panes.return_value = [make_pane(command="zsh", shell_pid=1000)]
        mock_session.return_value = (None, None)

        snapshot(str(tmp_path), "/unused")

        # latest.json should still point to the good snapshot
        assert latest.exists()
        preserved = json.loads(latest.resolve().read_text())
        assert preserved["panes"][0]["session"] == FAKE_UUID

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_latest_symlink_points_to_new_file(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(command="claude", shell_pid=1000),
        ]
        mock_session.return_value = (FAKE_UUID, "2000")
        mock_cwd.return_value = "/Users/max"

        snapshot(str(tmp_path), "/unused")

        latest = tmp_path / "latest.json"
        assert latest.is_symlink()
        target = latest.resolve()
        assert target.name.endswith(".json")
        assert target.name != "latest.json"

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_uses_home_dir_when_cwd_unknown(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(command="claude", shell_pid=1000),
        ]
        mock_session.return_value = (FAKE_UUID, None)
        mock_cwd.return_value = None

        snapshot(str(tmp_path), "/unused")

        data = json.loads((tmp_path / "latest.json").resolve().read_text())
        assert data["panes"][0]["cwd"] == str(Path.home())

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_skips_panes_without_session_id(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(command="claude", shell_pid=1000, pane_id="%0"),
            make_pane(command="claude", shell_pid=1001, pane_id="%1"),
        ]
        # First pane has no session, second has one
        mock_session.side_effect = [
            (None, "2000"),
            (FAKE_UUID, "2001"),
        ]
        mock_cwd.return_value = "/Users/max"

        snapshot(str(tmp_path), "/unused")

        data = json.loads((tmp_path / "latest.json").resolve().read_text())
        assert len(data["panes"]) == 1
        assert data["panes"][0]["session"] == FAKE_UUID

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_preserves_window_info(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(window="work", pane=2, command="claude", shell_pid=1000),
        ]
        mock_session.return_value = (FAKE_UUID, "2000")
        mock_cwd.return_value = "/Users/max/work"

        snapshot(str(tmp_path), "/unused")

        data = json.loads((tmp_path / "latest.json").resolve().read_text())
        entry = data["panes"][0]
        assert entry["window"] == "work"
        assert entry["pane"] == 2
        assert entry["cwd"] == "/Users/max/work"

    @patch("snapshot_restore.get_process_cwd")
    @patch("snapshot_restore.get_session_id_from_process")
    @patch("snapshot_restore.get_pane_list")
    def test_three_unique_sessions_across_windows(self, mock_panes, mock_session, mock_cwd, tmp_path):
        mock_panes.return_value = [
            make_pane(window="claude", pane=0, command="claude", shell_pid=1000),
            make_pane(window="claude", pane=1, command="claude", shell_pid=1001),
            make_pane(window="work", pane=0, command="claude", shell_pid=1002),
        ]
        mock_session.side_effect = [
            (FAKE_UUID, "2000"),
            (FAKE_UUID2, "2001"),
            (FAKE_UUID3, "2002"),
        ]
        mock_cwd.return_value = "/Users/max"

        snapshot(str(tmp_path), "/unused")

        data = json.loads((tmp_path / "latest.json").resolve().read_text())
        assert len(data["panes"]) == 3
