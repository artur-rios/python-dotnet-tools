"""cli: the `python-dotnet-tools <command>` dispatcher."""

import sys
from unittest import mock

import pytest

import cli


@pytest.mark.parametrize("argv", [[], ["-h"], ["--help"], ["help"]])
def test_given_no_command_or_a_help_flag_when_dispatched_then_the_usage_is_printed(argv, capsys):
    assert cli.main(argv) == 0
    assert "Usage: python-dotnet-tools" in capsys.readouterr().out


def test_given_an_unknown_command_when_dispatched_then_it_fails_with_the_usage(capsys):
    assert cli.main(["deploy"]) == 1
    out = capsys.readouterr().out
    assert "Unknown command: deploy" in out
    assert "Usage:" in out


@pytest.mark.parametrize("command, module", [
    ("build", "build"), ("clean", "clean"), ("bump", "bump"), ("tag", "tag"),
    ("init-lib", "init_lib"), ("init-min", "init_min"), ("init-proj", "init_proj"),
])
def test_given_a_command_when_dispatched_then_its_main_gets_the_command_and_the_rest(command, module, monkeypatch):
    target = mock.Mock(return_value=7)
    monkeypatch.setattr(getattr(cli, module), "main", target)
    assert cli.main([command, "a", "--b"]) == 7
    target.assert_called_once_with([command, "a", "--b"])


def test_given_test_when_dispatched_then_commands_test_runs_with_no_arguments(monkeypatch):
    target = mock.Mock(return_value=0)
    monkeypatch.setattr(cli.test, "main", target)
    assert cli.main(["test"]) == 0
    target.assert_called_once_with()


def test_given_no_argv_when_dispatched_then_sys_argv_is_read(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["python-dotnet-tools", "nope"])
    assert cli.main() == 1
    assert "Unknown command: nope" in capsys.readouterr().out


@pytest.mark.parametrize("module, argv, expected", [
    ("commands.bump", ["python-dotnet-bump"], 1),
    ("commands.clean", ["python-dotnet-clean", "."], 0),
    ("commands.init_proj", ["python-dotnet-init-proj", "--name", "Extra"], 0),
])
def test_given_a_console_script_when_called_without_argv_then_it_reads_sys_argv(
        module, argv, expected, monkeypatch, in_tmp):
    import importlib
    monkeypatch.setattr(sys, "argv", argv)
    assert importlib.import_module(module).main() == expected
