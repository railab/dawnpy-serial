# tools/dawnpy/src/dawnpy/commands/cmd_serial.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containing serial commands."""

import hashlib
import struct
import time

import click
from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.cli.options import configure_cli_logging
from dawnpy.objectid import ObjectIdDecoder

from dawnpy_serial.client import run_console
from dawnpy_serial.serial import DawnSerialProtocol


def _dtype_id(decoder: ObjectIdDecoder, dtype_name: str) -> int:
    """
    Resolve numeric dtype value by dtype type name.

    :param decoder: Object ID decoder with loaded dtype metadata.
    :param dtype_name: Dtype name from YAML (e.g. ``"uint32"``).
    :return: Numeric dtype ID.
    :raises click.ClickException: When dtype is not found.
    """
    target = dtype_name.strip().lower()

    for dtype_id, info in decoder.dtype_info.items():
        if str(info.get("type", "")).strip().lower() == target:
            return int(dtype_id)

    raise click.ClickException(f"Unsupported dtype mapping: {dtype_name}")


def _resolve(decoder: ObjectIdDecoder, kind: str, name: str) -> int:
    """Look up a header-defined enum and raise ClickException if missing."""
    if kind == "object_type":
        value = decoder.find_object_type(name)
    elif kind == "io_class":
        value = decoder.find_io_class(name)
    else:
        raise click.ClickException(f"Unknown lookup kind: {kind}")
    if value is None:
        raise click.ClickException(f"Unknown {kind}: {name}")
    return value


def _descriptor_objid(decoder: ObjectIdDecoder, slot: int) -> int:
    """
    Build ObjectID for descriptor IO of a slot.

    :param decoder: Object ID decoder.
    :param slot: Descriptor slot index.
    :return: Encoded descriptor ObjectID.
    """
    return decoder.encode(
        obj_type=_resolve(decoder, "object_type", "io"),
        cls=_resolve(decoder, "io_class", "descriptor"),
        dtype=_dtype_id(decoder, "block"),
        flags=0,
        priv=slot,
    )


def _descselector_objid(decoder: ObjectIdDecoder) -> int:
    """
    Build ObjectID for descriptor selector IO.

    :param decoder: Object ID decoder.
    :return: Encoded descriptor selector ObjectID (instance 0).
    """
    return decoder.encode(
        obj_type=_resolve(decoder, "object_type", "io"),
        cls=_resolve(decoder, "io_class", "desc_selector"),
        dtype=_dtype_id(decoder, "uint32"),
        flags=0,
        priv=0,
    )


def _wait_reconnect(
    port: str,
    baudrate: int,
    timeout_s: float,
    debug: bool,
) -> bool:
    """
    Wait for serial endpoint to reconnect and respond to ping.

    :param port: Serial port path.
    :param baudrate: Serial baudrate.
    :param timeout_s: Maximum reconnect wait time in seconds.
    :param debug: Enable verbose protocol logs.
    :return: True when device reconnects and responds, else False.
    """
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        client = DawnSerialProtocol(port, baudrate=baudrate, verbose=debug)
        try:
            if not client.connect():
                time.sleep(0.2)
                continue

            if client.ping():
                client.disconnect()
                return True
        finally:
            client.disconnect()

        time.sleep(0.2)

    return False


def _connect_and_ping(client: DawnSerialProtocol) -> None:
    """
    Connect and verify protocol responsiveness.

    :param client: Serial protocol client.
    :raises click.ClickException: On connect or ping failure.
    """
    if not client.connect():
        raise click.ClickException("Failed to open serial port")

    if not client.ping():
        raise click.ClickException("No PONG response from device")


def _upload_chunks(
    client: DawnSerialProtocol,
    descriptor_objid: int,
    payload: bytes,
    chunk_size: int,
) -> None:
    """
    Upload descriptor payload in seek-write chunks.

    :param client: Serial protocol client.
    :param descriptor_objid: Descriptor IO ObjectID.
    :param payload: Full descriptor payload bytes.
    :param chunk_size: Chunk size in bytes.
    :raises click.ClickException: On first write failure.
    """
    offset = 0
    total = len(payload)

    while offset < total:
        chunk = payload[offset : offset + chunk_size]
        if not client.write_io_seek(descriptor_objid, offset, chunk):
            raise click.ClickException(
                f"SET_IO_SEEK failed at offset {offset}"
            )
        offset += len(chunk)


