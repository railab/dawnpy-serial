#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/serial/serial.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Simple Python library for communicating with Dawn Serial Protocol devices.

This library implements the Dawn Serial Simple Protocol (CProtoSerial)
for reading/writing IO data and device information.
"""

import struct
from functools import partial
from typing import Any

import serial
from dawnpy.objectid import ObjectIdDecoder
from dawnpy.simple_protocol import SimpleProtocolBase


class DawnSerialProtocol(SimpleProtocolBase):
    """Client for communicating with Dawn devices via serial port."""

    STATE_SYNC = 0
    STATE_LEN_LO = 1
    STATE_LEN_HI = 2
    STATE_FRAME = 3

    @staticmethod
    def _received_frame_log_message(cmd_byte: int, frame_len: int) -> str:
        """Build the verbose log message for a received frame."""
        return f"Received frame: CMD=0x{cmd_byte:02X} LEN={frame_len}"

    @staticmethod
    def _reset_receive_state() -> tuple[int, int, int]:
        """Return the initial serial frame parser state."""
        return (
            DawnSerialProtocol.STATE_SYNC,
            0,
            0,
        )

    @staticmethod
    def _frame_complete(length: int, pos: int) -> bool:
        """Return whether the receive buffer holds a complete frame."""
        return pos >= (DawnSerialProtocol.FRAME_MIN_LEN + length)

    def _advance_receive_state(
        self,
        state: int,
        pos: int,
        length: int,
        byte: int,
        buffer: bytearray,
    ) -> tuple[int, int, int]:
        """Advance the byte-wise serial frame parser state."""
        if state == self.STATE_SYNC:
            if byte == self.FRAME_SYNC:
                buffer[0] = byte
                return (self.STATE_LEN_LO, 1, 0)
            return (state, pos, length)

        buffer[pos] = byte

        if state == self.STATE_LEN_LO:
            return (self.STATE_LEN_HI, 2, byte)

        if state == self.STATE_LEN_HI:
            length |= byte << 8
            if length > self.FRAME_MAX_PAYLOAD:
                return self._reset_receive_state()
            return (self.STATE_FRAME, 3, length)

        return (state, pos + 1, length)

    def _parse_received_frame(self, frame: bytes) -> tuple[int, bytes] | None:
        """Validate and decode a completed serial frame."""
        cmd_byte = frame[3]
        return self._parse_frame_bytes(
            frame,
            short_frame_message="Received short frame ({length} bytes)",
            invalid_sync_message="Invalid sync byte: 0x{sync:02X}",
            length_mismatch_message=(
                "Frame length mismatch: expected {expected}, " "got {actual}"
            ),
            log_message_factory=partial(
                self._received_frame_log_message,
                cmd_byte,
            ),
        )

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
        verbose: bool = False,
    ):
        """
        Initialize serial connection.

        Args:
            port: Serial port device (e.g., '/dev/ttyUSB0' or 'COM3')
            baudrate: Baud rate for serial communication
            timeout: Read timeout in seconds
        """
        super().__init__(verbose=verbose)
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Any = None

    def _create_objid_decoder(self) -> ObjectIdDecoder | None:
        """Create the object ID decoder for the serial protocol."""
        return ObjectIdDecoder()

    def connect(self) -> bool:
        """Open serial port and establish connection."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
            )
            self._log(f"Connected to {self.port} @ {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            self._err(f"Failed to open serial port: {e}")
            return False

    def disconnect(self) -> None:
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self._log("Disconnected from serial port")

    @staticmethod
    def _wrap_hex(hexstr: str, prefix: str, max_line: int = 80) -> list[str]:
        """Wrap a hex string into lines with aligned prefixes."""
        available = max_line - len(prefix)
        if available < 8:
            available = 8
        lines = []
        for i in range(0, len(hexstr), available):
            chunk = hexstr[i : i + available]
            if i == 0:
                lines.append(f"{prefix}{chunk}")
            else:
                lines.append(f"{' ' * len(prefix)}{chunk}")
        return lines

    def send_frame(
        self, cmd: int, payload: bytes = b""
    ) -> bool:  # pragma: no cover
        """
        Send a frame to the device.

        Frame format: [SYNC][LEN][CMD][PAYLOAD][CRC]

        Args:
            cmd: Command byte
            payload: Optional payload bytes

        Returns:
            True if successful, False otherwise
        """
        if not self.serial or not self.serial.is_open:
            self._err("Serial port not open")
            return False

        if len(payload) > self.FRAME_MAX_PAYLOAD:
            self._err(
                f"Payload too large: {len(payload)} > {self.FRAME_MAX_PAYLOAD}"
            )
            return False

        frame, crc = self._build_frame(cmd, payload)

        # Send frame
        try:
            self.serial.write(frame)
            msg = f"Sent frame: CMD=0x{cmd:02X} LEN={len(payload)}"
            msg += f" CRC=0x{crc:02X}"
            self._log(msg)
            return True
        except serial.SerialException as e:
            self._err(f"Failed to send frame: {e}")
            return False

    def receive_frame(self) -> tuple[int, bytes] | None:  # pragma: no cover
        """
        Receive a frame from the device.

        Returns:
            Tuple of (command, payload) or None if error/timeout
        """
        if not self.serial or not self.serial.is_open:
            return None

        state, pos, length = self._reset_receive_state()
        buffer = bytearray(self.FRAME_MAX_PAYLOAD + self.FRAME_MIN_LEN)

        while True:
            byte_data = self.serial.read(1)
            if not byte_data:
                self._err("Timeout waiting for frame")
                return None

            byte = byte_data[0]
            state, pos, length = self._advance_receive_state(
                state, pos, length, byte, buffer
            )

            if state != self.STATE_FRAME or not self._frame_complete(
                length, pos
            ):
                continue

            parsed = self._parse_received_frame(bytes(buffer[:pos]))
            if parsed is None:
                state, pos, length = self._reset_receive_state()
                continue

            return parsed

    def ping(self) -> bool:  # pragma: no cover
        """
        Send PING command to establish connection.

        Returns:
            True if device responds with PONG, False otherwise
        """
        success_message = (
            "Device responded with PONG - connection established!"
        )
        return self._ping_with_messages(
            start_message="\nPinging device...",
            success_message=success_message,
            failure_message="No PONG response from device",
        )

    def get_io_list(self) -> list[int]:  # pragma: no cover
        """
        Get list of available IO objects.

        Returns:
            List of object IDs, or empty list on error
        """
        self._log("\nGetting available IO objects...")
        if not self.send_frame(self.CMD_LIST_IOS):
            return []

        frame_data = self.receive_frame()
        if not frame_data:
            self._err("No response from device")
            return []

        cmd, payload = frame_data
        if cmd != self.CMD_LIST_IOS:
            self._err(f"Unexpected response: CMD=0x{cmd:02X}")
            return []

        if len(payload) < 2:
            self._err("Invalid response length")
            return []

        return self._parse_io_list_payload(payload, log_decoded_ids=True)

    def get_io_info(
        self, objid: int
    ) -> dict[str, Any] | None:  # pragma: no cover
        """
        Get information about a specific IO object.

        Args:
            objid: Object ID to query

        Returns:
            Dictionary with io_type, dimension, dtype or None on error
        """
        payload = struct.pack("<I", objid)

        if not self.send_frame(self.CMD_GET_INFO, payload):
            return None

        frame_data = self.receive_frame()
        if not frame_data:
            self._err("No response from device")
            return None

        cmd, response = frame_data
        if cmd != self.CMD_GET_INFO:
            self._err(f"Unexpected response to GET_INFO: CMD=0x{cmd:02X}")
            return None

        if len(response) < 3:
            self._err("Invalid GET_INFO response length")
            return None

        return self._build_io_info(
            objid,
            response,
            detailed_unknown=True,
            log_details=True,
        )

    def read_io(self, objid: int) -> bytes | None:  # pragma: no cover
        """
        Read data from an IO object.

        Args:
            objid: Object ID to read from

        Returns:
            Data bytes or None on error
        """
        frame = self._exchange_objid(self.CMD_GET_IO, objid)
        if frame is None:
            return None

        cmd, data = frame
        if cmd != self.CMD_GET_IO:
            if cmd == self.CMD_ERROR:
                self._err(f"Error reading IO 0x{objid:08X}")
            else:
                self._err(f"Unexpected response to GET_IO: CMD=0x{cmd:02X}")
            return None

        return data

    def write_io(self, objid: int, data: bytes) -> bool:  # pragma: no cover
        """
        Write data to an IO object.

        Args:
            objid: Object ID to write to
            data: Data bytes to write

        Returns:
            True if successful, False otherwise
        """
        if not isinstance(data, bytes):
            self._err("Data must be bytes")
            return False

        frame_data = self._exchange_write(self.CMD_SET_IO, objid, data)
        if not frame_data:
            self._err("No response from device")
            return False

        cmd, response = frame_data
        if cmd != self.CMD_SET_IO:
            if cmd == self.CMD_ERROR:
                self._err(f"Error writing IO 0x{objid:08X}")
            else:
                self._err(f"Unexpected response to SET_IO: CMD=0x{cmd:02X}")
            return False

        # Parse response: [status(1B)]
        if len(response) < 1:
            self._err("Invalid SET_IO response length")
            return False

        status = response[0]
        if status == self.STATUS_OK:
            self._log(
                f"Successfully wrote {len(data)} bytes to IO 0x{objid:08X}"
            )
            return True
        else:
            status_names = {
                self.STATUS_INVALID_CMD: "INVALID_CMD",
                self.STATUS_INVALID_OBJ: "INVALID_OBJ",
                self.STATUS_INVALID_CFG: "INVALID_CFG",
                self.STATUS_READ_ONLY: "READ_ONLY",
                self.STATUS_WRITE_ONLY: "WRITE_ONLY",
                self.STATUS_INVALID_FORMAT: "INVALID_FORMAT",
                self.STATUS_ERROR: "ERROR",
            }
            status_str = status_names.get(status, f"UNKNOWN(0x{status:02X})")
            self._err(f"Write failed with status: {status_str}")
            return False

    def discover_all_ios(
        self,
        *,
        read_values: bool = False,
    ) -> dict[int, dict[str, Any]]:  # pragma: no cover
        """
        Discover all IO objects and optionally read their current values.

        Returns:
            Dictionary with IO object data
        """
        self._log("\n=== Discovering all IO objects ===")

        # Get IO list
        if not self.get_io_list():
            self._err("Failed to get IO list")
            return {}

        print(f"\nDiscovered IOs ({len(self.io_list)}):")
        for objid in self.io_list:
            print(f"  {self.decode_object_id(objid)}")

        def _log_data(info: dict[str, Any], data: bytes) -> None:
            if self.verbose:
                prefix = "  Data: "
                for line in self._wrap_hex(info["data"], prefix, max_line=80):
                    print(line)
                print(f"{' ' * len(prefix)}({len(data)} bytes)")

        return self._collect_io_snapshot(
            set_none_for_write_only=True,
            set_none_for_failed_read=True,
            read_values=read_values,
            fetch_info=read_values,
            on_data=_log_data,
        )

    def read_io_seek_chunk(
        self,
        objid: int,
        offset: int,
    ) -> tuple[int, bytes] | None:  # pragma: no cover
        """
        Read one chunk from a seekable IO at a given byte offset.

        Sends CMD_GET_IO_SEEK with payload [objid:4][offset:4] and parses
        the response [objid:4][total_size:4][data:N].

        :param objid: Object ID of the seekable IO.
        :param offset: Byte offset into the IO data.
        :return: Tuple of (total_size, chunk_data) or None on error.
        """
        payload = struct.pack("<II", objid, offset)

        if not self.send_frame(self.CMD_GET_IO_SEEK, payload):
            return None

        frame_data = self.receive_frame()
        if not frame_data:
            self._err("No response from device")
            return None

        cmd, response = frame_data
        if cmd != self.CMD_GET_IO_SEEK:
            if cmd == self.CMD_ERROR and len(response) >= 1:
                status = response[0]
                status_names = {
                    self.STATUS_INVALID_FORMAT: "INVALID_FORMAT",
                    self.STATUS_INVALID_OBJ: "INVALID_OBJ",
                    self.STATUS_ERROR: "ERROR",
                }
                status_str = status_names.get(status, f"0x{status:02X}")
                self._err(
                    f"GET_IO_SEEK error for 0x{objid:08X}"
                    f" at offset={offset}: {status_str}"
                )
            else:
                self._err(
                    f"Unexpected response to GET_IO_SEEK: CMD=0x{cmd:02X}"
                )
            return None

        if len(response) < 8:
            self._err(f"GET_IO_SEEK response too short: {len(response)} bytes")
            return None

        resp_objid = struct.unpack("<I", response[0:4])[0]
        total_size = struct.unpack("<I", response[4:8])[0]
        chunk_data = bytes(response[8:])

        if resp_objid != objid:
            self._err(
                f"GET_IO_SEEK objid mismatch:"
                f" expected 0x{objid:08X} got 0x{resp_objid:08X}"
            )
            return None

        self._log(
            f"  GET_IO_SEEK 0x{objid:08X}:"
            f" offset={offset} total={total_size} chunk={len(chunk_data)}"
        )
        return (total_size, chunk_data)

    def read_io_seek(self, objid: int) -> bytes | None:  # pragma: no cover
        """
        Read all data from a seekable IO via chunked CMD_GET_IO_SEEK requests.

        Drives the request loop with increasing offsets until the complete
        data is reassembled based on total_size from the first response.

        :param objid: Object ID of the seekable IO.
        :return: Complete data as bytes, or None on error.
        """
        data = self._read_io_seek_all(
            objid,
            empty_chunk_error=("GET_IO_SEEK: empty chunk at offset={offset}"),
        )
        if data is None:
            return None
        return data

    def write_io_seek(
        self, objid: int, offset: int, data: bytes
    ) -> bool:  # pragma: no cover
        """
        Write one chunk to a seekable IO at a given byte offset.

        Sends CMD_SET_IO_SEEK with payload [objid:4][offset:4][data:N] and
        expects a 1-byte status response payload.

        :param objid: Object ID of the seekable IO.
        :param offset: Byte offset into IO data.
        :param data: Chunk payload bytes.
        :return: True on success, False on error.
        """
        cmd: int
        response: bytes
        frame_data: tuple[int, bytes] | None
        status: int
        status_names: dict[int, str]
        status_str: str
        payload: bytes

        if not isinstance(data, bytes):
            self._err("Data must be bytes")
            return False

        payload = struct.pack("<II", objid, offset) + data
        if not self.send_frame(self.CMD_SET_IO_SEEK, payload):
            return False

        frame_data = self.receive_frame()
        if not frame_data:
            self._err("No response from device")
            return False

        cmd, response = frame_data
        if cmd != self.CMD_SET_IO_SEEK:
            if cmd == self.CMD_ERROR:
                self._err(
                    f"SET_IO_SEEK error for 0x{objid:08X} at offset={offset}"
                )
            else:
                self._err(
                    f"Unexpected response to SET_IO_SEEK: CMD=0x{cmd:02X}"
                )
            return False

        if len(response) < 1:
            self._err("Invalid SET_IO_SEEK response length")
            return False

        status = response[0]
        if status == self.STATUS_OK:
            return True

        status_names = {
            self.STATUS_INVALID_CMD: "INVALID_CMD",
            self.STATUS_INVALID_OBJ: "INVALID_OBJ",
            self.STATUS_INVALID_CFG: "INVALID_CFG",
            self.STATUS_READ_ONLY: "READ_ONLY",
            self.STATUS_WRITE_ONLY: "WRITE_ONLY",
            self.STATUS_INVALID_FORMAT: "INVALID_FORMAT",
            self.STATUS_ERROR: "ERROR",
        }
        status_str = status_names.get(status, f"UNKNOWN(0x{status:02X})")
        self._err(f"SET_IO_SEEK failed with status: {status_str}")
        return False
