import pathlib
import os
import sys
import subprocess
from contextlib import contextmanager

import cli as cli

from conftest import write_file

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
    _run(["git", "init"])  # in cwd where called
    _run(["git", "config", "user.email", "test@example.com"])
    _run(["git", "config", "user.name", "Test User"])
    # README.md already exists from init command
    _run(["git", "add", "."])
    _run(["git", "commit", "-m", "init"])


# Suite-level setup: clean tests/mock
_clean_mock_root()


def _unique_proj_root(prefix: str) -> pathlib.Path:
    import uuid
    return MOCK_ROOT / f"{prefix}-{uuid.uuid4().hex[:8]}"


def _scaffold_min_project() -> pathlib.Path:
    proj_root = _unique_proj_root("proj-cmd-min")
    rc = cli.main([
        "init-min",
        "--root", str(proj_root),
        "--solution", "MinSuite",
        "--project", "MinLib",
        "--author", "Test User",
        "--description", "Minimal library for tests"
    ])
    assert rc == 0
    # Add test project for coverage
    tests_dir = proj_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    write_file(tests_dir / "MinSuite.Tests.csproj", (
        """
<Project Sdk=\"Microsoft.NET.Sdk\">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include=\"coverlet.collector\" Version=\"6.0.0\" />
    <PackageReference Include=\"Microsoft.NET.Test.Sdk\" Version=\"17.9.0\" />
    <PackageReference Include=\"xunit\" Version=\"2.7.0\" />
    <PackageReference Include=\"xunit.runner.visualstudio\" Version=\"2.5.7\" />
  </ItemGroup>
</Project>
""".strip() + "\n"
    ))
    tests_src = tests_dir / "Tests"
    tests_src.mkdir(parents=True, exist_ok=True)
    write_file(tests_src / "SampleTests.cs", (
        """
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
""".strip() + "\n"
    ))
    return proj_root


def test_01_init_min_cmd():
    """init-min creates minimal scaffold under tests/mock/<unique> and we add tests project"""
    global PROJ_ROOT
    proj_root = _scaffold_min_project()
    PROJ_ROOT = proj_root
    assert (proj_root / "src").exists()
    assert (proj_root / "tests").exists()
    assert (proj_root / "src" / "MinSuite.sln").exists()
    assert (proj_root / "src" / "MinLib" / "MinLib.csproj").exists()


def test_02_build_cmd():
    """build via dispatcher works on init-min scaffold"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    rc = cli.main(["build", str(src_dir)])
    assert rc == 0


def test_03_clean_cmd():
    """clean removes bin/ and obj/ in init-min scaffold"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    # Create bin/obj under src and tests
    for base in (proj_root / "src", proj_root / "tests"):
        cs = list(base.rglob("*.csproj"))
        if cs:
            for name in ("bin", "obj"):
                d = cs[0].parent / name
                d.mkdir(parents=True, exist_ok=True)
    rc = cli.main(["clean", str(proj_root)])
    assert rc == 0
    for base in (proj_root / "src", proj_root / "tests"):
        cs = list(base.rglob("*.csproj"))
        if cs:
            for name in ("bin", "obj"):
                d = cs[0].parent / name
                assert not d.exists()


def test_04_test_cmd():
    """test via dispatcher runs dotnet test on init-min scaffold"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    with chdir(proj_root):
        orig_argv = sys.argv
        try:
            sys.argv = ["python-dotnet-test"]
            rc = cli.main(["test"])  # uses default tests/ under CWD
        finally:
            sys.argv = orig_argv
    assert rc == 0
    assert (proj_root / "tests" / "TestResults").exists()
    assert (proj_root / "docs" / "coverage-report").exists()


def test_05_bump_cmd():
    """bump via dispatcher sets Version explicitly on minimal csproj"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    csproj = next((src_dir / "MinLib").glob("*.csproj"))
    before = csproj.read_text(encoding="utf-8")
    rc = cli.main(["bump", "1.0.0", str(src_dir / "MinLib")])
    assert rc == 0
    after = csproj.read_text(encoding="utf-8")
    assert "<Version>1.0.0</Version>" in after


def test_06_tag_cmd():
    """tag via dispatcher tags init-min project version"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    with chdir(proj_root):
        _init_git_repo(proj_root)
        rc = cli.main(["tag", str(src_dir)])
    assert rc == 0
    # Verify tag exists locally
    with chdir(proj_root):
        out = subprocess.run(["git", "tag"], check=True, capture_output=True, text=True).stdout
    assert any(line.strip().startswith("v") for line in out.splitlines())
