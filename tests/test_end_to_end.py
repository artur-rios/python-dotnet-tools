"""The commands against a real scaffold, with the real dotnet, reportgenerator and git.

One library scaffold (init-lib) and one minimal scaffold (init-min) are built
per module and shared by its tests; each test sets up what it checks itself,
so they pass in any order. The library is driven through the
`python-dotnet-tools` dispatcher, the minimal one through each console
script's own entry point, so both ways in run for real once. Marked `e2e`:
`pytest -m "not e2e"` runs only the unit tests.
"""

import shutil
import subprocess
import sys

import pytest

import cli
import commands.build as build_cmd
import commands.bump as bump_cmd
import commands.clean as clean_cmd
import commands.init_lib as init_lib
import commands.init_min as init_min
import commands.init_proj as init_proj
import commands.tag as tag_cmd
import commands.test as test_cmd
from conftest import write_file

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="needs the .NET SDK"),
]

SAMPLE_TEST = """using Xunit;

namespace Tests;

public class SampleTests
{
    [Fact]
    public void Addition_Works()
    {
        Assert.Equal(4, 2 + 2);
    }
}
"""

MIN_TESTS_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="coverlet.collector" Version="6.0.0" />
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.9.0" />
    <PackageReference Include="xunit" Version="2.7.0" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.7" />
  </ItemGroup>
