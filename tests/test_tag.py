"""commands.tag: tag the repository with the version of its .csproj."""

import pytest

import commands.tag as tag
from conftest import exits_with, write_file

CSPROJ = "<Project>\n  <PropertyGroup>\n    <Version>{}</Version>\n  </PropertyGroup>\n</Project>\n"


@pytest.fixture
def src(in_tmp):
    write_file(in_tmp / "src" / "Lib" / "Lib.csproj", CSPROJ.format("1.4.0"))
    return in_tmp / "src"


class TestFlagsAndPath:
    def test_given_no_flags_when_parsed_then_it_does_not_push_and_the_remote_is_origin(self):
        assert tag.parse_flags(["tag"]) == (False, "origin")

    def test_given_push_and_a_remote_when_parsed_then_both_are_read(self):
        assert tag.parse_flags(["tag", "--push", "--remote", "upstream"]) == (True, "upstream")

    @pytest.mark.parametrize("argv", [["tag", "--remote"], ["tag", "--remote", "--push"]])
    def test_given_a_remote_flag_without_a_name_when_parsed_then_it_exits(self, argv):
        with exits_with(1):
            tag.parse_flags(argv)

    def test_given_no_path_when_resolved_then_src_is_used(self, src):
        assert tag.resolve_base_path(["tag", "--push"]) == src.resolve()

    def test_given_no_path_and_no_src_when_resolved_then_it_exits(self, in_tmp):
        with exits_with(1):
            tag.resolve_base_path(["tag"])

    def test_given_a_remote_name_before_the_path_when_resolved_then_it_is_not_taken_for_the_path(self, src):
        assert tag.resolve_base_path(["tag", "--remote", "upstream", str(src / "Lib")]) == (src / "Lib").resolve()

    def test_given_a_missing_path_when_resolved_then_it_exits(self, in_tmp):
        with exits_with(1):
            tag.resolve_base_path(["tag", str(in_tmp / "nope")])


class TestProjectAndVersion:
    def test_given_one_csproj_anywhere_below_when_found_then_it_is_returned(self, src):
        assert tag.find_single_csproj(src).name == "Lib.csproj"

    def test_given_no_csproj_when_found_then_it_exits(self, in_tmp):
        with exits_with(1):
            tag.find_single_csproj(in_tmp)

    def test_given_many_csproj_when_found_then_it_exits_naming_the_first_five(self, in_tmp, capsys):
        for index in range(7):
            write_file(in_tmp / f"P{index}" / f"P{index}.csproj")
        with exits_with(1):
            tag.find_single_csproj(in_tmp)
        assert capsys.readouterr().out.rstrip().endswith("...")

    def test_given_a_version_with_spaces_when_read_then_it_is_trimmed(self, in_tmp):
        assert tag.read_version_from_csproj(write_file(in_tmp / "a.csproj", CSPROJ.format(" 2.0.1 "))) == "2.0.1"

    def test_given_a_namespaced_csproj_when_read_then_the_version_is_still_found(self, in_tmp):
        xml = ('<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'
               "<PropertyGroup><Version>3.1.0</Version></PropertyGroup></Project>")
        assert tag.read_version_from_csproj(write_file(in_tmp / "a.csproj", xml)) == "3.1.0"

    def test_given_no_version_when_read_then_it_exits(self, in_tmp):
        csproj = write_file(in_tmp / "a.csproj", "<Project><PropertyGroup /></Project>")
        with exits_with(1):
            tag.read_version_from_csproj(csproj)

    def test_given_malformed_xml_when_read_then_it_exits(self, in_tmp, capsys):
        with exits_with(1):
            tag.read_version_from_csproj(write_file(in_tmp / "a.csproj", "<Project>"))
        assert "Failed to parse csproj" in capsys.readouterr().out


class TestTagging:
    def test_given_a_version_when_run_then_an_annotated_tag_is_created(self, src, fake_run):
        fake_run.results[("git", "rev-parse")] = 1  # no such tag yet
        assert tag.main(["tag"]) == 0
        assert fake_run.calls == [
            ["git", "rev-parse", "--verify", "v1.4.0"],
            ["git", "tag", "-a", "v1.4.0", "-m", "Release 1.4.0"],
        ]

    def test_given_push_when_run_then_the_tag_goes_to_the_chosen_remote(self, src, fake_run):
        fake_run.results[("git", "rev-parse")] = 1
        assert tag.main(["tag", "--push", "--remote", "upstream"]) == 0
        assert fake_run.calls[-1] == ["git", "push", "upstream", "v1.4.0"]

    def test_given_a_tag_that_already_exists_when_run_then_it_exits_without_tagging(self, src, fake_run, capsys):
        with exits_with(1):
            tag.main(["tag"])
        assert [c[1] for c in fake_run.calls] == ["rev-parse"]
        assert "Tag 'v1.4.0' already exists" in capsys.readouterr().out

    def test_given_git_missing_when_checking_the_tag_then_the_tag_command_reports_it(self, src, monkeypatch, fake_run):
        calls = []

        def run(cmd, check=False, **kwargs):
            calls.append(cmd)
            if cmd[1] == "rev-parse":
                raise FileNotFoundError("git")
            return fake_run(cmd, check=check, **kwargs)

        monkeypatch.setattr(tag.subprocess, "run", run)
        assert tag.create_git_tag("1.4.0") == "v1.4.0"
        assert calls[-1][:2] == ["git", "tag"]

    def test_given_a_failing_git_tag_when_run_then_it_exits(self, src, fake_run):
        fake_run.results[("git", "rev-parse")] = 1
        fake_run.results[("git", "tag")] = 128
        with exits_with(1):
            tag.main(["tag"])
