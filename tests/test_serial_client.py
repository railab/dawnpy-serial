#!/usr/bin/env python3
# tools/dawnpy/tests/test_serial_client.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for the serial client functionality.

Tests connection management, IO operations, and device discovery.
"""

from unittest.mock import MagicMock, patch

import pytest
import serial

from dawnpy_serial.client import SerialClient
from dawnpy_serial.serial import DawnSerialProtocol


@pytest.fixture
def mock_serial():
    """Fixture to mock serial.Serial."""
    with patch("dawnpy_serial.serial.serial.Serial") as mock:
        yield mock


@pytest.fixture
def client(mock_serial):
    """Fixture to create a DawnSerialProtocol client with mocked serial."""
    return DawnSerialProtocol("/dev/ttyUSB0")


@pytest.fixture
def serial_client(mock_serial):
    """Fixture to create a SerialClient with mocked serial."""
    return SerialClient("/dev/ttyUSB0")


class TestConnect:
    """Tests for connection management."""

    def test_connect_success(self, client, mock_serial):
        """Test successful connection."""
        mock_serial.return_value.is_open = True
        result = client.connect()
        assert result is True

    def test_disconnect(self, client, mock_serial):
        """Test disconnection."""
        client.connect()
        client.disconnect()
        mock_serial.return_value.close.assert_called()


class TestPing:
    """Tests for ping command."""

    def test_ping_send_fails(self, client, mock_serial):
        """Test ping when send fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=False)

        result = client.ping()
        assert result is False


class TestGetIOList:
    """Tests for get_io_list command."""

    def test_get_io_list_success(self, client, mock_serial):
        """Test successful IO list retrieval."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=True)
        # Mock response with 2 IO objects
        payload = b"\x02\x00\x01\x00\x00\x02\x00\x00"
        client.receive_frame = MagicMock(return_value=(0x21, payload))

        result = client.get_io_list()
        assert isinstance(result, list)

    def test_get_io_list_empty(self, client, mock_serial):
        """Test IO list with no objects."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=True)
        # Mock response with 0 IO objects
        payload = b"\x00"
        client.receive_frame = MagicMock(return_value=(0x21, payload))

        result = client.get_io_list()
        assert result == []

    def test_get_io_list_send_fails(self, client, mock_serial):
        """Test IO list when send fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=False)

        result = client.get_io_list()
        assert result == []


class TestReadIO:
    """Tests for read IO operations."""

    def test_read_io_send_fails(self, client, mock_serial):
        """Test read IO when send fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=False)

        result = client.read_io(0x40A10001)
        assert result is None


class TestWriteIO:
    """Tests for write IO operations."""

    def test_write_io_send_fails(self, client, mock_serial):
        """Test write IO when send fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=False)

        result = client.write_io(0x40A10001, b"\x42")
        assert result is False


class TestGetIOInfo:
    """Tests for get IO info."""

    def test_get_io_info_send_fails(self, client, mock_serial):
        """Test get IO info when send fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.send_frame = MagicMock(return_value=False)

        result = client.get_io_info(0x40A10001)
        assert result is None


class TestDiscoverAllIOs:
    """Tests for device discovery."""

    def test_discover_all_ios_success(self, client, mock_serial):
        """Test successful device discovery."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.connect = MagicMock(return_value=True)
        client.ping = MagicMock(return_value=True)
        client.get_io_list = MagicMock(return_value=[0x40A10001])
        client.get_io_info = MagicMock(
            return_value={"io_type": 1, "io_type_str": "IO_READ_WRITE"}
        )

        result = client.discover_all_ios()
        assert isinstance(result, dict)

    def test_discover_all_ios_empty(self, client, mock_serial):
        """Test discovery with no IOs."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.connect = MagicMock(return_value=True)
        client.ping = MagicMock(return_value=True)
        client.get_io_list = MagicMock(return_value=[])

        result = client.discover_all_ios()
        assert result == {}


class TestPackData:
    """Tests for data packing by dtype."""

    def test_pack_uint8(self, client):
        """Test packing uint8."""
        result = client.pack_data_by_dtype(1, 42)
        assert result == b"\x2a"

    def test_pack_invalid_dtype(self, client):
        """Test packing with invalid dtype."""
        result = client.pack_data_by_dtype(999, 42)
        assert result is None


