"""commands.test: run every test project with coverage, then build the HTML report."""

import sys

import pytest

import commands.test as test_cmd
from conftest import exits_with, write_file


@pytest.fixture
def argv(monkeypatch):
    """commands.test reads sys.argv itself, so each test sets its own."""
    def set_args(*args):
        monkeypatch.setattr(sys, "argv", ["python-dotnet-test", *args])
    set_args()
    return set_args


class TestPaths:
    def test_given_no_path_when_run_then_tests_holds_the_results_and_docs_the_report(self, in_tmp, argv, fake_run):
        write_file(in_tmp / "tests" / "A.Tests" / "A.Tests.csproj")
        stale = write_file(in_tmp / "tests" / "TestResults" / "old" / "coverage.xml")

        assert test_cmd.main() == 0

        results = in_tmp / "tests" / "TestResults"
        report = in_tmp / "docs" / "coverage-report"
        assert report.is_dir()
        assert not stale.exists()  # the previous run's results are cleared
        assert fake_run.calls == [
            ["dotnet", "test", str(in_tmp / "tests" / "A.Tests" / "A.Tests.csproj"),
             "--collect:XPlat Code Coverage;Format=json,lcov,cobertura", "--results-directory", str(results)],
            ["reportgenerator", f"-reports:{results / '**' / 'coverage.cobertura.xml'}",
             f"-targetdir:{report}", "-reporttypes:Html"],
        ]

    def test_given_no_path_and_no_tests_folder_when_run_then_it_exits(self, in_tmp, argv, fake_run, capsys):
        with exits_with(1):
            test_cmd.main()
        assert "Could not find a 'tests' directory" in capsys.readouterr().out

    def test_given_a_path_when_run_then_results_and_report_go_under_it(self, in_tmp, argv, fake_run):
        base = in_tmp / "elsewhere"
        write_file(base / "X.Tests.csproj")
        argv(str(base))

        assert test_cmd.main() == 0

        assert (base / "TestResults").is_dir()
        assert (base / "coverage-report").is_dir()
        assert fake_run.calls[0][-1] == str(base.resolve() / "TestResults")

    def test_given_a_missing_path_when_run_then_it_exits(self, in_tmp, argv, fake_run):
        argv(str(in_tmp / "nope"))
        with exits_with(1):
            test_cmd.main()


class TestDiscovery:
    def test_given_projects_under_a_setup_folder_when_discovered_then_they_are_skipped(self, in_tmp):
        keep = write_file(in_tmp / "A.Tests" / "A.Tests.csproj")
        write_file(in_tmp / "setup" / "Fixture.csproj")
        write_file(in_tmp / "B" / "Setup" / "Deep" / "Other.csproj")
        assert test_cmd.collect_test_projects(in_tmp) == [keep]

    def test_given_no_test_projects_when_run_then_it_succeeds_without_running_anything(
            self, in_tmp, argv, fake_run, capsys):
        (in_tmp / "tests").mkdir()
        assert test_cmd.main() == 0
        assert fake_run.calls == []
        assert "No test projects found" in capsys.readouterr().out

    def test_given_several_projects_when_run_then_each_is_tested_before_one_report(self, in_tmp, argv, fake_run):
        write_file(in_tmp / "tests" / "A" / "A.csproj")
        write_file(in_tmp / "tests" / "B" / "B.csproj")
        assert test_cmd.main() == 0
        assert [c[0] for c in fake_run.calls] == ["dotnet", "dotnet", "reportgenerator"]


class TestFailures:
    def test_given_a_failing_test_run_when_run_then_it_exits_before_the_report(self, in_tmp, argv, fake_run, capsys):
        write_file(in_tmp / "tests" / "A" / "A.csproj")
        fake_run.results[("dotnet", "test")] = 1
        with exits_with(1):
            test_cmd.main()
        assert [c[0] for c in fake_run.calls] == ["dotnet"]
        assert "Command failed with exit code 1" in capsys.readouterr().out


class TestHelpers:
    def test_given_a_tests_folder_when_discovered_then_it_is_returned(self, in_tmp):
        (in_tmp / "tests").mkdir()
        assert test_cmd.discover_tests_base(in_tmp) == in_tmp / "tests"

    def test_given_no_tests_folder_when_discovered_then_it_exits(self, in_tmp):
        with exits_with(1):
            test_cmd.discover_tests_base(in_tmp)

    def test_given_files_and_folders_when_a_directory_is_cleaned_then_it_is_emptied_but_kept(self, in_tmp):
        write_file(in_tmp / "out" / "a.txt")
        write_file(in_tmp / "out" / "sub" / "b.txt")
        test_cmd.clean_dir(in_tmp / "out")
        assert (in_tmp / "out").is_dir()
        assert list((in_tmp / "out").iterdir()) == []

    def test_given_a_missing_directory_when_cleaned_then_nothing_happens(self, in_tmp):
        test_cmd.clean_dir(in_tmp / "missing")
        assert not (in_tmp / "missing").exists()
