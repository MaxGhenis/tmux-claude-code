"""Tests for get_session_id_from_process()."""

from conftest import FAKE_UUID, FAKE_UUID2, make_completed_process
from snapshot_restore import get_session_id_from_process


class TestGetSessionIdFromProcess:
    """3-tier detection: --resume args → lsof on claude → lsof on grandchildren."""

    def test_extracts_resume_id_from_args(self, mock_run):
        mock_run.add("pgrep", make_completed_process("2000\n"))
        mock_run.add("ps", make_completed_process(
            f"/usr/local/bin/claude --resume '{FAKE_UUID}'"
        ))
        sid, pid = get_session_id_from_process(1000)
        assert sid == FAKE_UUID
        assert pid == "2000"

    def test_resume_id_without_quotes(self, mock_run):
        mock_run.add("pgrep", make_completed_process("2000\n"))
        mock_run.add("ps", make_completed_process(
            f"/usr/local/bin/claude --resume {FAKE_UUID}"
        ))
        sid, pid = get_session_id_from_process(1000)
        assert sid == FAKE_UUID

    def test_falls_back_to_lsof_on_claude_pid(self, mock_run):
        mock_run.add("pgrep", make_completed_process("2000\n"))
        # ps shows claude but no --resume
        mock_run.add("ps", make_completed_process("/usr/local/bin/claude"))
        # lsof on claude pid finds the JSONL
        lsof_output = f"p2000\nn/path/{FAKE_UUID}.jsonl\n"
        mock_run.add("lsof", make_completed_process(lsof_output))
        sid, pid = get_session_id_from_process(1000)
        assert sid == FAKE_UUID
        assert pid == "2000"

    def test_falls_back_to_grandchild_lsof(self, mock_run):
        # pgrep finds claude child
        mock_run.add("pgrep", make_completed_process("2000\n"), call_index=0)
        # ps shows claude but no --resume
        mock_run.add("ps", make_completed_process("/usr/local/bin/claude"))
        # lsof on claude pid finds nothing
        mock_run.add("lsof", make_completed_process("p2000\n"), call_index=0)
        # pgrep finds grandchildren of claude
        mock_run.add("pgrep", make_completed_process("3000\n3001\n"), call_index=1)
        # lsof on first grandchild finds the JSONL
        lsof_output = f"p3000\nn/path/{FAKE_UUID}.jsonl\n"
        mock_run.add("lsof", make_completed_process(lsof_output), call_index=1)
        sid, pid = get_session_id_from_process(1000)
        assert sid == FAKE_UUID
        assert pid == "2000"

    def test_returns_none_none_when_no_children(self, mock_run):
        mock_run.add("pgrep", make_completed_process("", returncode=1))
        sid, pid = get_session_id_from_process(1000)
        assert sid is None
        assert pid is None

    def test_returns_none_sid_with_claude_pid_when_no_session(self, mock_run):
        mock_run.add("pgrep", make_completed_process("2000\n"), call_index=0)
        mock_run.add("ps", make_completed_process("/usr/local/bin/claude"))
        # lsof finds nothing
        mock_run.add("lsof", make_completed_process(""), call_index=0)
        # No grandchildren
        mock_run.add("pgrep", make_completed_process("", returncode=1), call_index=1)
        sid, pid = get_session_id_from_process(1000)
        assert sid is None
        assert pid == "2000"

    def test_skips_non_claude_children(self, mock_run):
        # pgrep finds two children
        mock_run.add("pgrep", make_completed_process("2000\n2001\n"))
        # First child is vim, not claude
        mock_run.add("ps", make_completed_process("vim file.py"), call_index=0)
        # Second child is claude
        mock_run.add("ps", make_completed_process(
            f"/usr/local/bin/claude --resume '{FAKE_UUID}'"
        ), call_index=1)
        sid, pid = get_session_id_from_process(1000)
        assert sid == FAKE_UUID
        assert pid == "2001"

    def test_empty_pgrep_lines_ignored(self, mock_run):
        mock_run.add("pgrep", make_completed_process("\n\n2000\n\n"))
        mock_run.add("ps", make_completed_process(
            f"/usr/local/bin/claude --resume '{FAKE_UUID}'"
        ))
        sid, pid = get_session_id_from_process(1000)
        assert sid == FAKE_UUID
