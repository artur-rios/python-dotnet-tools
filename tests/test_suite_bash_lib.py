import pathlib
import os
import sys
import subprocess
from contextlib import contextmanager

import commands.init_lib as init_lib
import commands.build as build_cmd
import commands.clean as clean_cmd
import commands.test as test_cmd
import commands.bump as bump_cmd
import commands.tag as tag_cmd
import commands.init_proj as init_proj

from conftest import CallLog

MOCK_ROOT = pathlib.Path(__file__).parent / "mock"
PROJ_ROOT: pathlib.Path | None = None


@contextmanager
def chdir(path: pathlib.Path):
    prev = pathlib.Path.cwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(prev))


def _clean_mock_root():
    if MOCK_ROOT.exists():
        for child in MOCK_ROOT.iterdir():
            if child.is_dir():
                import shutil
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except Exception:
                    pass
    else:
        MOCK_ROOT.mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str]):
    subprocess.run(cmd, check=True)


def _init_git_repo(repo_root: pathlib.Path):
    _run(["git", "init"])  # in cwd
    _run(["git", "config", "user.email", "test@example.com"])
    _run(["git", "config", "user.name", "Test User"])
    # README.md already exists from init command
    _run(["git", "add", "."])
    _run(["git", "commit", "-m", "init"])


# Note: avoid global cleanup to prevent cross-suite interference


def _unique_proj_root(prefix: str) -> pathlib.Path:
    import uuid
    name = f"{prefix}-{uuid.uuid4().hex[:8]}"
    return MOCK_ROOT / name


def test_01_init_lib_bash():
    """init-lib entrypoint creates scaffold under tests/mock/<unique>"""
    global PROJ_ROOT
    proj_root = _unique_proj_root("proj-bash-lib")
    # Ensure fresh target
    if proj_root.exists():
        import shutil
        shutil.rmtree(proj_root, ignore_errors=True)
    rc = init_lib.main(["init-lib", "--root", str(proj_root)])
    assert rc == 0
    PROJ_ROOT = proj_root
    assert (proj_root / "src").exists()
    assert (proj_root / "tests").exists()
    # Add a simple test file under tests
    tests_src = proj_root / "tests" / "Tests"
    tests_src.mkdir(parents=True, exist_ok=True)
    from conftest import write_file as _wf
    _wf(tests_src / "SampleTests.cs", """
using Xunit;

namespace Tests;

public class SampleTests
{
    [Fact]
    public void Addition_Works()
    {
        Assert.Equal(4, 2+2);
    }
}
""".strip() + "\n")


def test_02_build_bash():
    """build entrypoint restores/builds solution (mocked)"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    rc = build_cmd.main(["python-dotnet-build", str(src_dir)])
    assert rc == 0


def test_03_clean_bash():
    """clean entrypoint removes bin/ and obj/"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    # Create bin/obj under src and tests
    for base in (proj_root / "src", proj_root / "tests"):
        for name in ("bin", "obj"):
            # create under the directory containing a csproj if any exist
            cs = list(base.glob("*.csproj"))
            if cs:
                d = cs[0].parent / name
                d.mkdir(parents=True, exist_ok=True)
    rc = clean_cmd.main(["python-dotnet-clean", str(proj_root)])
    assert rc == 0
    for base in (proj_root / "src", proj_root / "tests"):
        for name in ("bin", "obj"):
            d = next(base.glob("*.csproj")).parent / name
            assert not d.exists()


def test_04_test_bash():
    """test entrypoint runs dotnet test and reportgenerator"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    with chdir(proj_root):
        orig_argv = sys.argv
        try:
            sys.argv = ["python-dotnet-test"]
            rc = test_cmd.main()
        finally:
            sys.argv = orig_argv
    assert rc == 0
    assert (proj_root / "tests" / "TestResults").exists()
    assert (proj_root / "docs" / "coverage-report").exists()
    assert (proj_root / "docs" / "coverage-report" / "index.htm").exists()


def test_05_bump_bash():
    """bump entrypoint updates Version using --patch"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    csproj = next(src_dir.glob("*.csproj"))
    before = csproj.read_text(encoding="utf-8")
    rc = bump_cmd.main(["python-dotnet-bump", "--patch", str(src_dir)])
    assert rc == 0
    after = csproj.read_text(encoding="utf-8")
    assert after != before


def test_06_tag_bash():
    """tag entrypoint creates git tag v<Version>"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    with chdir(proj_root):
        _init_git_repo(proj_root)
        rc = tag_cmd.main(["python-dotnet-tag", str(src_dir)])
    assert rc == 0
    with chdir(proj_root):
        out = subprocess.run(["git", "tag"], check=True, capture_output=True, text=True).stdout
    assert any(line.strip().startswith("v") for line in out.splitlines())


def test_07_init_proj_bash():
    """init-proj entrypoint creates a minimal project folder"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    extra = proj_root / "src" / "ExtraProjectBash"
    rc = init_proj.main(["init-proj", "--name", str(extra), "--min"])
    assert rc == 0
    assert (extra / f"{extra.name}.csproj").exists()
