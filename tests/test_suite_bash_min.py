import pathlib
import os
import sys
import subprocess
from contextlib import contextmanager

import commands.build as build_cmd
import commands.clean as clean_cmd
import commands.test as test_cmd
import commands.bump as bump_cmd
import commands.tag as tag_cmd
import commands.init_proj as init_proj
import commands.init_min as init_min

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
    _run(["git", "init"])  # in cwd
    _run(["git", "config", "user.email", "test@example.com"])
    _run(["git", "config", "user.name", "Test User"])
    # ensure at least one file to commit
    write_file(repo_root / "README.md", "Temporary repo for tests\n")
    _run(["git", "add", "."])
    _run(["git", "commit", "-m", "init"])


# Suite-level setup
_clean_mock_root()


def _unique_proj_root(prefix: str) -> pathlib.Path:
    import uuid
    return MOCK_ROOT / f"{prefix}-{uuid.uuid4().hex[:8]}"


def _scaffold_min_project() -> pathlib.Path:
    proj_root = _unique_proj_root("proj-bash-min")
    rc = init_min.main([
        "init-min",
        "--root", str(proj_root),
        "--solution", "MinSuite",
        "--project", "MinLib",
        "--author", "Test User",
        "--description", "Minimal library for tests"
    ])
    assert rc == 0

    # Add test project with coverlet + xUnit so coverage works
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


def test_01_init_min_bash():
    """init-min creates minimal scaffold under tests/mock/<unique> and we add tests project"""
    global PROJ_ROOT
    proj_root = _scaffold_min_project()
    PROJ_ROOT = proj_root
    assert (proj_root / "src").exists()
    assert (proj_root / "docs").exists()
    assert (proj_root / "tests").exists()
    # Solution and project
    assert (proj_root / "src" / "MinSuite.sln").exists()
    assert (proj_root / "src" / "MinLib" / "MinLib.csproj").exists()


def test_02_build_bash():
    """build entrypoint works on init-min scaffold"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    rc = build_cmd.main(["python-dotnet-build", str(src_dir)])
    assert rc == 0


def test_03_clean_bash():
    """clean entrypoint removes bin/ and obj/"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    for base in (proj_root / "src", proj_root / "tests"):
        # create under the directory containing a csproj if any exist (search recursively)
        cs = list(base.rglob("*.csproj"))
        if cs:
            for name in ("bin", "obj"):
                d = cs[0].parent / name
                d.mkdir(parents=True, exist_ok=True)
    rc = clean_cmd.main(["python-dotnet-clean", str(proj_root)])
    assert rc == 0
    for base in (proj_root / "src", proj_root / "tests"):
        cs = list(base.rglob("*.csproj"))
        if cs:
            for name in ("bin", "obj"):
                d = cs[0].parent / name
                assert not d.exists()


def test_04_test_bash():
    """test entrypoint generates results and coverage"""
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


def test_05_bump_bash():
    """bump entrypoint sets Version explicitly on minimal csproj"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    src_dir = proj_root / "src"
    csproj = next((src_dir / "MinLib").glob("*.csproj"))
    rc = bump_cmd.main(["python-dotnet-bump", "1.0.0", str(src_dir / "MinLib")])
    assert rc == 0
    after = csproj.read_text(encoding="utf-8")
    assert "<Version>1.0.0</Version>" in after


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
    """init-proj entrypoint creates minimal project folder in init-min suite"""
    assert PROJ_ROOT is not None, "Project root not initialized"
    proj_root = PROJ_ROOT
    extra = proj_root / "src" / "ExtraProjectManual"
    rc = init_proj.main(["init-proj", "--name", str(extra), "--min"])
    assert rc == 0
    assert (extra / f"{extra.name}.csproj").exists()
