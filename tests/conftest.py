"""Shared fixtures for snapshot_restore tests."""

import pytest
from unittest.mock import patch


# Standard UUID used across tests
FAKE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FAKE_UUID2 = "11111111-2222-3333-4444-555555555555"
FAKE_UUID3 = "99999999-8888-7777-6666-555555555555"


def make_completed_process(stdout="", returncode=0):
    """Create a subprocess.CompletedProcess."""
    import subprocess
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def make_pane(window="claude", pane=0, pane_id="%0", shell_pid=1000, command="claude"):
    """Create a pane dict matching get_pane_list() output."""
    return {
        "window": window,
        "pane": pane,
        "pane_id": pane_id,
        "shell_pid": shell_pid,
        "command": command,
    }


@pytest.fixture
def mock_run():
    """Patch subprocess.run with a configurable dispatcher.

    Usage:
        def test_something(mock_run):
            mock_run.add("lsof", make_completed_process("n/path/to/file.jsonl"))
            mock_run.add("pgrep", make_completed_process("1234"))
    """
    with patch("snapshot_restore.run") as m:
        dispatcher = _Dispatcher(m)
        yield dispatcher


class _Dispatcher:
    """Route mock calls by first arg of the command list."""

    def __init__(self, mock):
        self.mock = mock
        self._routes = {}
        self._call_counts = {}
        mock.side_effect = self._dispatch

    def add(self, key, result, *, call_index=None):
        """Register a result for commands starting with `key`.

        If call_index is set, only return this result on the Nth call (0-based)
        to commands starting with `key`.
        """
        if call_index is not None:
            self._routes.setdefault(f"{key}#{call_index}", []).append(result)
        else:
            self._routes.setdefault(key, []).append(result)

    def _dispatch(self, cmd, **kwargs):
        key = cmd[0] if isinstance(cmd, list) else cmd
        count = self._call_counts.get(key, 0)
        self._call_counts[key] = count + 1

        # Try indexed route first
        indexed_key = f"{key}#{count}"
        if indexed_key in self._routes:
            results = self._routes[indexed_key]
            return results[0] if len(results) == 1 else results.pop(0)

        # Fall back to generic route
        if key in self._routes:
            results = self._routes[key]
            return results[0] if len(results) == 1 else results.pop(0)

        return make_completed_process()