class TestDecodeObjectID:
    """Tests for object ID decoding."""

    def test_decode_object_id(self, client):
        """Test object ID decoding."""
        result = client.decode_object_id(0x40A10001)
        assert isinstance(result, str)
        assert "0x" in result

    def test_decode_zero_objid(self, client):
        """Test decoding zero object ID."""
        result = client.decode_object_id(0x00000000)
        assert isinstance(result, str)


class TestParseObjectID:
    """Tests for object ID parsing."""

    def test_parse_single_objid_hex(self, serial_client):
        """Test parsing single object ID in hex."""
        result = serial_client.parse_object_id("0x40A10001")
        assert result == 0x40A10001

    def test_parse_single_objid_decimal(self, serial_client):
        """Test parsing single object ID in decimal as hex."""
        # Note: parse_object_id treats all input as hex, even decimal strings
        result = serial_client.parse_object_id("1084293121")
        assert result is not None
        assert isinstance(result, int)

    def test_parse_objid_invalid(self, serial_client):
        """Test parsing invalid object ID."""
        result = serial_client.parse_object_id("invalid")
        assert result is None

    def test_parse_multiple_objids(self, serial_client):
        """Test parsing multiple object IDs."""
        result = serial_client.parse_object_ids("0x40A10001,0x40A10002")
        assert result is not None
        assert len(result) == 2
        assert 0x40A10001 in result
        assert 0x40A10002 in result

    def test_parse_objids_empty(self, serial_client):
        """Test parsing empty object ID list."""
        result = serial_client.parse_object_ids("")
        assert result is None or result == []

    def test_parse_objids_invalid_format(self, serial_client):
        """Test parsing invalid format."""
        result = serial_client.parse_object_ids("invalid,0x40A10001")
        assert result is None or (
            isinstance(result, list) and len(result) <= 2
        )


class TestPort:
    """Tests for port property."""

    def test_port_property(self, client):
        """Test port property."""
        assert client.port == "/dev/ttyUSB0"


class TestSerialClientMethods:
    """Tests for SerialClient helper methods."""

    def test_read_io_value(self, serial_client, mock_serial):
        """Test reading IO value."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.get_io_info = MagicMock(
            return_value={"io_type": 1, "io_type_str": "IO_READ"}
        )
        serial_client.client.read_io = MagicMock(return_value=b"\x42")

        serial_client.read_io_value(0x40A10001)

    def test_write_io_value(self, serial_client, mock_serial):
        """Test writing IO value."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 2,
                "io_type_str": "IO_WRITE",
                "dtype": 1,
            }
        )
        serial_client.client.write_io = MagicMock(return_value=True)

        serial_client.write_io_value(0x40A10001, 42)

    def test_write_io_value_readonly(self, serial_client, mock_serial):
        """Test writing to read-only IO."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.get_io_info = MagicMock(
            return_value={"io_type": 1, "io_type_str": "IO_READ_ONLY"}
        )
        serial_client.client.IO_TYPE_READ_ONLY = 1

        serial_client.write_io_value(0x40A10001, 42)


class TestFrameBuilding:
    """Tests for frame building and sending."""

    def test_send_frame_basic(self, client, mock_serial):
        """Test sending a basic frame."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        client.connect()
        result = client.send_frame(0x00)
        assert isinstance(result, bool)

    def test_calculate_crc_empty(self, client):
        """Test CRC calculation with empty data."""
        result = client.calculate_crc(b"")
        assert result == 0xFFFF

    def test_calculate_crc_single_byte(self, client):
        """Test CRC with single byte."""
        result = client.calculate_crc(b"\x42")
        assert result == 0x8976

    def test_calculate_crc_multiple_bytes(self, client):
        """Test CRC with multiple bytes."""
        result = client.calculate_crc(b"\x01\x02\x03")
        assert result == 0xADAD


class TestDataPacking:
    """Tests for data packing utilities."""

    def test_pack_uint8_zero(self, client):
        """Test packing uint8 zero."""
        result = client.pack_data_by_dtype(1, 0)
        assert result == b"\x00"

    def test_pack_uint8_max(self, client):
        """Test packing uint8 max value."""
        result = client.pack_data_by_dtype(1, 255)
        assert result == b"\xff"


