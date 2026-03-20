#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/serial/client.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Serial console interface for DawnSerialProtocol client.

Provides interactive console for serial device communication.
"""

import struct
import time
from collections.abc import Callable
from typing import Any

from dawnpy.cli.simple_device_client import SimpleDeviceClient
from dawnpy.cli.simple_device_console import SimpleDeviceConsole
from dawnpy.device.decode import decode_value

from dawnpy_serial.serial import DawnSerialProtocol


class SerialClient(SimpleDeviceClient):
    """Serial communication client for Dawn devices."""

    connect_error = "ERROR: Failed to connect to device"
    ping_error = "ERROR: Failed to ping device"

    def __init__(
        self,
        port: str,
        debug: bool = False,
        descriptor_path: str | None = None,
    ) -> None:
        """
        Initialize serial client.

        Args:
            port: Serial port path
        """
        super().__init__(descriptor_path=descriptor_path)
        self.port = port
        self.debug = debug
        self.client = DawnSerialProtocol(port, verbose=debug)

    def discovery(
        self,
    ) -> None:  # pragma: no cover
        """Discover device information and list all available IOs."""
        if not self.connected:
            print("ERROR: Not connected to device")
            return

        print("=" * 60)
        print("Device Discovery: Basic IO Information")
        print("=" * 60)

        # Use descriptor-backed IOs when provided, otherwise device discovery.
        io_data = self.discover_ios()
        self.discovered_ios = io_data

        # Print results
        if not io_data:
            print("No IO objects found")
            return

        print("\nDetailed IO Information:")
        for objid, info in io_data.items():
            print(f"\nObject ID: 0x{objid:08X}")
            print(f"  Type: {info['io_type_str']}")
            print(f"  Dimension: {info['dimension']}")
            print(f"  Data Type: {info['dtype']}")
            if info.get("data"):
                print(f"  Data (hex): {info['data']}")
                print(f"  Data (raw): {info['data_bytes']}")

    def list_discovered_features(self) -> None:
        """List features discovered during initial discovery."""
        if not self.discovered_ios:
            print("No discovered IOs. Run discovery (d) first.")
            return

        print("\nDetailed IO Information:")
        for objid in sorted(self.discovered_ios):
            info = self.discovered_ios[objid]
            decoded = self.client.decode_object_id(objid)
            print(f"\nObject ID: 0x{objid:08X} ({decoded})")
            print(f"  Type: {info.get('io_type_str', 'unknown')}")
            print(f"  Dimension: {info.get('dimension', 'unknown')}")
            print(f"  Data Type: {info.get('dtype', 'unknown')}")
            if info.get("data") is not None:
                print(f"  Data (hex): {info.get('data')}")
                print(f"  Data (raw): {info.get('data_bytes')}")
                try:
                    data_bytes = info.get("data_bytes", [])
                    if not isinstance(data_bytes, list) or not all(
                        isinstance(b, int) for b in data_bytes
                    ):
                        raise TypeError("Invalid data_bytes")
                    data = bytes(data_bytes)
                    dtype_val = info.get("dtype", 0)
                    dtype = dtype_val if isinstance(dtype_val, int) else 0
                    print("  Data (decoded): ", end="")
                    self.format_value(
                        objid,
                        data,
                        dtype,
                        include_objid=False,
                    )
                except Exception:
                    print("  Data (decoded): <decode failed>")

    def monitoring(
        self,
        poll_interval: float = 1.0,
        duration: float = 10.0,
        objids: list[int] | None = None,
    ) -> None:  # pragma: no cover  # Has time.sleep() loop
        """Monitor IO values continuously over a duration."""
        print("\n" + "=" * 60)
        print("Continuous IO Monitoring")
        print("=" * 60)

        client = DawnSerialProtocol(self.port)

        try:
            if not client.connect() or not client.ping():
                return

            # Use provided list or get all IOs
            if objids is None:
                io_list = self.known_objids() or client.get_io_list()
            else:
                io_list = objids

            if not io_list:
                print("No IO objects found")
                return

            msg = f"Monitoring {len(io_list)} IO objects for {duration}s"
            print(f"\n{msg}...")
            print(f"Poll interval: {poll_interval}s\n")

            start_time = time.time()
            poll_count = 0

            while time.time() - start_time < duration:
                print(f"--- Poll #{poll_count} ---")

                for objid in io_list:
                    data = client.read_io(objid)
                    if data is not None:
                        info = client.get_io_info(objid)
                        dtype = info["dtype"] if info else 0
                        lines = decode_value(
                            data,
                            dtype=dtype,
                            objid_decoder=client.objid_decoder,
                            include_objid=True,
                            objid=objid,
                            debug=False,
                        )
                        for idx, line in enumerate(lines):
                            prefix = "  " if idx == 0 else "    "
                            print(f"{prefix}{line}")
                    else:
                        print(f"  0x{objid:08X}: ERROR")

                poll_count += 1
                time.sleep(poll_interval)

            print(f"\nMonitoring complete. Total polls: {poll_count}")

        finally:
            client.disconnect()

    def selective_access(self, objids: list[int]) -> None:  # pragma: no cover
        """Access and read specific IO objects by their IDs."""
        print("\n" + "=" * 60)
        print("Selective IO Access")
        print("=" * 60)

        client = DawnSerialProtocol(self.port)

        try:
            if not client.connect() or not client.ping():
                return

            print(f"\nAccessing {len(objids)} specific IO objects:\n")

            for objid in objids:
                print(f"Reading IO 0x{objid:08X}:")

                # Get info
                info = client.get_io_info(objid)
                if not info:
                    print("  ERROR: Failed to get info")
                    continue

                print(f"  Type: {info['io_type_str']}")
                print(f"  Dimension: {info['dimension']}")
                print(f"  Data Type: {info['dtype']}")

                # Read data
                data = client.read_io(objid)
                if data:
                    print(f"  Value (hex): {data.hex()}")

                    # Try to interpret based on data type
                    if len(data) == 1:
                        print(f"  Value (uint8): {data[0]}")
                    elif len(data) == 2:
                        val = struct.unpack("<H", data)[0]
                        print(f"  Value (uint16): {val}")
                    elif len(data) == 4:
                        val = struct.unpack("<I", data)[0]
                        print(f"  Value (uint32): {val}")
                        val_float = struct.unpack("<f", data)[0]
                        print(f"  Value (float): {val_float}")
                else:
                    print("  ERROR: Failed to read data")

                print()

        finally:
            client.disconnect()

    def parse_types(self) -> None:  # pragma: no cover  # noqa: C901
        """Parse common data types from IOs."""
        print("\n" + "=" * 60)
        print("Parse Common Data Types")
        print("=" * 60)

        client = DawnSerialProtocol(self.port)

        try:
            if not client.connect() or not client.ping():
                return

            io_list = self.known_objids() or client.get_io_list()
            if not io_list:
                print("No IO objects found")
                return

            print("\nParsing IO data with type interpretation:\n")

            for objid in io_list[:5]:  # Limit to first 5
                info = client.get_io_info(objid)
                if not info:
                    continue

                data = client.read_io(objid)
                if not data:
                    continue

                print(f"IO 0x{objid:08X} (dtype={info['dtype']}):")

                # Parse based on length
                try:
                    if len(data) == 1:
                        print(f"  uint8:  {struct.unpack('B', data)[0]}")
                    elif len(data) == 2:
                        print(f"  uint16: {struct.unpack('<H', data)[0]}")
                        print(f"  int16:  {struct.unpack('<h', data)[0]}")
                    elif len(data) == 4:
                        print(f"  uint32: {struct.unpack('<I', data)[0]}")
                        print(f"  int32:  {struct.unpack('<i', data)[0]}")
                        print(f"  float:  {struct.unpack('<f', data)[0]}")
                    elif len(data) == 8:
                        print(f"  uint64: {struct.unpack('<Q', data)[0]}")
                        print(f"  double: {struct.unpack('<d', data)[0]}")
                    else:
                        print(f"  raw:    {data.hex()}")
                except struct.error as e:
                    print(f"  ERROR parsing: {e}")

                print()

        finally:
            client.disconnect()

    def timing(self, num_reads: int = 100) -> None:  # pragma: no cover
        """Analyze communication timing."""
        print("\n" + "=" * 60)
        print("Communication Timing Analysis")
        print("=" * 60)

        client = DawnSerialProtocol(self.port)

        try:
            if not client.connect() or not client.ping():
                return

            io_list = client.get_io_list()
            if not io_list:
                print("No IO objects found")
                return

            objid = io_list[0]
            print(f"\nTiming {num_reads} reads from IO 0x{objid:08X}...\n")

            times = []
            start = time.time()

            for _ in range(num_reads):
                read_start = time.time()
                data = client.read_io(objid)
                read_time = time.time() - read_start

                if data:
                    times.append(read_time * 1000)  # Convert to ms

            total_time = time.time() - start

            if times:
                print(f"Total time: {total_time:.3f}s")
                print(f"Average read time: {sum(times) / len(times):.3f}ms")
                print(f"Min read time: {min(times):.3f}ms")
                print(f"Max read time: {max(times):.3f}ms")
                print(f"Throughput: {len(times) / total_time:.1f} reads/sec")
            else:
                print("No successful reads")

        finally:
            client.disconnect()

    def write_io(
        self, objid: int, value: int, use_dtype_packing: bool = True
    ) -> None:  # pragma: no cover
        """Write data to IO objects with proper dtype packing."""
        print("\n" + "=" * 60)
        print("Write Data to IO Objects")
        print("=" * 60)

        proto = DawnSerialProtocol(self.port)

        try:
            if not proto.connect() or not proto.ping():
                return

            print(f"\nWriting to {proto.decode_object_id(objid)}:")

            # Get IO info first to verify it's writable
            info = proto.get_io_info(objid)
            if not info:
                print("  ERROR: Failed to get IO info")
                return

            print(f"  IO Type: {info['io_type_str']}")
            print(f"  Data Type: {info['dtype']}")

            # Check if writable
            if info["io_type"] == proto.IO_TYPE_READ_ONLY:
                print("  ERROR: IO is read-only, cannot write")
                return

            # Pack data according to dtype
            if use_dtype_packing:
                data = proto.pack_data_by_dtype(info["dtype"], value)
                if data is None:
                    dtype = info["dtype"]
                    print(f"  ERROR: Could not pack data for dtype {dtype}")
                    return
                print(f"  Value: {value} -> Packed (hex): {data.hex()}")
            else:
                data = struct.pack("<I", value)
                print(f"  Value: {value} -> Packed (hex): {data.hex()}")

            # Write the data
            if proto.write_io(objid, data):
                print("  SUCCESS: Data written")

                # Read it back to verify
                print("\n  Verifying written data...")
                read_back = proto.read_io(objid)
                if read_back:
                    print(f"  Read back (hex): {read_back.hex()}")
                    if read_back == data:
                        print("  VERIFICATION: Data matches!")
                    else:
                        print("  WARNING: Data mismatch!")
                else:
                    print("  ERROR: Failed to read back data")
            else:
                print("  ERROR: Write failed")

        finally:
            proto.disconnect()

    def write_multiple(self) -> None:  # pragma: no cover
        """Write multiple values with different data types."""
        print("\n" + "=" * 60)
        print("Write Multiple Values with Different Types")
        print("=" * 60)

        client = DawnSerialProtocol(self.port)

        try:
            if not client.connect() or not client.ping():
                return

            # Get list of IOs
            io_list = self.known_objids() or client.get_io_list()
            if not io_list:
                print("No IO objects found")
                return

            print(f"\nDiscovered {len(io_list)} IO objects")
            print("Attempting to write values to writable IOs:\n")

            write_count = 0
            success_count = 0
            skipped_count = 0

            for objid in io_list:
                info = client.get_io_info(objid)
                if not info:
                    continue

                # Skip read-only IOs
                if info["io_type"] == client.IO_TYPE_READ_ONLY:
                    decoded_id = client.decode_object_id(objid)
                    print(f"  {decoded_id}: SKIPPED (read-only)")
                    skipped_count += 1
                    continue

                write_count += 1
                decoded_id = client.decode_object_id(objid)

                # Create test value based on dtype
                # Map test values for different data types
                dtype_test_values = {
                    "bool": 1,  # true
                    "int8": -42,
                    "uint8": 200,
                    "int16": -1000,
                    "uint16": 50000,
                    "int32": -100000,
                    "uint32": 3000000000,
                    "int64": -9000000000000,
                    "uint64": 18000000000000,
                    "float": 3.14159,
                    "double": 2.71828,
                    "char": "A",
                }

                # Get dtype name from decoder if available
                dtype_name = "uint32"  # default
                if client.objid_decoder:
                    dtype_info = client.objid_decoder.dtype_info.get(
                        info["dtype"], {}
                    )
                    dtype_name = dtype_info.get("type", "uint32")

                test_value = dtype_test_values.get(dtype_name, 42)

                # Pack data according to dtype
                packed_data = client.pack_data_by_dtype(
                    info["dtype"], test_value
                )
                if packed_data is None:
                    msg = f"SKIPPED (unsupported dtype {dtype_name})"
                    print(f"  {decoded_id}: {msg}")
                    skipped_count += 1
                    continue

                print(
                    f"  {decoded_id}: Writing {dtype_name}({test_value})...",
                    end=" ",
                )

                if client.write_io(objid, packed_data):
                    success_count += 1
                    print("OK")
                else:
                    print("FAILED")

            print("\nWrite summary:")
            print(f"  Successful: {success_count}/{write_count}")
            print(f"  Skipped: {skipped_count} (read-only or unsupported)")

        finally:
            client.disconnect()


class SerialConsole(SimpleDeviceConsole):  # pragma: no cover
    """Interactive serial console for device communication."""

    initial_discovery_error = "Initial discovery failed. Exiting."
    allow_empty_raw_bytes = True

    def __init__(
        self,
        port: str,
        debug: bool = False,
        descriptor_path: str | None = None,
    ) -> None:  # pragma: no cover
        """
        Initialize serial console.

        Args:
            port: Serial port path
        """
        super().__init__(
            prompt="\nEnter command (h for help): ",
            history_file=".dawnpy_serial_history",
        )
        self.client = SerialClient(
            port,
            debug=debug,
            descriptor_path=descriptor_path,
        )

    def _console_header(self) -> str:
        """Return the serial startup banner."""
        return f"\nSerial Console - Port: {self.client.port}"

    def commands_no_args(self) -> dict[str, Callable[[], None]]:
        """Return serial-specific commands."""
        commands = dict(super().commands_no_args())
        commands.update(
            {
                "p": self.cmd_parse_types,
                "t": self.cmd_timing,
            }
        )
        return commands

    def _on_exit(self) -> None:
        """Render the serial exit message."""
        self.info("Exiting serial console.")

    def _monitoring_kwargs(self) -> dict[str, Any]:
        """Use the original serial console polling defaults."""
        return {"poll_interval": 0.5, "duration": 5.0}

    def show_menu(self) -> None:  # pragma: no cover
        """Display command menu."""
        self.print_menu(
            "Serial Console - Commands",
            [
                "d: Device discovery - Basic IO information",
                "l: List discovered features",
                "p: Parse types - Parse common data types",
                "t: Timing analysis - Analyze communication timing",
                "",
                "m [objid]: Continuous monitoring - Monitor IO values",
                "  Usage: m (monitor all IOs)",
                "  Single: m 0x40A10001",
                "  Multiple: m 0x40A10001,0x40A10002",
                "",
                "r <objid>: Read object ID (hex)",
                "  Auto-uses seek read for DTYPE_BLOCK object IDs.",
                "  Usage: r 0x40A10001",
                "  Multiple: r 0x40A10001,0x40A10002",
                "",
                "s <objid>: Read seekable IO (hex dump via CMD_GET_IO_SEEK)",
                "  Usage: s 0x40A10001",
                "",
                "w <objid> <value>: Write value to IO object",
                "  Single: w 0x40A10001 100",
                "  Multiple: w -m (write to all writable IOs)",
                "",
                "h: Show this help message",
                "q: Quit",
                "",
                "Command history is saved automatically. "
                "Use UP/DOWN arrows to",
                "navigate through previous commands.",
            ],
        )

    def cmd_parse_types(self) -> None:  # pragma: no cover
        """Run parse common types."""
        self.client.parse_types()

    def cmd_timing(self) -> None:  # pragma: no cover
        """Run timing analysis."""
        self.client.timing(num_reads=50)

    def cmd_write(self, args: str) -> None:  # pragma: no cover
        """
        Write value to IO object(s).

        Supports two modes:
        1. Single write with arguments: w 0x40A10001 100
        1a. Single write hex bytes: w 0x40A10001 0x01FF
        2. Write multiple values: w -m (writes to all writable IOs)
        """
        if not args:
            print("ERROR: Usage: w 0x40A10001 100  or  w -m")
            return

        # Parse arguments for single write mode
        parts = args.split()

        # Check for multiple write flag
        if parts[0] == "-m":
            self.client.write_multiple()
            return

        # Single write mode with objid and value
        if len(parts) < 2:
            print("ERROR: Usage: w 0x40A10001 100")
            return

        objid = self.client.parse_object_id(parts[0])
        if objid is None:
            return

        raw = self.client.parse_hex_bytes(parts[1])
        if raw is not None:
            self.client.write_io_raw(objid, raw)
            return

        try:
            value = int(parts[1])
        except ValueError:
            print(f"ERROR: Invalid value format: {parts[1]}")
            return

        self.client.write_io_value(objid, value)


def run_console(
    port: str,
    debug: bool = False,
    descriptor_path: str | None = None,
) -> None:  # pragma: no cover
    """
    Run serial console with the given port.

    Args:
        port: Serial port path
    """
    console = SerialConsole(port, debug=debug, descriptor_path=descriptor_path)
    console.run()


if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    run_console(port)
