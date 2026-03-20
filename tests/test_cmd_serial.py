"""Tests for dawnpy-serial CLI command wiring."""

from click.testing import CliRunner

import dawnpy_serial.commands.cmd_serial as cmd_serial_mod
from dawnpy_serial.commands.cmd_serial import cmd_serial


def test_serial_console_accepts_descriptor_option(monkeypatch, tmp_path):
    """The console should pass --descriptor through to run_console."""
    descriptor = tmp_path / "descriptor.yaml"
    descriptor.write_text("ios: []\n", encoding="utf-8")
    calls = []

    def _run_console(port, debug=False, descriptor_path=None):
        calls.append((port, debug, descriptor_path))

    monkeypatch.setattr(cmd_serial_mod, "run_console", _run_console)

    result = CliRunner().invoke(
        cmd_serial,
        [
            "--descriptor",
            str(descriptor),
            "/dev/ttyUSB0",
        ],
    )

    assert result.exit_code == 0
    assert calls == [("/dev/ttyUSB0", False, str(descriptor))]


def test_serial_help_documents_descriptor_option():
    """CLI help should expose descriptor-backed discovery."""
    result = CliRunner().invoke(cmd_serial, ["--help"])

    assert result.exit_code == 0
    assert "--descriptor" in result.output
    assert "CMD_LIST_IOS" in result.output