class TestSerialClientHelpers:
    """Tests for SerialClient utility methods."""

    def test_serial_client_init(self, serial_client):
        """Test SerialClient initialization."""
        assert serial_client.port == "/dev/ttyUSB0"
        assert serial_client.connected is False
        assert serial_client.discovered_ios == {}

    def test_perform_discovery_success(self, serial_client, mock_serial):
        """Test successful device discovery."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.ping = MagicMock(return_value=True)
        serial_client.client.discover_all_ios = MagicMock(
            return_value={0x40A10001: {"io_type": 1}}
        )

        result = serial_client.perform_discovery()
        assert result is True
        assert len(serial_client.discovered_ios) > 0

    def test_perform_discovery_connect_fails(self, serial_client, mock_serial):
        """Test discovery when connect fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = False

        serial_client.client.connect = MagicMock(return_value=False)

        result = serial_client.perform_discovery()
        assert result is False

    def test_perform_discovery_ping_fails(self, serial_client, mock_serial):
        """Test discovery when ping fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.ping = MagicMock(return_value=False)

        result = serial_client.perform_discovery()
        assert result is False


class TestConnectionMethods:
    """Tests for connection methods."""

    def test_connect_establishes_connection(self, serial_client, mock_serial):
        """Test connect method."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.ping = MagicMock(return_value=True)

        result = serial_client.connect()
        assert result is True
        assert serial_client.connected is True

    def test_connect_fails_when_client_fails(self, serial_client, mock_serial):
        """Test connect fails when client fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = False

        serial_client.client.connect = MagicMock(return_value=False)

        result = serial_client.connect()
        assert result is False

    def test_disconnect_closes_connection(self, serial_client, mock_serial):
        """Test disconnect method."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.disconnect = MagicMock()

        serial_client.disconnect()
        assert serial_client.connected is False

    def test_disconnect_when_not_connected(self, serial_client):
        """Test disconnect when not connected."""
        serial_client.connected = False
        serial_client.disconnect()
        # Should not raise any error


class TestParsingHelpers:
    """Tests for parsing helper methods."""

    def test_parse_object_id_hex_with_0x(self, serial_client):
        """Test parsing hex object ID with 0x prefix."""
        result = serial_client.parse_object_id("0x40A10001")
        assert result == 0x40A10001

    def test_parse_object_id_hex_without_prefix(self, serial_client):
        """Test parsing hex without prefix."""
        result = serial_client.parse_object_id("40A10001")
        assert result == 0x40A10001

    def test_parse_object_id_invalid_format(self, serial_client):
        """Test parsing invalid format."""
        result = serial_client.parse_object_id("not_a_hex")
        assert result is None

    def test_parse_multiple_objids_single(self, serial_client):
        """Test parsing single object ID from list."""
        result = serial_client.parse_object_ids("0x40A10001")
        assert result is not None
        assert len(result) >= 1
        assert 0x40A10001 in result

    def test_parse_multiple_objids_list(self, serial_client):
        """Test parsing multiple object IDs."""
        result = serial_client.parse_object_ids("0x40A10001,0x40A10002")
        assert result is not None
        assert len(result) >= 2

    def test_parse_multiple_objids_with_spaces(self, serial_client):
        """Test parsing with spaces."""
        result = serial_client.parse_object_ids("0x40A10001 , 0x40A10002")
        assert result is not None
        assert isinstance(result, list)

    def test_parse_multiple_objids_invalid(self, serial_client):
        """Test parsing with invalid ID."""
        result = serial_client.parse_object_ids("invalid")
        assert result is None or isinstance(result, list)


