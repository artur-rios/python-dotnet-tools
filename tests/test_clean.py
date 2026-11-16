"""commands.clean: remove every bin/ and obj/ under a directory."""

import shutil

import commands.clean as clean
from conftest import exits_with, write_file


class TestTargetDirectory:
    def test_given_no_path_when_resolved_then_src_is_used(self, in_tmp):
        (in_tmp / "src").mkdir()
        assert clean.resolve_target_dir(["clean"]) == (in_tmp / "src").resolve()

    def test_given_no_path_and_no_src_when_resolved_then_it_exits(self, in_tmp, capsys):
        with exits_with(1):
            clean.resolve_target_dir(["clean"])
        assert "'src' directory was not found" in capsys.readouterr().out

    def test_given_a_dot_when_resolved_then_the_working_directory_is_used(self, in_tmp):
        assert clean.resolve_target_dir(["clean", "./"]) == in_tmp.resolve()

    def test_given_a_quoted_path_when_resolved_then_the_quotes_are_stripped(self, in_tmp):
        (in_tmp / "proj").mkdir()
        assert clean.resolve_target_dir(["clean", f'"{in_tmp / "proj"}"']) == (in_tmp / "proj").resolve()

    def test_given_a_file_or_a_missing_path_when_resolved_then_it_exits(self, in_tmp):
        write_file(in_tmp / "a.txt", "x")
        for raw in (str(in_tmp / "a.txt"), str(in_tmp / "missing")):
            with exits_with(1):
                clean.resolve_target_dir(["clean", raw])


class TestClean:
    def test_given_nested_build_output_when_cleaned_then_only_bin_and_obj_are_removed(self, in_tmp, capsys):
        for project in ("src/A", "src/B", "tests/C"):
            write_file(in_tmp / project / "bin" / "Debug" / "a.dll", "x")
            write_file(in_tmp / project / "obj" / "project.assets.json", "{}")
            write_file(in_tmp / project / "Program.cs", "class P {}")

        assert clean.main(["clean", str(in_tmp)]) == 0

        assert not list(in_tmp.rglob("bin"))
        assert not list(in_tmp.rglob("obj"))
        assert len(list(in_tmp.rglob("Program.cs"))) == 3
        assert "[OK] Cleaned 6 folders" in capsys.readouterr().out

    def test_given_nothing_to_clean_when_cleaned_then_it_succeeds_with_zero(self, in_tmp, capsys):
        assert clean.clean(in_tmp) == 0
        assert "[OK] Cleaned 0 folders" in capsys.readouterr().out

    def test_given_a_target_that_vanished_when_cleaned_then_it_exits(self, in_tmp):
        with exits_with(1):
            clean.clean(in_tmp / "gone")

    def test_given_a_folder_that_cannot_be_removed_when_cleaned_then_it_warns_and_carries_on(
            self, in_tmp, monkeypatch, capsys):
        (in_tmp / "bin").mkdir()

        def broken(path, ignore_errors=False):
            raise PermissionError("in use")

        monkeypatch.setattr(shutil, "rmtree", broken)
        clean.remove_dir_tree(in_tmp / "bin")
        assert "[WARN] Failed to remove" in capsys.readouterr().out

    def test_given_a_file_when_removed_as_a_tree_then_it_is_left_alone(self, in_tmp):
        file = write_file(in_tmp / "bin", "not a folder")
        clean.remove_dir_tree(file)
        assert file.exists()
