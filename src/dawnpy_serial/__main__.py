"""Standalone CLI entry point for dawnpy-serial."""

from dawnpy_serial.commands.cmd_serial import cmd_serial


def main() -> None:
    """Run the serial CLI."""
    cmd_serial(prog_name="dawnpy-serial")


if __name__ == "__main__":
    main()
