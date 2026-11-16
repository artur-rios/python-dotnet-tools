"""commands.init_lib, init_min and init_proj: scaffolding, without running dotnet."""

import json

import pytest

import commands.init_lib as init_lib
import commands.init_min as init_min
import commands.init_proj as init_proj
from conftest import exits_with, write_file


class FixedDate:
    """Stands in for datetime in the scaffolders, so the LICENSE year is known."""

    @staticmethod
    def now():
        class _Now:
            year = 2031
        return _Now()


@pytest.fixture(autouse=True)
def fixed_year(monkeypatch):
    monkeypatch.setattr(init_lib, "datetime", FixedDate)
    monkeypatch.setattr(init_min, "datetime", FixedDate)


LIB_FLAGS = ["--solution", "Acme.Lib", "--project", "Acme.Lib.Core", "--author", "Ana", "--company", "Acme",
             "--description", "Core bits", "--version", "0.2.0", "--packageId", "Acme.Core",
             "--repositoryUrl", "https://example.test/acme.git"]


class TestInitLib:
    def test_given_every_flag_when_scaffolded_then_the_library_layout_is_written(self, in_tmp):
        root = in_tmp / "acme"
        assert init_lib.main(["init-lib", "--root", str(root), *LIB_FLAGS]) == 0

        for path in (".editorconfig", ".gitignore", "LICENSE", "README.md", ".wakatime-project",
                     "src/Acme.Lib.sln", "src/Acme.Lib.Core.csproj", "src/README.md",
                     "tests/Acme.Lib.Core.Tests.csproj"):
            assert (root / path).is_file(), path
        csproj = (root / "src" / "Acme.Lib.Core.csproj").read_text(encoding="utf-8")
        assert "<PackageId>Acme.Core</PackageId>" in csproj
        assert "<Version>0.2.0</Version>" in csproj
        assert "<Authors>Ana</Authors>" in csproj
        assert "<RepositoryUrl>https://example.test/acme.git</RepositoryUrl>" in csproj
        assert "__" not in csproj

    def test_given_a_company_other_than_the_author_when_scaffolded_then_the_csproj_names_the_company(self, in_tmp):
        root = in_tmp / "acme"
        assert init_lib.main(["init-lib", "--root", str(root), *LIB_FLAGS]) == 0
        csproj = (root / "src" / "Acme.Lib.Core.csproj").read_text(encoding="utf-8")
        assert "<Authors>Ana</Authors>" in csproj
        assert "<Company>Acme</Company>" in csproj

    def test_given_a_project_directly_under_src_when_scaffolded_then_the_solution_points_at_it(self, in_tmp):
        root = in_tmp / "acme"
        init_lib.main(["init-lib", "--root", str(root), *LIB_FLAGS])
        sln = (root / "src" / "Acme.Lib.sln").read_text(encoding="utf-8")
        assert '"Acme.Lib.Core.csproj"' in sln
        assert "__PROJECT_GUID__" not in sln
        tests = (root / "tests" / "Acme.Lib.Core.Tests.csproj").read_text(encoding="utf-8")
        assert r"..\src\Acme.Lib.Core.csproj" in tests

    def test_given_a_scaffold_when_written_then_the_readme_has_a_versioning_section_and_the_license_the_year(
            self, in_tmp):
        root = in_tmp / "acme"
        init_lib.main(["init-lib", "--root", str(root), *LIB_FLAGS])
        readme = (root / "README.md").read_text(encoding="utf-8")
        assert "## Versioning" in readme
        assert readme.index("## Versioning") < readme.index("## Build, test and publish")
        assert "Core bits" in readme
        assert "2031" in (root / "LICENSE").read_text(encoding="utf-8")

    def test_given_only_a_root_when_scaffolded_then_the_embedded_parameters_fill_the_rest(self, in_tmp):
        root = in_tmp / "lib"
        assert init_lib.main(["init-lib", "--root", str(root)]) == 0
        assert (root / "src" / "ArturRios.NewLibrary.Core.csproj").is_file()
        assert (root / "src" / "ArturRios.NewLibrary.sln").is_file()

    def test_given_a_json_file_when_scaffolded_then_its_values_are_used(self, in_tmp):
        params = {"RootFolder": str(in_tmp / "fromjson"), "SolutionName": "J.Sln", "ProjectName": "J.Proj",
                  "Author": "J", "Company": "J Co", "Description": "d", "PackageId": "J.Pkg",
                  "RepositoryUrl": "u", "Version": "9.9.9"}
        json_file = write_file(in_tmp / "p.json", json.dumps(params))
        assert init_lib.main(["init-lib", "--json", str(json_file)]) == 0
        assert "<Version>9.9.9</Version>" in (in_tmp / "fromjson" / "src" / "J.Proj.csproj").read_text(encoding="utf-8")

    def test_given_a_json_file_and_flags_together_when_scaffolded_then_it_exits(self, in_tmp, capsys):
        json_file = write_file(in_tmp / "p.json", "{}")
        with exits_with(1):
            init_lib.main(["init-lib", "--json", str(json_file), "--root", str(in_tmp / "x")])
        assert "Do not mix --json" in capsys.readouterr().out

    @pytest.mark.parametrize("content, message", [
        (None, "JSON file not found"),
        ("{not json", "Failed to parse JSON"),
        ('{"RootFolder": "x"}', "missing required properties"),
    ])
    def test_given_an_unusable_json_file_when_scaffolded_then_it_exits_saying_why(self, in_tmp, capsys, content, message):
        path = in_tmp / "p.json"
        if content is not None:
            write_file(path, content)
        with exits_with(1):
            init_lib.main(["init-lib", "--json", str(path)])
        assert message in capsys.readouterr().out

    def test_given_an_existing_root_when_scaffolded_then_it_exits_without_touching_it(self, in_tmp):
        (in_tmp / "taken").mkdir()
        with exits_with(1):
            init_lib.main(["init-lib", "--root", str(in_tmp / "taken")])
        assert list((in_tmp / "taken").iterdir()) == []

    def test_given_a_missing_resource_when_read_then_it_exits(self):
        with exits_with(1):
            init_lib._read_text("commands._data", "templates/nope.template")

    def test_given_no_origin_remote_when_the_repository_url_is_looked_up_then_it_is_blank(self, fake_run):
        fake_run.results[("git", "remote")] = 2
        assert init_lib._git_repo_url() == ""

    def test_given_git_missing_when_the_repository_url_is_looked_up_then_it_is_blank(self, fake_run):
        fake_run.error = FileNotFoundError("git")
        assert init_lib._git_repo_url() == ""

    def test_given_parameters_that_are_present_but_false_when_scaffolded_then_each_falls_back_to_its_default(
            self, in_tmp, monkeypatch, fake_run):
        """Every key must be present, but a JSON false or 0 still counts as no value."""
        root = in_tmp / "Fallback"
        params = {"RootFolder": str(root), "SolutionName": False, "ProjectName": 0, "Author": False,
                  "Company": False, "Description": 0, "PackageId": False, "RepositoryUrl": False, "Version": "1.0.0"}
        monkeypatch.setenv("GIT_AUTHOR_NAME", "Env Author")
        assert init_lib.main(["init-lib", "--json", str(write_file(in_tmp / "p.json", json.dumps(params)))]) == 0

        csproj = (root / "src" / "Fallback.csproj").read_text(encoding="utf-8")
        assert (root / "src" / "Fallback.sln").is_file()
        assert "<Authors>Env Author</Authors>" in csproj
        assert "<Company>Env Author</Company>" in csproj  # no company: the author's name
        assert "<PackageId>Fallback</PackageId>" in csproj
        assert "<Description>Fallback library</Description>" in csproj
        assert fake_run.calls == [["git", "remote", "get-url", "origin"]]

    def test_given_broken_embedded_parameters_when_scaffolded_then_it_exits(self, in_tmp, monkeypatch, capsys):
        monkeypatch.setattr(init_lib, "_read_text", lambda package, name: "{broken")
        with exits_with(1):
            init_lib.main(["init-lib", "--root", str(in_tmp / "x")])
        assert "Failed to parse embedded parameters JSON" in capsys.readouterr().out

    @pytest.mark.parametrize("cli, json_value, expected", [("flag", "json", "flag"), (None, "json", "json"), (None, None, None)])
    def test_given_a_flag_and_a_parameter_when_coalesced_then_the_flag_wins(self, cli, json_value, expected):
        assert init_lib.coalesce(cli, json_value) == expected