</Project>
"""


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _commit_everything(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")


def _run_test_command(root, monkeypatch, run):
    """commands.test parses sys.argv itself, so it gets a clean one and the scaffold as cwd."""
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["python-dotnet-test"])
    return run()


def _bin_obj_dirs(root):
    return [p for p in root.rglob("*") if p.is_dir() and p.name in {"bin", "obj"}]


@pytest.fixture(scope="module")
def lib_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e") / "lib"
    assert cli.main(["init-lib", "--root", str(root)]) == 0
    write_file(root / "tests" / "Tests" / "SampleTests.cs", SAMPLE_TEST)
    return root


@pytest.fixture(scope="module")
def min_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e") / "min"
    assert init_min.main(["init-min", "--root", str(root), "--solution", "MinSuite", "--project", "MinLib",
                          "--author", "Test User", "--description", "Minimal library for tests"]) == 0
    write_file(root / "tests" / "MinSuite.Tests.csproj", MIN_TESTS_CSPROJ)
    write_file(root / "tests" / "Tests" / "SampleTests.cs", SAMPLE_TEST)
    return root


class TestLibraryThroughTheDispatcher:
    def test_given_a_library_scaffold_when_built_then_the_solution_restores_and_builds(self, lib_root):
        assert cli.main(["build", str(lib_root / "src")]) == 0
        assert (lib_root / "src" / "bin" / "Release").is_dir()

    def test_given_build_output_when_cleaned_then_every_bin_and_obj_is_gone(self, lib_root):
        for base in (lib_root / "src", lib_root / "tests"):
            write_file(base / "bin" / "Debug" / "x.dll", "x")
            write_file(base / "obj" / "x.json", "{}")
        assert cli.main(["clean", str(lib_root)]) == 0
        assert _bin_obj_dirs(lib_root) == []

    def test_given_a_test_project_when_tested_then_results_and_an_html_coverage_report_are_written(
            self, lib_root, monkeypatch):
        assert _run_test_command(lib_root, monkeypatch, lambda: cli.main(["test"])) == 0
        assert list((lib_root / "tests" / "TestResults").rglob("coverage.cobertura.xml"))
        assert (lib_root / "docs" / "coverage-report" / "index.htm").is_file()

    def test_given_the_scaffold_version_when_bumped_with_patch_then_the_csproj_moves_on(self, lib_root):
        csproj = next((lib_root / "src").glob("*.csproj"))
        before = bump_cmd.read_current_version(csproj)
        major, minor, patch = map(int, before.split("."))
        assert cli.main(["bump", "--patch", str(lib_root / "src")]) == 0
        assert bump_cmd.read_current_version(csproj) == f"{major}.{minor}.{patch + 1}"
        assert list(csproj.parent.glob("*.bak.*")) == []

    def test_given_a_committed_scaffold_when_tagged_then_git_has_the_version_tag(self, lib_root, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        shutil.copytree(lib_root, repo, ignore=shutil.ignore_patterns("bin", "obj", "TestResults", "docs"))
        _commit_everything(repo)
        version = bump_cmd.read_current_version(next((repo / "src").glob("*.csproj")))
        monkeypatch.chdir(repo)
        assert cli.main(["tag", str(repo / "src")]) == 0
        assert _git(repo, "tag").split() == [f"v{version}"]

    def test_given_a_scaffold_when_a_project_is_added_then_it_gets_its_own_folder(self, lib_root):
        extra = lib_root / "extra" / "ExtraProject"
        assert cli.main(["init-proj", "--name", str(extra), "--min"]) == 0
        assert (extra / "ExtraProject.csproj").is_file()


class TestMinimalThroughTheEntryPoints:
    def test_given_a_minimal_scaffold_when_built_then_the_solution_restores_and_builds(self, min_root):
        assert build_cmd.main(["python-dotnet-build", str(min_root / "src")]) == 0
        assert (min_root / "src" / "MinLib" / "bin" / "Release").is_dir()

    def test_given_build_output_when_cleaned_then_every_bin_and_obj_is_gone(self, min_root):
        write_file(min_root / "src" / "MinLib" / "bin" / "x.dll", "x")
        write_file(min_root / "src" / "MinLib" / "obj" / "x.json", "{}")
        assert clean_cmd.main(["python-dotnet-clean", str(min_root)]) == 0
        assert _bin_obj_dirs(min_root) == []

    def test_given_a_test_project_when_tested_then_results_and_an_html_coverage_report_are_written(
            self, min_root, monkeypatch):
        assert _run_test_command(min_root, monkeypatch, test_cmd.main) == 0
        assert list((min_root / "tests" / "TestResults").rglob("coverage.cobertura.xml"))
        assert (min_root / "docs" / "coverage-report" / "index.htm").is_file()

    def test_given_a_csproj_without_a_version_when_bumped_explicitly_then_one_is_inserted(self, min_root):
        project = min_root / "src" / "MinLib"
        assert bump_cmd.main(["python-dotnet-bump", "1.0.0", str(project)]) == 0
        assert "<Version>1.0.0</Version>" in (project / "MinLib.csproj").read_text(encoding="utf-8")

    def test_given_a_committed_scaffold_when_tagged_then_git_has_the_version_tag(self, min_root, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        shutil.copytree(min_root, repo, ignore=shutil.ignore_patterns("bin", "obj", "TestResults", "docs"))
        write_file(repo / "src" / "MinLib" / "MinLib.csproj",
                   "<Project><PropertyGroup><Version>2.3.4</Version></PropertyGroup></Project>\n")
        _commit_everything(repo)
        monkeypatch.chdir(repo)
        assert tag_cmd.main(["python-dotnet-tag", str(repo / "src" / "MinLib")]) == 0
        assert _git(repo, "tag").split() == ["v2.3.4"]

    def test_given_a_scaffold_when_a_project_is_added_then_it_gets_its_own_folder(self, min_root):
        extra = min_root / "extra" / "ExtraProjectManual"
        assert init_proj.main(["init-proj", "--name", str(extra), "--min"]) == 0
        assert (extra / "ExtraProjectManual.csproj").is_file()

    def test_given_the_library_entry_point_when_scaffolding_then_it_works_on_its_own_too(self, tmp_path):
        root = tmp_path / "direct"
        assert init_lib.main(["init-lib", "--root", str(root)]) == 0
        assert next((root / "src").glob("*.sln"))
