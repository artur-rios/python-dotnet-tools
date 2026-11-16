"""Fixtures shared by the unit and end-to-end tests."""

import pathlib
import subprocess

import pytest


def write_file(path: pathlib.Path, content: str = "") -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class FakeRun:
    """Stands in for subprocess.run: records every command, runs none.

    `results` maps the first words of a command (a tuple such as ("git", "tag"))
    to the return code it should get; anything else succeeds.
    """

    def __init__(self):
        self.calls: list[list[str]] = []
        self.results: dict[tuple[str, ...], int] = {}
        self.error: BaseException | None = None

    def __call__(self, cmd, check=False, **kwargs):
        cmd = [str(part) for part in cmd]
        self.calls.append(cmd)
        if self.error is not None:
            raise self.error
        code = next((rc for prefix, rc in self.results.items() if tuple(cmd[:len(prefix)]) == prefix), 0)
        if check and code != 0:
            raise subprocess.CalledProcessError(returncode=code, cmd=cmd)
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="")


@pytest.fixture
def fake_run(monkeypatch):
    """Replace subprocess.run everywhere for the test, restoring it afterwards."""
    fake = FakeRun()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    """Run the test with tmp_path as the working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def exits_with(code: int):
    """The commands report a user error by calling sys.exit(1) / raising SystemExit(1)."""
    return pytest.raises(SystemExit, match=f"^{code}$")
