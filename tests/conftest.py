import pathlib
import subprocess
import contextlib
import shutil
import pytest
from typing import Callable, Optional, Tuple, Dict, Any

class CallLog:
    def __init__(self):
        self.calls = []

    def record(self, cmd):
        self.calls.append(list(cmd))

@contextlib.contextmanager
def mock_subprocess_run(call_log: CallLog, returncode: int = 0):
    original_run = subprocess.run
    def _fake_run(cmd, check=False, **kwargs):
        call_log.record(cmd)
        class Result:
            def __init__(self, returncode):
                self.returncode = returncode
                # Provide stdout/stderr placeholders for callers using capture_output
                self.stdout = ""
                self.stderr = ""
        if check and returncode != 0:
            raise subprocess.CalledProcessError(returncode=returncode, cmd=cmd)
        return Result(returncode)
    subprocess.run = _fake_run
    try:
        yield
    finally:
        subprocess.run = original_run


def write_file(path: pathlib.Path, content: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@contextlib.contextmanager
def mock_subprocess_run_dynamic(
    call_log: CallLog,
    behavior: Optional[Callable[[list[str], Dict[str, Any]], Tuple[int, str, str]]] = None,
    default_returncode: int = 0,
    default_stdout: str = "",
    default_stderr: str = "",
):
    """
    Mock subprocess.run with dynamic behavior per command.

    behavior: function receiving (cmd, kwargs) and returning (returncode, stdout, stderr).
    If behavior is None, uses defaults for all commands.
    Records all calls into call_log.
    """
    original_run = subprocess.run

    def _fake_run(cmd, check=False, **kwargs):
        call_log.record(cmd)
        rc, out, err = default_returncode, default_stdout, default_stderr
        if behavior is not None:
            try:
                rc, out, err = behavior(list(cmd), kwargs)
            except Exception:
                # Fallback to defaults if behavior fails
                rc, out, err = default_returncode, default_stdout, default_stderr
        class Result:
            def __init__(self, returncode: int, stdout: str, stderr: str):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
        if check and rc != 0:
            raise subprocess.CalledProcessError(returncode=rc, cmd=cmd)
        return Result(rc, out, err)

    subprocess.run = _fake_run
    try:
        yield
    finally:
        subprocess.run = original_run


# Pretty test summary at the end of the run
_TEST_DESCRIPTIONS: Dict[str, str] = {}


@pytest.fixture(scope="session", autouse=True)
def cleanup_mock_folder():
    """Clean tests/mock folder completely before running tests."""
    mock_dir = pathlib.Path(__file__).parent / "mock"
    
    # Remove directory and all contents if it exists
    if mock_dir.exists():
        def handle_remove_error(func, path, exc):
            """Error handler for rmtree to force removal of read-only files."""
            import os
            import stat
            if not os.access(path, os.W_OK):
                os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                func(path)
            else:
                raise
        
        try:
            shutil.rmtree(mock_dir, onerror=handle_remove_error)
        except Exception:
            pass  # Silently ignore any remaining issues
    
    yield


def pytest_collection_modifyitems(session, config, items):
    for item in items:
        desc = None
        try:
            obj = getattr(item, 'obj', None)
            if obj and getattr(obj, '__doc__', None):
                # First line of docstring
                desc = (obj.__doc__ or '').strip().splitlines()[0]
        except Exception:
            pass
        if not desc:
            # Fall back to function name
            desc = item.name
        _TEST_DESCRIPTIONS[item.nodeid] = desc


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    # Collect outcomes
    order = [('passed', 'PASSED'), ('failed', 'FAILED'), ('error', 'ERROR'), ('skipped', 'SKIPPED')]
    results = []
    for key, label in order:
        for rep in terminalreporter.getreports(key):
            nodeid = rep.nodeid
            desc = _TEST_DESCRIPTIONS.get(nodeid, nodeid)
            results.append((desc, label))

    # Print per-test summary
    if results:
        terminalreporter.write_sep("=", "Test Summary")
        for desc, label in results:
            terminalreporter.write_line(f"- {desc}: {label}")
        total = len(results)
        passed = sum(1 for _, l in results if l == 'PASSED')
        terminalreporter.write_sep("-", f"{passed} of {total} tests passed")