class TestInitMin:
    def test_given_flags_when_scaffolded_then_the_minimal_layout_is_written(self, in_tmp):
        root = in_tmp / "min"
        assert init_min.main(["init-min", "--root", str(root), "--solution", "MinSuite", "--project", "MinLib",
                              "--author", "Ana", "--description", "Small"]) == 0
        for path in (".editorconfig", ".gitignore", "LICENSE", "README.md", ".wakatime-project",
                     "src/MinSuite.sln", "src/MinLib/MinLib.csproj", "src/README.md", "tests/.gitkeep"):
            assert (root / path).is_file(), path
        assert "<Version>" not in (root / "src" / "MinLib" / "MinLib.csproj").read_text(encoding="utf-8")
        assert r'"MinLib\MinLib.csproj"' in (root / "src" / "MinSuite.sln").read_text(encoding="utf-8")
        assert "2031" in (root / "LICENSE").read_text(encoding="utf-8")
        assert (root / ".wakatime-project").read_text(encoding="utf-8") == "MinLib"

    def test_given_a_json_file_when_scaffolded_then_its_values_are_used(self, in_tmp):
        params = {"RootFolder": str(in_tmp / "m"), "SolutionName": "S", "ProjectName": "P",
                  "Author": "A", "Description": "D"}
        assert init_min.main(["init-min", "--json", str(write_file(in_tmp / "p.json", json.dumps(params)))]) == 0
        assert (in_tmp / "m" / "src" / "P" / "P.csproj").is_file()

    def test_given_a_json_file_and_flags_together_when_scaffolded_then_it_exits(self, in_tmp):
        with exits_with(1):
            init_min.main(["init-min", "--json", str(write_file(in_tmp / "p.json", "{}")), "--author", "A"])

    def test_given_a_missing_json_file_when_scaffolded_then_it_exits(self, in_tmp):
        with exits_with(1):
            init_min.main(["init-min", "--json", str(in_tmp / "missing.json")])

    def test_given_a_json_file_missing_required_values_when_scaffolded_then_it_exits(self, in_tmp, capsys):
        with exits_with(1):
            init_min.main(["init-min", "--json", str(write_file(in_tmp / "p.json", '{"Author": "A"}'))])
        assert "RootFolder" in capsys.readouterr().out

    def test_given_an_existing_root_when_scaffolded_then_it_exits(self, in_tmp):
        (in_tmp / "taken").mkdir()
        with exits_with(1):
            init_min.main(["init-min", "--root", str(in_tmp / "taken")])


