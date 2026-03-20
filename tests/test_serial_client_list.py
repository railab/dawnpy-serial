#!/usr/bin/env python3
# tools/dawnpy/tests/test_serial_client_list.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for serial client list output."""

import struct

from dawnpy.objectid import ObjectIdDecoder

from dawnpy_serial.client import SerialClient


class FakeProto:
    """Minimal serial protocol stub for raw write tests."""

    IO_TYPE_READ_ONLY = 0x01

    def __init__(self):
        """Initialize stub."""
        self.objid_decoder = ObjectIdDecoder()
        self._written = None

    def get_io_info(self, _objid):
        """Return fixed IO info."""
        return {"io_type": 0x03, "dtype": 10}

    def write_io(self, _objid, data):
        """Store written data."""
        self._written = data
        return True

    def read_io(self, _objid):
        """Return stored data."""
        return self._written


def test_list_discovered_features_decodes(capsys):
    """List output includes decoded values."""
    client = SerialClient("/dev/null")
    data = struct.pack("<4f", 1.0, 2.0, 3.0, 4.0)
    client.discovered_ios = {
        0x4C8A0001: {
            "io_type_str": "Read-Write",
            "dimension": 4,
            "dtype": 10,
            "data": data.hex(),
            "data_bytes": list(data),
        }
    }

    client.list_discovered_features()
    out = capsys.readouterr().out

    assert "Data (decoded): [1.0, 2.0, 3.0, 4.0]" in out


def test_list_discovered_features_empty(capsys):
    """List output handles empty discovery."""
    client = SerialClient("/dev/null")
    client.discovered_ios = {}
    client.list_discovered_features()
    out = capsys.readouterr().out
    assert "No discovered IOs" in out


def test_list_discovered_features_invalid_bytes(capsys):
    """List output handles invalid byte data."""
    client = SerialClient("/dev/null")
    client.discovered_ios = {1: {"data": "00", "data_bytes": "bad"}}
    client.list_discovered_features()
    out = capsys.readouterr().out
    assert "decode failed" in out


def test_parse_hex_bytes():
    """Hex parsing accepts prefixes and rejects odd length."""
    assert SerialClient.parse_hex_bytes("0x0102") == b"\x01\x02"
    assert SerialClient.parse_hex_bytes("01_02") == b"\x01\x02"
    assert SerialClient.parse_hex_bytes("0x1") is None
    assert SerialClient.parse_hex_bytes("0xGG") is None


def test_write_io_raw_decodes(capsys):
    """Raw writes decode values on read-back."""
    client = SerialClient("/dev/null")
    client.connected = True
    client.client = FakeProto()
    client.write_io_raw(1, b"\x00\x00\x80\x3f")
    out = capsys.readouterr().out
    assert "1.0" in out


def test_write_io_raw_not_connected(capsys):
    """Raw write fails when not connected."""
    client = SerialClient("/dev/null")
    client.connected = False
    client.write_io_raw(1, b"\x00")
    out = capsys.readouterr().out
    assert "Not connected" in out


def test_write_io_raw_missing_info(capsys):
    """Raw write fails when info is missing."""

    class MissingInfo:
        IO_TYPE_READ_ONLY = 0x01

        def get_io_info(self, _objid):
            return None

    client = SerialClient("/dev/null")
    client.connected = True
    client.client = MissingInfo()
    client.write_io_raw(1, b"\x00")
    out = capsys.readouterr().out
    assert "Failed to get IO info" in out


def test_write_io_raw_read_only(capsys):
    """Raw write fails for read-only IOs."""

    class ReadOnly:
        IO_TYPE_READ_ONLY = 0x01

        def get_io_info(self, _objid):
            return {"io_type": self.IO_TYPE_READ_ONLY, "dtype": 10}

    client = SerialClient("/dev/null")
    client.connected = True
    client.client = ReadOnly()
    client.write_io_raw(1, b"\x00")
    out = capsys.readouterr().out
    assert "read-only" in out


def test_write_io_raw_write_failed(capsys):
    """Raw write reports protocol failure."""

    class WriteFail:
        IO_TYPE_READ_ONLY = 0x01

        def get_io_info(self, _objid):
            return {"io_type": 0x03, "dtype": 10}

        def write_io(self, _objid, _data):
            return False

    client = SerialClient("/dev/null")
    client.connected = True
    client.client = WriteFail()
    client.write_io_raw(1, b"\x00")
    out = capsys.readouterr().out
    assert "Write failed" in out