def _verify_seek_payload(
    client: DawnSerialProtocol,
    descriptor_objid: int,
    payload: bytes,
) -> None:
    """
    Verify uploaded payload by read-back and SHA256 comparison.

    :param client: Serial protocol client.
    :param descriptor_objid: Descriptor IO ObjectID.
    :param payload: Expected descriptor bytes.
    :raises click.ClickException: When read-back fails or hashes differ.
    """
    read_back = client.read_io_seek(descriptor_objid)
    if read_back is None:
        raise click.ClickException("Read-back verification failed")

    expected_hash = hashlib.sha256(payload).hexdigest()
    actual_hash = hashlib.sha256(read_back).hexdigest()
    if expected_hash != actual_hash:
        raise click.ClickException(
            "Read-back hash mismatch:\n"
            f"  expected: {expected_hash}\n"
            f"  actual:   {actual_hash}"
        )
    click.echo(f"Verify OK (sha256={expected_hash})")


def _request_switch_and_wait(
    client: DawnSerialProtocol,
    selector_objid: int,
    slot: int,
    path: str,
    baudrate: int,
    wait_reconnect_s: float,
    debug: bool,
) -> None:
    """
    Request descriptor switch and optionally wait for reconnect.

    :param client: Serial protocol client.
    :param selector_objid: Descriptor selector ObjectID.
    :param slot: Target slot index.
    :param path: Serial port path.
    :param baudrate: Serial baudrate.
    :param wait_reconnect_s: Reconnect wait timeout in seconds.
    :param debug: Enable verbose protocol logging.
    :raises click.ClickException: On switch request or reconnect failure.
    """
    if not client.write_io(selector_objid, struct.pack("<I", slot)):
        raise click.ClickException("Failed to request descriptor switch")
    click.echo(f"Switch request sent for slot {slot}")

    if wait_reconnect_s <= 0:
        return

    client.disconnect()
    click.echo(f"Waiting for reconnect (timeout {wait_reconnect_s:.1f}s)...")
    if not _wait_reconnect(
        path,
        baudrate=baudrate,
        timeout_s=wait_reconnect_s,
        debug=debug,
    ):
        raise click.ClickException("Reconnect timeout after switch request")
    click.echo("Reconnect OK")


def _upload_descriptor(
    path: str,
    bin_path: str,
    slot: int,
    chunk_size: int,
    baudrate: int,
    verify: bool,
    switch: bool,
    wait_reconnect_s: float,
    debug: bool,
) -> bool:
    """
    Upload a raw descriptor binary to a descriptor slot over serial.

    :param path: Serial port path.
    :param bin_path: Path to input binary descriptor file.
    :param slot: Destination descriptor slot index.
    :param chunk_size: Upload chunk size in bytes.
    :param baudrate: Serial baudrate.
    :param verify: Read-back verify written slot contents.
    :param switch: Request slot activation after upload.
    :param wait_reconnect_s: Wait timeout after switch request (seconds).
    :param debug: Enable verbose protocol logs.
    :return: True on success, False on failure.
    """
    payload = open(bin_path, "rb").read()
    total = len(payload)

    if total == 0:
        raise click.ClickException("Descriptor binary is empty")

    if chunk_size <= 0:
        raise click.ClickException("--chunk-size must be > 0")

    click.echo(f"Uploading {total} bytes to slot {slot} from {bin_path}")

    decoder = ObjectIdDecoder()
    descriptor_objid = _descriptor_objid(decoder, slot)
    selector_objid = _descselector_objid(decoder)

    client = DawnSerialProtocol(path, baudrate=baudrate, verbose=debug)
    try:
        _connect_and_ping(client)

        click.echo(f"Descriptor IO ObjectID: 0x{descriptor_objid:08X}")
        click.echo(f"Selector IO ObjectID:   0x{selector_objid:08X}")

        _upload_chunks(client, descriptor_objid, payload, chunk_size)
        click.echo("Upload complete")

        if verify:
            _verify_seek_payload(client, descriptor_objid, payload)

        if switch:
            _request_switch_and_wait(
                client=client,
                selector_objid=selector_objid,
                slot=slot,
                path=path,
                baudrate=baudrate,
                wait_reconnect_s=wait_reconnect_s,
                debug=debug,
            )
    finally:
        client.disconnect()

    return True