class TestIOOperations:
    """Tests for IO read/write operations."""

    def test_read_io_value_not_connected(self, serial_client):
        """Test reading IO when not connected."""
        serial_client.connected = False
        serial_client.read_io_value(0x40A10001)

    def test_read_io_value_connected(self, serial_client, mock_serial):
        """Test reading IO when connected."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 1,
                "io_type_str": "READ",
                "dtype": 1,
                "dimension": 1,
            }
        )
        serial_client.client.read_io = MagicMock(return_value=b"\x42")

        serial_client.read_io_value(0x40A10001)

    def test_read_io_value_no_info(self, serial_client, mock_serial):
        """Test reading IO when info fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(return_value=None)

        serial_client.read_io_value(0x40A10001)

    def test_write_io_value_not_connected(self, serial_client):
        """Test writing IO when not connected."""
        serial_client.connected = False
        serial_client.write_io_value(0x40A10001, 42)

    def test_write_io_value_connected(self, serial_client, mock_serial):
        """Test writing IO when connected."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={"io_type": 2, "io_type_str": "WRITE", "dtype": 1}
        )
        serial_client.client.pack_data_by_dtype = MagicMock(
            return_value=b"\x2a"
        )
        serial_client.client.write_io = MagicMock(return_value=True)
        serial_client.client.read_io = MagicMock(return_value=b"\x2a")

        serial_client.write_io_value(0x40A10001, 42)

    def test_write_io_value_read_only(self, serial_client, mock_serial):
        """Test writing to read-only IO."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 1,
                "io_type_str": "READ",
                "dtype": 1,
                "dimension": 1,
            }
        )

        serial_client.write_io_value(0x40A10001, 42)

    def test_write_io_value_pack_fails(self, serial_client, mock_serial):
        """Test writing when pack fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 2,
                "io_type_str": "WRITE",
                "dtype": 1,
                "dimension": 1,
            }
        )
        serial_client.client.pack_data_by_dtype = MagicMock(return_value=None)

        serial_client.write_io_value(0x40A10001, 42)

    def test_write_io_value_write_fails(self, serial_client, mock_serial):
        """Test writing when write operation fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 2,
                "io_type_str": "WRITE",
                "dtype": 1,
                "dimension": 1,
            }
        )
        serial_client.client.pack_data_by_dtype = MagicMock(
            return_value=b"\x2a"
        )
        serial_client.client.write_io = MagicMock(return_value=False)

        serial_client.write_io_value(0x40A10001, 42)

    def test_read_io_value_various_lengths(self, serial_client, mock_serial):
        """Test reading various data lengths."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        info = {
            "io_type": 1,
            "io_type_str": "READ",
            "dtype": 1,
            "dimension": 1,
        }

        # Test 2-byte read
        serial_client.client.get_io_info = MagicMock(return_value=info)
        serial_client.client.read_io = MagicMock(return_value=b"\x01\x02")
        serial_client.read_io_value(0x40A10001)

        # Test 4-byte read
        serial_client.client.read_io = MagicMock(
            return_value=b"\x01\x02\x03\x04"
        )
        serial_client.read_io_value(0x40A10001)

    def test_parse_object_id_with_spaces(self, serial_client):
        """Test parsing object ID with leading/trailing spaces."""
        result = serial_client.parse_object_id("  0x40A10001  ")
        assert result == 0x40A10001

    def test_parse_object_ids_invalid_in_list(self, serial_client):
        """Test parsing when one ID in list is invalid."""
        result = serial_client.parse_object_ids("0x40A10001,invalid")
        assert result is None

    def test_parse_object_ids_empty_string(self, serial_client):
        """Test parsing empty string."""
        result = serial_client.parse_object_ids("")
        assert result is None

    def test_parse_object_ids_with_spaces(self, serial_client):
        """Test parsing with extra spaces."""
        result = serial_client.parse_object_ids(
            "  0x40A10001  ,  0x40A10002  "
        )
        assert result is not None
        assert len(result) == 2

    def test_perform_discovery_ping_fails(self, serial_client, mock_serial):
        """Test discovery when ping fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.ping = MagicMock(return_value=False)

        result = serial_client.perform_discovery()
        assert result is False

    def test_perform_discovery_connect_fails(self, serial_client, mock_serial):
        """Test discovery when connect fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=False)

        result = serial_client.perform_discovery()
        assert result is False

    def test_perform_discovery_discover_fails(
        self, serial_client, mock_serial
    ):
        """Test discovery when discover_all_ios fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.ping = MagicMock(return_value=True)
        serial_client.client.discover_all_ios = MagicMock(return_value={})

        result = serial_client.perform_discovery()
        assert result is False

    def test_connect_failure(self, serial_client, mock_serial):
        """Test connection failure."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = False

        serial_client.client.connect = MagicMock(return_value=False)

        result = serial_client.connect()
        assert result is False

    def test_disconnect_when_not_connected(self, serial_client):
        """Test disconnect when not connected."""
        serial_client.connected = False
        serial_client.disconnect()
        assert serial_client.connected is False

    def test_read_io_value_verify_readback_none(
        self, serial_client, mock_serial
    ):
        """Test read verification when readback is None."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 1,
                "io_type_str": "READ",
                "dtype": 1,
                "dimension": 1,
            }
        )
        serial_client.client.read_io = MagicMock(return_value=None)

        serial_client.read_io_value(0x40A10001)