class TestInitProj:
    @pytest.mark.parametrize("flags", [[], ["--min"]])
    def test_given_min_or_no_mode_when_scaffolded_then_the_minimal_csproj_is_written(self, in_tmp, flags):
        assert init_proj.main(["init-proj", "--name", str(in_tmp / "Extra"), *flags]) == 0
        csproj = (in_tmp / "Extra" / "Extra.csproj").read_text(encoding="utf-8")
        assert "<PackageId>" not in csproj

    def test_given_nuget_when_scaffolded_then_the_package_metadata_is_present_but_blank(self, in_tmp):
        assert init_proj.main(["init-proj", "--name", str(in_tmp / "Pkg"), "--nuget"]) == 0
        csproj = (in_tmp / "Pkg" / "Pkg.csproj").read_text(encoding="utf-8")
        for tag in ("PackageId", "Version", "Authors", "Company", "Description", "RepositoryUrl"):
            assert f"<{tag}></{tag}>" in csproj
        assert "__" not in csproj

    @pytest.mark.parametrize("argv", [["init-proj"], ["init-proj", "--name", "X", "--min", "--nuget"]])
    def test_given_no_name_or_both_modes_when_scaffolded_then_it_exits(self, in_tmp, argv):
        with exits_with(1):
            init_proj.main(argv)

    def test_given_an_existing_folder_when_scaffolded_then_it_exits(self, in_tmp):
        (in_tmp / "Extra").mkdir()
        with exits_with(1):
            init_proj.main(["init-proj", "--name", str(in_tmp / "Extra")])


def test_given_min_parameters_that_are_present_but_false_when_scaffolded_then_each_falls_back_to_its_default(
        in_tmp, monkeypatch):
    root = in_tmp / "Small"
    params = {"RootFolder": str(root), "SolutionName": False, "ProjectName": 0, "Author": False, "Description": 0}
    for name in ("GIT_AUTHOR_NAME", "USER", "USERNAME"):
        monkeypatch.delenv(name, raising=False)
    assert init_min.main(["init-min", "--json", str(write_file(in_tmp / "p.json", json.dumps(params)))]) == 0
    assert (root / "src" / "Small" / "Small.csproj").is_file()
    assert "Small library" in (root / "README.md").read_text(encoding="utf-8")