###############################################################################
# Command Group: serial
###############################################################################


@click.group(name="serial", invoke_without_command=True)
@click.argument("path", type=click.Path(resolve_path=False), required=False)
@click.option(
    "--descriptor",
    "-d",
    "descriptor_path",
    type=click.Path(exists=True, dir_okay=True, file_okay=True),
    help=(
        "Optional descriptor.yaml path or config directory. When provided, "
        "the console uses descriptor-backed IOs instead of CMD_LIST_IOS "
        "discovery."
    ),
)
@click.option(
    "--debug/--no-debug",
    default=False,
    is_flag=True,
    envvar="DAWNPY_DEBUG",
)
@pass_environment
@click.pass_context
def cmd_serial(
    click_ctx: click.Context,
    ctx: Environment,
    path: str | None,
    descriptor_path: str | None,
    debug: bool,
) -> bool:
    """
    Run serial console or serial utility subcommands.

    When called as ``dawnpy-serial /dev/ttyUSB0`` without a subcommand,
    starts interactive serial console.
    """
    ctx.debug = debug
    configure_cli_logging(debug)

    if click_ctx.invoked_subcommand is not None:
        return True

    if not path:
        raise click.UsageError(
            "PATH is required for interactive mode "
            "(e.g. `dawnpy-serial /dev/ttyUSB0`)"
        )

    run_console(port=path, debug=ctx.debug, descriptor_path=descriptor_path)
    return True


###############################################################################
# Subcommand: serial upload
###############################################################################


@cmd_serial.command(name="upload")
@click.argument("path", type=click.Path(resolve_path=False), required=True)
@click.argument(
    "descriptor_bin",
    type=click.Path(exists=True, dir_okay=False, resolve_path=False),
    required=True,
)
@click.option(
    "--slot",
    type=int,
    default=1,
    show_default=True,
    help="Target descriptor slot (slot 0 is read-only).",
)
@click.option(
    "--chunk-size",
    type=int,
    default=128,
    show_default=True,
    help="Upload chunk size in bytes for CMD_SET_IO_SEEK.",
)
@click.option(
    "--baudrate",
    type=int,
    default=115200,
    show_default=True,
    help="Serial baudrate.",
)
@click.option(
    "--verify/--no-verify",
    default=True,
    show_default=True,
    help="Read back uploaded slot and verify SHA256.",
)
@click.option(
    "--switch/--no-switch",
    default=True,
    show_default=True,
    help="Request descriptor slot switch after upload.",
)
@click.option(
    "--wait-reconnect",
    type=float,
    default=10.0,
    show_default=True,
    help="Reconnect timeout in seconds after switch request.",
)
@pass_environment
def cmd_serial_upload(
    ctx: Environment,
    path: str,
    descriptor_bin: str,
    slot: int,
    chunk_size: int,
    baudrate: int,
    verify: bool,
    switch: bool,
    wait_reconnect: float,
) -> bool:
    """
    Upload raw descriptor binary to a descriptor slot over serial.

    PATH is the serial port (for example ``/dev/ttyUSB0``).
    DESCRIPTOR_BIN is a raw little-endian descriptor binary file.
    """
    if slot < 1:
        raise click.ClickException("slot must be >= 1")

    return _upload_descriptor(
        path=path,
        bin_path=descriptor_bin,
        slot=slot,
        chunk_size=chunk_size,
        baudrate=baudrate,
        verify=verify,
        switch=switch,
        wait_reconnect_s=wait_reconnect if switch else 0.0,
        debug=ctx.debug,
    )
