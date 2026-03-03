"""Tests for helper functions: get_pane_list(), get_process_cwd()."""

from conftest import make_completed_process
from snapshot_restore import get_pane_list, get_process_cwd


class TestGetPaneList:
    """Parse tmux list-panes output."""

    def test_parses_multi_pane_output(self, mock_run):
        mock_run.add("tmux", make_completed_process(
            "claude\t0\t%0\t1000\tclaude\n"
            "claude\t1\t%1\t1001\tzsh\n"
            "work\t0\t%2\t1002\tvim\n"
        ))
        panes = get_pane_list()
        assert len(panes) == 3
        assert panes[0]["window"] == "claude"
        assert panes[0]["pane"] == 0
        assert panes[0]["pane_id"] == "%0"
        assert panes[0]["shell_pid"] == 1000
        assert panes[0]["command"] == "claude"
        assert panes[2]["window"] == "work"

    def test_returns_empty_on_no_output(self, mock_run):
        mock_run.add("tmux", make_completed_process(""))
        panes = get_pane_list()
        assert panes == []

    def test_skips_malformed_lines(self, mock_run):
        mock_run.add("tmux", make_completed_process(
            "claude\t0\t%0\t1000\tclaude\n"
            "bad line\n"
            "work\t0\t%2\t1002\tvim\n"
        ))
        panes = get_pane_list()
        assert len(panes) == 2

    def test_handles_single_pane(self, mock_run):
        mock_run.add("tmux", make_completed_process("main\t0\t%0\t500\tzsh\n"))
        panes = get_pane_list()
        assert len(panes) == 1
        assert panes[0]["shell_pid"] == 500


class TestGetProcessCwd:
    """Extract cwd from lsof output."""

    def test_extracts_cwd_path(self, mock_run):
        mock_run.add("lsof", make_completed_process(
            "p1234\n"
            "fcwd\n"
            "n/Users/max/project\n"
        ))
        assert get_process_cwd(1234) == "/Users/max/project"

    def test_returns_none_on_no_cwd(self, mock_run):
        mock_run.add("lsof", make_completed_process("p1234\n"))
        assert get_process_cwd(1234) is None

    def test_returns_none_on_error(self, mock_run):
        mock_run.add("lsof", make_completed_process("", returncode=1))
        assert get_process_cwd(1234) is None

    def test_handles_paths_with_spaces(self, mock_run):
        mock_run.add("lsof", make_completed_process(
            "p1234\n"
            "n/Users/max/my project/src\n"
        ))
        assert get_process_cwd(1234) == "/Users/max/my project/src"