class TestDiscoveryMethod:
    """Tests for discovery method."""

    def test_discovery_not_connected(self, serial_client):
        """Test discovery when not connected."""
        serial_client.connected = False
        serial_client.discovery()

    def test_discovery_connected_with_data(self, serial_client, mock_serial):
        """Test discovery when connected with IO data."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.discover_all_ios = MagicMock(
            return_value={
                0x40A10001: {
                    "io_type_str": "READ",
                    "dimension": 1,
                    "dtype": 1,
                    "data": "0x42",
                    "data_bytes": [0x42],
                }
            }
        )

        serial_client.discovery()

    def test_discovery_connected_no_data(self, serial_client, mock_serial):
        """Test discovery when connected but no IOs found."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.discover_all_ios = MagicMock(return_value={})

        serial_client.discovery()


class TestInitialization:
    """Tests for client initialization."""

    def test_serial_client_initialization(self):
        """Test SerialClient initialization."""
        client = SerialClient("/dev/ttyUSB0")
        assert client.port == "/dev/ttyUSB0"
        assert client.connected is False
        assert client.discovered_ios == {}


class TestParseObjectIdEdgeCases:
    """Additional edge case tests for object ID parsing."""

    def test_parse_object_id_uppercase_prefix(self, serial_client):
        """Test parsing with uppercase 0X prefix."""
        result = serial_client.parse_object_id("0X40A10001")
        assert result == 0x40A10001

    def test_parse_object_id_empty_string(self, serial_client):
        """Test parsing empty string."""
        result = serial_client.parse_object_id("")
        assert result is None

    def test_parse_object_id_whitespace_only(self, serial_client):
        """Test parsing whitespace only."""
        result = serial_client.parse_object_id("   ")
        assert result is None

    def test_parse_multiple_objids_single_with_spaces(self, serial_client):
        """Test parsing single ID with surrounding spaces."""
        result = serial_client.parse_object_ids("  0x40A10001  ")
        assert result is not None
        assert len(result) == 1
        assert 0x40A10001 in result

    def test_parse_multiple_objids_mixed_case_prefix(self, serial_client):
        """Test parsing with mixed case prefix."""
        result = serial_client.parse_object_ids("0X40A10001,0x40A10002")
        assert result is not None
        assert len(result) == 2


class TestPerformDiscoveryEdgeCases:
    """Additional edge case tests for discovery."""

    def test_perform_discovery_caches_result(self, serial_client, mock_serial):
        """Test that perform_discovery caches the results."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.client.connect = MagicMock(return_value=True)
        serial_client.client.ping = MagicMock(return_value=True)
        test_ios = {
            0x40A10001: {"io_type_str": "READ", "dimension": 1, "dtype": 1}
        }
        serial_client.client.discover_all_ios = MagicMock(
            return_value=test_ios
        )

        result = serial_client.perform_discovery()
        assert result is True
        assert serial_client.discovered_ios == test_ios


class TestReadIOValueEdgeCases:
    """Additional edge case tests for read_io_value."""

    def test_read_io_value_8byte_data(self, serial_client, mock_serial):
        """Test reading 8-byte data."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 1,
                "io_type_str": "READ",
                "dtype": 1,
                "dimension": 1,
            }
        )
        serial_client.client.read_io = MagicMock(
            return_value=b"\x01\x02\x03\x04\x05\x06\x07\x08"
        )

        serial_client.read_io_value(0x40A10001)

    def test_read_io_value_block_dtype_uses_seek(self, serial_client):
        """Block dtype object IDs should use seek read path automatically."""
        serial_client.connected = True
        serial_client.read_seekable_io = MagicMock()
        serial_client.client.get_io_info = MagicMock()
        serial_client.client.read_io = MagicMock()

        serial_client.read_io_value(0x400F0001)

        serial_client.read_seekable_io.assert_called_once_with(0x400F0001)
        serial_client.client.get_io_info.assert_not_called()
        serial_client.client.read_io.assert_not_called()


