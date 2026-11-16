"""commands.bump: set or increment the <Version> of a .csproj."""

import datetime

import pytest

import commands.bump as bump
from conftest import exits_with, write_file

WITH_VERSION = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <PackageId>Lib</PackageId>
    <Version>1.2.3</Version>
  </PropertyGroup>
</Project>
"""


@pytest.fixture
def csproj(in_tmp):
    return write_file(in_tmp / "src" / "Lib.csproj", WITH_VERSION)


class TestResolveCsproj:
    def test_given_no_path_when_resolved_then_the_single_csproj_in_src_is_used(self, csproj):
        assert bump.resolve_csproj(["bump", "--patch"]) == csproj.resolve()

    def test_given_no_src_when_resolved_then_it_exits(self, in_tmp):
        with exits_with(1):
            bump.resolve_csproj(["bump", "--patch"])

    @pytest.mark.parametrize("names", [[], ["A.csproj", "B.csproj"]])
    def test_given_zero_or_several_csproj_in_src_when_resolved_then_it_exits(self, in_tmp, names):
        (in_tmp / "src").mkdir()
        for name in names:
            write_file(in_tmp / "src" / name)
        with exits_with(1):
            bump.resolve_csproj(["bump", "--patch"])

    def test_given_a_csproj_file_when_resolved_then_it_is_used(self, csproj):
        assert bump.resolve_csproj(["bump", "1.0.0", str(csproj)]) == csproj.resolve()

    def test_given_a_file_that_is_not_a_csproj_when_resolved_then_it_exits(self, in_tmp):
        other = write_file(in_tmp / "Lib.fsproj")
        with exits_with(1):
            bump.resolve_csproj(["bump", "1.0.0", str(other)])

    def test_given_a_missing_path_when_resolved_then_it_exits(self, in_tmp):
        with exits_with(1):
            bump.resolve_csproj(["bump", "1.0.0", str(in_tmp / "nope")])

    def test_given_a_directory_when_resolved_then_only_its_immediate_csproj_counts(self, in_tmp):
        target = write_file(in_tmp / "proj" / "Lib.csproj")
        write_file(in_tmp / "proj" / "nested" / "Other.csproj")
        assert bump.resolve_csproj(["bump", "1.0.0", str(in_tmp / "proj")]) == target.resolve()

    @pytest.mark.parametrize("names", [[], ["A.csproj", "B.csproj"]])
    def test_given_a_directory_with_zero_or_several_csproj_when_resolved_then_it_exits(self, in_tmp, names):
        (in_tmp / "proj").mkdir()
        for name in names:
            write_file(in_tmp / "proj" / name)
        with exits_with(1):
            bump.resolve_csproj(["bump", "1.0.0", str(in_tmp / "proj")])


class TestTargetVersion:
    @pytest.mark.parametrize("arg, expected", [
        ("--major", "2.0.0"), ("--minor", "1.3.0"), ("--patch", "1.2.4"), ("5.6.7", "5.6.7"),
    ])
    def test_given_a_bump_kind_when_computed_then_the_right_part_moves(self, arg, expected):
        assert bump.compute_target(arg, "1.2.3") == expected

    @pytest.mark.parametrize("arg", ["--major", "--minor", "--patch"])
    def test_given_no_current_version_when_incrementing_then_it_exits(self, arg):
        with exits_with(1):
            bump.compute_target(arg, None)

    def test_given_an_explicit_version_and_no_current_one_when_computed_then_it_is_used(self):
        assert bump.compute_target("0.1.0", None) == "0.1.0"

    @pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0-beta", "a.b.c", ""])
    def test_given_a_version_that_is_not_major_minor_patch_when_validated_then_it_exits(self, version):
        with exits_with(1):
            bump.validate_version(version)


class TestRewrite:
    def test_given_an_existing_version_when_replaced_then_only_the_first_occurrence_changes(self):
        raw = "<Version>1.0.0</Version>\n<Version>1.0.0</Version>"
        assert bump.insert_or_replace_version(raw, "11.0.0") == "<Version>11.0.0</Version>\n<Version>1.0.0</Version>"

    def test_given_no_version_but_a_package_id_when_inserted_then_it_follows_the_package_id(self):
        raw = "<PropertyGroup>\n    <PackageId>Lib</PackageId>\n    <Nullable>enable</Nullable>\n</PropertyGroup>"
        updated = bump.insert_or_replace_version(raw, "1.0.0")
        assert updated.index("<PackageId>") < updated.index("<Version>1.0.0</Version>") < updated.index("<Nullable>")

    def test_given_no_version_and_no_package_id_when_inserted_then_it_opens_the_first_property_group(self):
        raw = "<Project>\n  <PropertyGroup>\n    <Nullable>enable</Nullable>\n  </PropertyGroup>\n</Project>"
        updated = bump.insert_or_replace_version(raw, "1.0.0")
        assert updated.index("<PropertyGroup>") < updated.index("<Version>1.0.0</Version>") < updated.index("<Nullable>")

    def test_given_no_property_group_when_inserted_then_it_is_appended(self):
        assert bump.insert_or_replace_version("<Project />", "1.0.0").endswith("<Version>1.0.0</Version>\n")

    def test_given_a_csproj_when_read_then_the_numeric_version_is_found(self, csproj):
        assert bump.read_current_version(csproj) == "1.2.3"


class TestMain:
    def test_given_no_arguments_when_run_then_the_usage_is_printed(self, capsys):
        assert bump.main(["bump"]) == 1
        assert "Usage:" in capsys.readouterr().out

    def test_given_patch_when_run_then_the_csproj_is_bumped_and_the_backup_removed(self, csproj):
        assert bump.main(["bump", "--patch"]) == 0
        assert "<Version>1.2.4</Version>" in csproj.read_text(encoding="utf-8")
        assert list(csproj.parent.glob("*.bak.*")) == []

    def test_given_an_explicit_version_on_a_csproj_without_one_when_run_then_it_is_inserted(self, in_tmp):
        target = write_file(in_tmp / "src" / "Min.csproj",
                            "<Project>\n  <PropertyGroup>\n    <Nullable>enable</Nullable>\n  </PropertyGroup>\n</Project>")
        assert bump.main(["bump", "1.0.0", str(target)]) == 0
        assert "<Version>1.0.0</Version>" in target.read_text(encoding="utf-8")

    def test_given_an_invalid_version_when_run_then_the_csproj_is_untouched(self, csproj):
        with exits_with(1):
            bump.main(["bump", "1.0"])
        assert csproj.read_text(encoding="utf-8") == WITH_VERSION
        assert list(csproj.parent.glob("*.bak.*")) == []

    def test_given_a_change_that_cannot_be_verified_when_run_then_the_backup_is_kept(self, csproj, monkeypatch):
        monkeypatch.setattr(bump, "verify", lambda path, version: False)
        assert bump.main(["bump", "--minor"]) == 0
        assert len(list(csproj.parent.glob("Lib.csproj.bak.*"))) == 1

    def test_given_a_backup_that_cannot_be_deleted_when_run_then_it_warns(self, csproj, monkeypatch, capsys):
        def locked(self, missing_ok=False):
            raise PermissionError("locked")

        monkeypatch.setattr(bump.pathlib.Path, "unlink", locked)
        assert bump.main(["bump", "--patch"]) == 0
        assert "[WARN] Backup not deleted" in capsys.readouterr().out

    def test_given_a_fixed_clock_when_a_backup_is_made_then_its_name_carries_the_timestamp(self, csproj, monkeypatch):
        class Fixed(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 1, 2, 3, 4, 5)

        monkeypatch.setattr(bump.datetime, "datetime", Fixed)
        backup = bump.create_backup(csproj)
        assert backup.name == "Lib.csproj.bak.20260102030405"
        assert backup.read_text(encoding="utf-8") == WITH_VERSION
