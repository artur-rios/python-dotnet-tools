"""commands.build: restore and build a solution, Debug and Release."""

import pytest

import commands.build as build
from conftest import exits_with, write_file


@pytest.fixture
def src(in_tmp):
    write_file(in_tmp / "src" / "App.sln")
    return in_tmp / "src"


class TestTargetDirectory:
    def test_given_no_path_when_resolved_then_src_under_the_working_directory_is_used(self, src):
        assert build.resolve_target_dir(["build"]) == src.resolve()

    def test_given_no_path_and_no_src_when_resolved_then_it_exits(self, in_tmp, capsys):
        with exits_with(1):
            build.resolve_target_dir(["build"])
        assert "No 'src' folder found" in capsys.readouterr().out

    def test_given_a_path_when_resolved_then_it_is_used(self, src):
        assert build.resolve_target_dir(["build", str(src)]) == src.resolve()

    def test_given_a_missing_path_when_resolved_then_it_exits(self, in_tmp):
        with exits_with(1):
            build.resolve_target_dir(["build", str(in_tmp / "nope")])

    def test_given_flag_values_and_a_stray_build_token_when_resolved_then_they_are_not_taken_for_the_path(
            self, src, in_tmp):
        other = in_tmp / "other"
        other.mkdir()
        argv = ["x", "build", "--solution", "App.sln", "--configuration", "Debug", "--no-restore", str(other)]
        assert build.resolve_target_dir(argv) == other.resolve()


class TestFlags:
    def test_given_no_flags_when_parsed_then_everything_is_default(self):
        assert build.parse_flags(["build"]) == {"no_restore": False, "solution": None, "configuration": None}

    @pytest.mark.parametrize("flag", ["--no-restore", "--noRestore"])
    def test_given_either_no_restore_spelling_when_parsed_then_restore_is_skipped(self, flag):
        assert build.parse_flags(["build", flag])["no_restore"] is True

    def test_given_a_solution_and_a_configuration_when_parsed_then_both_are_read(self):
        flags = build.parse_flags(["build", "--solution", "A.sln", "--configuration", "Release"])
        assert flags["solution"] == "A.sln"
        assert flags["configuration"] == "Release"

    @pytest.mark.parametrize("argv", [
        ["build", "--solution"], ["build", "--solution", "--no-restore"],
        ["build", "--configuration"], ["build", "--configuration", "Staging"],
    ])
    def test_given_a_flag_without_a_valid_value_when_parsed_then_it_exits(self, argv):
        with exits_with(1):
            build.parse_flags(argv)


class TestPickSolution:
    def test_given_one_solution_when_picked_then_it_is_used(self, src):
        assert build.pick_solution(src, None).name == "App.sln"

    def test_given_a_named_solution_when_picked_then_that_one_is_used(self, src):
        write_file(src / "Other.sln")
        assert build.pick_solution(src, "Other.sln").name == "Other.sln"

    def test_given_a_named_solution_that_is_missing_when_picked_then_it_exits(self, src):
        with exits_with(1):
            build.pick_solution(src, "Missing.sln")

    def test_given_no_solution_when_picked_then_it_exits(self, in_tmp):
        with exits_with(1):
            build.pick_solution(in_tmp, None)

    def test_given_several_solutions_when_picked_without_a_name_then_it_exits_naming_them(self, src, capsys):
        write_file(src / "Other.sln")
        with exits_with(1):
            build.pick_solution(src, None)
        assert "App.sln" in capsys.readouterr().out


class TestBuild:
    def test_given_defaults_when_built_then_it_restores_and_builds_debug_and_release(self, src, fake_run):
        assert build.main(["build"]) == 0
        sln = str(src.resolve() / "App.sln")
        assert fake_run.calls == [
            ["dotnet", "restore", sln],
            ["dotnet", "build", sln, "-c", "Debug"],
            ["dotnet", "build", sln, "-c", "Release"],
        ]

    def test_given_no_restore_and_a_configuration_when_built_then_only_that_build_runs_without_restore(
            self, src, fake_run):
        assert build.main(["build", "--no-restore", "--configuration", "Release"]) == 0
        assert fake_run.calls == [["dotnet", "build", str(src.resolve() / "App.sln"), "-c", "Release", "--no-restore"]]

    def test_given_a_failing_dotnet_when_built_then_it_exits_with_the_failure(self, src, fake_run, capsys):
        fake_run.results[("dotnet", "build")] = 3
        with exits_with(1):
            build.main(["build"])
        assert "Command failed with exit code 3" in capsys.readouterr().out

    def test_given_a_target_that_vanished_when_built_then_it_exits(self, in_tmp, fake_run):
        with exits_with(1):
            build.build(in_tmp / "gone", False, None, None)
        assert fake_run.calls == []
