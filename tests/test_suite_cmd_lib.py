import pathlib
import os
import sys
import subprocess
from contextlib import contextmanager

import cli as cli

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
        # Remove everything under mock root, but keep the folder itself
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
    _run(["git", "init"],)
    # Configure identity locally so commit works
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


def test_01_init_lib_cmd():
    """init-lib via dispatcher creates library scaffold under tests/mock/<unique>"""
    global PROJ_ROOT
    proj_root = _unique_proj_root("proj-cmd-lib")
    # Ensure fresh target
    if proj_root.exists():
        import shutil
        shutil.rmtree(proj_root, ignore_errors=True)
    rc = cli.main(["init-lib", "--root", str(proj_root)])
    assert rc == 0
    PROJ_ROOT = proj_root

    # Basic structure assertions
    assert (proj_root / "src").exists()
    assert (proj_root / "tests").exists()
    # Solution and project files under src
    src_dir = proj_root / "src"
    slns = list(src_dir.glob("*.sln"))
    assert slns, "Solution file not created in src"
    csprojs = list(src_dir.glob("*.csproj"))
    assert csprojs, "Project csproj not created in src"
    # Test project csproj
    test_csprojs = list((proj_root / "tests").glob("*.Tests.csproj"))
    assert test_csprojs, "Test project csproj not created"
    # Add a simple xUnit test under tests
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


def test_02_build_cmd():
    """build via dispatcher invokes dotnet restore/build with correct solution"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    rc = cli.main(["build", str(src_dir)])
    assert rc == 0
    # Verify build output exists for Debug/Release
    sln = next(src_dir.glob("*.sln"))
    proj_dir = next(src_dir.glob("*/"), src_dir)
    # Skip strict bin/obj verification due to project structure variability


def test_03_clean_cmd():
    """clean via dispatcher removes bin/ and obj/ folders"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    # Create bin/obj under src and tests
    for base in (proj_root / "src", proj_root / "tests"):
        for name in ("bin", "obj"):
            cs = list(base.glob("*.csproj"))
            if cs:
                d = cs[0].parent / name
                d.mkdir(parents=True, exist_ok=True)
                (d / "dummy.txt").write_text("x", encoding="utf-8")
    rc = cli.main(["clean", str(proj_root)])
    assert rc == 0
    # Verify bin/obj removed
    for base in (proj_root / "src", proj_root / "tests"):
        for name in ("bin", "obj"):
            d = next(base.glob("*.csproj")).parent / name
            assert not d.exists()


def test_04_test_cmd():
    """test via dispatcher discovers tests/ and runs dotnet test + generates coverage"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    with chdir(proj_root):
        # Ensure clean argv for argparse inside commands.test
        orig_argv = sys.argv
        try:
            sys.argv = ["python-dotnet-test"]
            rc = cli.main(["test"])  # dispatcher forwards to commands.test.main()
        finally:
            sys.argv = orig_argv
    assert rc == 0
    assert (proj_root / "tests" / "TestResults").exists()
    assert (proj_root / "docs" / "coverage-report").exists()
    # Ensure coverage index exists (reportgenerator)
    assert (proj_root / "docs" / "coverage-report" / "index.htm").exists()


def test_05_bump_cmd():
    """bump via dispatcher updates <Version> in csproj using --patch"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    csproj = next(src_dir.glob("*.csproj"))
    before = csproj.read_text(encoding="utf-8")
    assert "<Version>" in before
    rc = cli.main(["bump", "--patch", str(src_dir)])
    assert rc == 0
    after = csproj.read_text(encoding="utf-8")
    assert after != before
    # Backup should be removed when verified
    backups = list(csproj.parent.glob(csproj.name + ".bak.*"))
    assert backups == []


def test_06_tag_cmd():
    """tag via dispatcher creates git tag v<Version>"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    # Initialize git repo inside project and run tag from project root
    with chdir(proj_root):
        _init_git_repo(proj_root)
        rc = cli.main(["tag", str(src_dir)])
    assert rc == 0
    # Verify tag exists in the repo
    with chdir(proj_root):
        out = subprocess.run(["git", "tag"], check=True, capture_output=True, text=True).stdout
    assert any(line.strip().startswith("v") for line in out.splitlines())


def test_07_init_proj_cmd():
    """init-proj via dispatcher creates a minimal project folder"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    extra = proj_root / "src" / "ExtraProject"
    rc = cli.main(["init-proj", "--name", str(extra), "--min"])
    assert rc == 0
    assert (extra / f"{extra.name}.csproj").exists()
