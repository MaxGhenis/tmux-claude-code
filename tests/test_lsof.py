"""Tests for get_session_id_from_lsof()."""

from conftest import FAKE_UUID, FAKE_UUID2, make_completed_process
from snapshot_restore import get_session_id_from_lsof


class TestGetSessionIdFromLsof:
    """Find CC session UUID from open JSONL files."""

    def test_finds_uuid_jsonl(self, mock_run):
        lsof_output = (
            "p1234\n"
            f"n/Users/max/.claude/projects/-Users-max/{FAKE_UUID}.jsonl\n"
        )
        mock_run.add("lsof", make_completed_process(lsof_output))
        assert get_session_id_from_lsof(1234) == FAKE_UUID

    def test_skips_subagent_files(self, mock_run):
        lsof_output = (
            "p1234\n"
            f"n/Users/max/.claude/projects/-Users-max/subagents/{FAKE_UUID}.jsonl\n"
        )
        mock_run.add("lsof", make_completed_process(lsof_output))
        assert get_session_id_from_lsof(1234) is None

    def test_skips_non_uuid_jsonl(self, mock_run):
        lsof_output = "p1234\nn/some/path/not-a-uuid.jsonl\n"
        mock_run.add("lsof", make_completed_process(lsof_output))
        assert get_session_id_from_lsof(1234) is None

    def test_returns_none_on_no_jsonl(self, mock_run):
        lsof_output = "p1234\nn/some/path/file.txt\nn/another/file.log\n"
        mock_run.add("lsof", make_completed_process(lsof_output))
        assert get_session_id_from_lsof(1234) is None

    def test_returns_none_on_empty_output(self, mock_run):
        mock_run.add("lsof", make_completed_process(""))
        assert get_session_id_from_lsof(1234) is None

    def test_returns_none_on_error(self, mock_run):
        mock_run.add("lsof", make_completed_process("", returncode=1))
        assert get_session_id_from_lsof(1234) is None

    def test_picks_first_valid_uuid(self, mock_run):
        lsof_output = (
            "p1234\n"
            f"n/Users/max/.claude/projects/-Users-max/{FAKE_UUID}.jsonl\n"
            f"n/Users/max/.claude/projects/-Users-max/{FAKE_UUID2}.jsonl\n"
        )
        mock_run.add("lsof", make_completed_process(lsof_output))
        assert get_session_id_from_lsof(1234) == FAKE_UUID

    def test_ignores_non_jsonl_uuid_files(self, mock_run):
        lsof_output = f"p1234\nn/path/{FAKE_UUID}.json\n"
        mock_run.add("lsof", make_completed_process(lsof_output))
        assert get_session_id_from_lsof(1234) is None