class TestSerialProtocolErrorHandling:
    """Tests for error handling in serial protocol."""

    def test_protocol_connection_failure(self, client, mock_serial):
        """Test serial connection exception handling."""
        mock_serial.side_effect = serial.SerialException("Connection failed")
        result = client.connect()
        assert result is False

    def test_decode_object_id_exception(self, client):
        """Test decode_object_id with invalid decoder."""
        client.objid_decoder = None
        result = client.decode_object_id(0x40A10001)
        assert result == "0x40A10001"

    def test_pack_data_invalid_dtype(self, client):
        """Test packing data with invalid dtype."""
        result = client.pack_data_by_dtype(999, 42)
        assert result is None

    def test_pack_data_struct_error(self, client):
        """Test packing data that causes struct error."""
        # Setup objid_decoder mock
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {1: {"type": "int8"}}

        # Try to pack a value that's out of range
        result = client.pack_data_by_dtype(1, 300)  # int8 max is 127
        assert result is None

    def test_decode_object_id_with_decoder_exception(self, client):
        """Test decode_object_id when decoder raises exception."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.decode.side_effect = Exception("Decode error")
        result = client.decode_object_id(0x40A10001)
        assert result == "0x40A10001"

    def test_pack_data_char_string(self, client):
        """Test packing char/string data."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {14: {"type": "char"}}
        result = client.pack_data_by_dtype(14, "hello")
        assert result == b"hello"

    def test_pack_data_char_bytes(self, client):
        """Test packing bytes data for char type."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {14: {"type": "char"}}
        result = client.pack_data_by_dtype(14, b"hello")
        assert result == b"hello"

    def test_pack_data_char_invalid_type(self, client):
        """Test packing char data with invalid type."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {14: {"type": "char"}}
        result = client.pack_data_by_dtype(14, 123)  # Not string or bytes
        assert result is None

    def test_pack_data_no_decoder(self, client):
        """Test packing data when decoder is not available."""
        client.objid_decoder = None
        result = client.pack_data_by_dtype(1, 42)
        assert result is None

    def test_pack_data_multiple_values(self, client):
        """Test packing with multiple values (should fail)."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {1: {"type": "int8"}}
        result = client.pack_data_by_dtype(1, 42, 50)  # More than 1 value
        assert result is None

    def test_pack_data_float_int32(self, client):
        """Test packing float as int32."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {8: {"type": "float"}}
        result = client.pack_data_by_dtype(8, 3.14)
        assert result is not None
        assert len(result) == 4

    def test_pack_data_double_int64(self, client):
        """Test packing double as int64."""
        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {11: {"type": "double"}}
        result = client.pack_data_by_dtype(11, 3.14159)
        assert result is not None
        assert len(result) == 8

    def test_crc_calculation(self, client):
        """Test CRC calculation for frame validation."""
        data = b"\x10\x00"  # GET_IO command with no payload
        crc = client.calculate_crc(data)
        assert crc == 0x1E7C

    def test_crc_calculation_multiple_bytes(self, client):
        """Test CRC with multiple bytes."""
        data = b"\x01\x02\x03\x04"
        crc = client.calculate_crc(data)
        assert crc == 0x89C3


class TestParseObjectIdNormalization:
    """Tests for object ID normalization."""

    def test_parse_object_ids_normalizes_all_ids(self, serial_client):
        """Test that all object IDs are parsed correctly."""
        result = serial_client.parse_object_ids("0x100,0x200,0x300")
        assert result is not None
        assert len(result) == 3
        assert result == [0x100, 0x200, 0x300]


class TestWriteIOValueEdgeCases:
    """Additional edge case tests for write_io_value."""

    def test_write_io_value_no_info(self, serial_client, mock_serial):
        """Test writing when get_io_info fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(return_value=None)

        serial_client.write_io_value(0x40A10001, 42)

    def test_write_io_value_write_no_readback(
        self, serial_client, mock_serial
    ):
        """Test write when readback fails."""
        mock_instance = MagicMock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True

        serial_client.connected = True
        serial_client.client.get_io_info = MagicMock(
            return_value={
                "io_type": 2,
                "io_type_str": "WRITE",
                "dtype": 1,
                "dimension": 1,
            }
        )
        serial_client.client.pack_data_by_dtype = MagicMock(
            return_value=b"\x2a"
        )
        serial_client.client.write_io = MagicMock(return_value=True)
        serial_client.client.read_io = MagicMock(return_value=None)

        serial_client.write_io_value(0x40A10001, 42)
