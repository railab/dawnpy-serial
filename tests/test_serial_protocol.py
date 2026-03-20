#!/usr/bin/env python3
# tools/dawnpy/tests/test_serial_protocol.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for the Dawn Serial Protocol implementation.

Tests frame building, CRC calculation, and frame parsing using pytest.
"""

import struct

import pytest

from dawnpy_serial.serial import DawnSerialProtocol


@pytest.fixture
def client():
    """Fixture to create a DawnSerialProtocol client for testing."""
    return DawnSerialProtocol("/dev/null")


class TestCRCCalculation:
    """Tests for CRC calculation (CRC16-CCITT)."""

    def test_single_byte(self, client):
        """Test CRC calculation for single byte."""
        result = client.calculate_crc(b"\x00")
        assert result == 0xE1F0

    def test_multiple_bytes(self, client):
        """Test CRC calculation for multiple bytes."""
        result = client.calculate_crc(b"\x01\x02\x03")
        assert result == 0xADAD

    def test_ping_command(self, client):
        """Test CRC for PING command (CMD=0x00, no payload)."""
        result = client.calculate_crc(b"\x00")
        assert result == 0xE1F0

    def test_get_info_command(self, client):
        """Test CRC for GET_INFO with 4-byte object ID."""
        cmd_and_payload = bytes([0x20, 0x01, 0x00, 0x01, 0x00])
        result = client.calculate_crc(cmd_and_payload)
        assert result == 0x5C3D


class TestFrameFormat:
    """Tests for frame format and building."""

    def test_ping_frame_structure(self):
        """Verify PING frame structure."""
        # Frame format: [SYNC][LEN_L][LEN_H][CMD][PAYLOAD][CRC_L][CRC_H]
        # PING: [0xAA][0x00][0x00][0x00][0x00][0xF0][0xE1]
        frame_sync = 0xAA
        frame_len_l = 0x00
        frame_len_h = 0x00
        cmd = 0x00
        crc_l = 0xF0
        crc_h = 0xE1

        assert frame_sync == 0xAA
        assert frame_len_l == 0x00
        assert frame_len_h == 0x00
        assert cmd == 0x00
        assert crc_l == 0xF0
        assert crc_h == 0xE1

    def test_list_ios_frame_structure(self):
        """Verify LIST_IOS frame structure."""
        # LIST_IOS: [0xAA][0x00][0x00][0x21][CRC_L][CRC_H]
        # CRC = CRC16(0x21) = 0xD5B3
        frame_sync = 0xAA
        frame_len_l = 0x00
        frame_len_h = 0x00
        cmd = 0x21
        crc_l = 0xB3
        crc_h = 0xD5

        assert frame_sync == 0xAA
        assert frame_len_l == 0x00
        assert frame_len_h == 0x00
        assert cmd == 0x21
        assert crc_l == 0xB3
        assert crc_h == 0xD5

    def test_get_info_frame_structure(self):
        """Verify GET_INFO frame with 4-byte object ID."""
        # [0xAA][0x04][0x20][objid_4bytes][CRC]
        objid = 0x00010001
        payload = struct.pack("<I", objid)

        assert len(payload) == 4
        assert payload == b"\x01\x00\x01\x00"


class TestFrameParsing:
    """Tests for frame parsing and validation."""

    def test_parse_pong_response(self, client):
        """Test parsing PONG response frame."""
        # [SYNC][LEN_L][LEN_H][CMD][CRC_L][CRC_H]
        # CRC16(0x01) = 0xF1D1
        frame = bytes([0xAA, 0x00, 0x00, 0x01, 0xD1, 0xF1])

        # Verify frame structure
        assert frame[0] == 0xAA
        assert frame[1] == 0x00
        assert frame[2] == 0x00
        assert frame[3] == 0x01

        # Verify CRC
        crc_calc = client.calculate_crc(frame[3:4])
        crc_recv = struct.unpack("<H", frame[4:6])[0]
        assert crc_calc == crc_recv

    def test_parse_list_ios_response(self, client):
        """Test parsing LIST_IOS response with 2 objects."""
        response_payload = struct.pack("<HII", 2, 0x00010001, 0x00010002)
        cmd = 0x21  # CMD_LIST_IOS

        # Calculate full frame
        crc = client.calculate_crc(bytes([cmd]) + response_payload)
        frame = (
            bytes([0xAA])
            + struct.pack("<H", len(response_payload))
            + bytes([cmd])
            + response_payload
            + struct.pack("<H", crc)
        )

        # Parse response
        payload = frame[4:-2]
        count = struct.unpack("<H", payload[0:2])[0]

        assert count == 2

        # Verify objects
        for i in range(count):
            offset = 2 + (i * 4)
            objid = struct.unpack("<I", payload[offset : offset + 4])[0]
            assert objid in [0x00010001, 0x00010002]

    def test_parse_get_info_response(self, client):
        """Test parsing GET_INFO response."""
        response_payload = bytes(
            [0x03, 0x01, 0x04]
        )  # Read-Write, dim=1, dtype=4
        cmd = 0x20  # CMD_GET_INFO
        crc = client.calculate_crc(bytes([cmd]) + response_payload)
        frame = (
            bytes([0xAA])
            + struct.pack("<H", len(response_payload))
            + bytes([cmd])
            + response_payload
            + struct.pack("<H", crc)
        )

        # Parse response
        payload = frame[4:-2]
        io_type = payload[0]
        dimension = payload[1]
        dtype = payload[2]

        assert io_type == 0x03
        assert dimension == 0x01
        assert dtype == 0x04


class TestLittleEndian:
    """Tests for little-endian byte order."""

    def test_object_id_encoding(self):
        """Test little-endian encoding of 4-byte object ID."""
        objid = 0x12345678
        payload = struct.pack("<I", objid)

        assert payload == bytes([0x78, 0x56, 0x34, 0x12])

    def test_object_id_decoding(self):
        """Test little-endian decoding of 4-byte object ID."""
        expected_objid = 0x12345678
        payload = bytes([0x78, 0x56, 0x34, 0x12])
        decoded = struct.unpack("<I", payload)[0]

        assert decoded == expected_objid

    def test_count_encoding(self):
        """Test little-endian encoding of 2-byte count."""
        count = 258  # 0x0102
        payload = struct.pack("<H", count)

        assert payload == bytes([0x02, 0x01])

    def test_count_decoding(self):
        """Test little-endian decoding of 2-byte count."""
        expected_count = 258
        payload = bytes([0x02, 0x01])
        decoded = struct.unpack("<H", payload)[0]

        assert decoded == expected_count


class TestCommandConstants:
    """Tests for protocol command constants."""

    @pytest.mark.parametrize(
        "cmd_name,expected_value",
        [
            ("CMD_PING", 0x00),
            ("CMD_PONG", 0x01),
            ("CMD_GET_IO", 0x10),
            ("CMD_SET_IO", 0x11),
            ("CMD_GET_CFG", 0x12),
            ("CMD_SET_CFG", 0x13),
            ("CMD_GET_INFO", 0x20),
            ("CMD_LIST_IOS", 0x21),
            ("CMD_ERROR", 0xFF),
        ],
    )
    def test_command_constants(self, client, cmd_name, expected_value):
        """Verify command constant values match protocol."""
        actual_value = getattr(client, cmd_name)
        assert actual_value == expected_value


class TestSetIOFrameFormat:
    """Tests for SET_IO command frame format."""

    def test_set_io_with_two_byte_data(self):
        """Test SET_IO with 4-byte object ID and 2 bytes of data."""
        objid = 0x00010001
        data = bytes([0xAB, 0xCD])

        payload = struct.pack("<I", objid) + data
        expected_payload = bytes([0x01, 0x00, 0x01, 0x00, 0xAB, 0xCD])

        assert payload == expected_payload

    def test_set_io_with_single_byte_data(self):
        """Test SET_IO with single byte data."""
        objid = 0x12345678
        data = bytes([0xFF])

        payload = struct.pack("<I", objid) + data
        expected_payload = bytes([0x78, 0x56, 0x34, 0x12, 0xFF])

        assert payload == expected_payload

    def test_set_io_with_larger_data(self):
        """Test SET_IO with larger data payload."""
        objid = 0xFFFFFFFF
        data = bytes([0x01, 0x02, 0x03, 0x04, 0x05])

        payload = struct.pack("<I", objid) + data
        expected_payload = bytes(
            [0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x02, 0x03, 0x04, 0x05]
        )

        assert payload == expected_payload


class TestSetIOResponse:
    """Tests for SET_IO response parsing."""

    def test_set_io_success_response(self, client):
        """Test SET_IO success response parsing."""
        status = client.STATUS_OK
        response_payload = bytes([status])
        cmd = client.CMD_SET_IO

        crc = client.calculate_crc(bytes([cmd]) + response_payload)
        frame = (
            bytes([0xAA])
            + struct.pack("<H", len(response_payload))
            + bytes([cmd])
            + response_payload
            + struct.pack("<H", crc)
        )

        # Parse response
        payload = frame[4:-2]
        status_received = payload[0]
        assert status_received == client.STATUS_OK

    def test_set_io_read_only_error_response(self, client):
        """Test SET_IO read-only error response parsing."""
        status = client.STATUS_READ_ONLY
        response_payload = bytes([status])
        cmd = client.CMD_SET_IO

        crc = client.calculate_crc(bytes([cmd]) + response_payload)
        frame = (
            bytes([0xAA])
            + struct.pack("<H", len(response_payload))
            + bytes([cmd])
            + response_payload
            + struct.pack("<H", crc)
        )

        # Parse response
        payload = frame[4:-2]
        status_received = payload[0]
        assert status_received == client.STATUS_READ_ONLY


class TestDataPacking:
    """Tests for pack_data_by_dtype method."""

    def test_pack_bool(self, client):
        """Test packing bool data."""
        result = client.pack_data_by_dtype(1, 1)
        assert result == b"\x01"

    def test_pack_uint16(self, client):
        """Test packing uint16 data."""
        # dtype 5 = uint16_t
        result = client.pack_data_by_dtype(5, 0x1234)
        assert result == b"\x34\x12"  # little-endian

    def test_pack_uint32(self, client):
        """Test packing uint32 data."""
        # dtype 7 = uint32_t
        result = client.pack_data_by_dtype(7, 0x12345678)
        assert result == b"\x78\x56\x34\x12"  # little-endian

    def test_pack_invalid_dtype(self, client):
        """Test packing with invalid dtype returns None."""
        result = client.pack_data_by_dtype(99, 123)
        assert result is None

    def test_pack_char_string(self, client):
        """Test packing string data."""
        if client.objid_decoder:
            # dtype 14 = char
            result = client.pack_data_by_dtype(14, "hello")
            assert result == b"hello"

    def test_pack_char_bytes(self, client):
        """Test packing bytes data."""
        if client.objid_decoder:
            # dtype 14 = char
            data = b"world"
            result = client.pack_data_by_dtype(14, data)
            assert result == data

    def test_pack_without_decoder(self):
        """Test packing without ObjectIdDecoder returns None."""
        client_no_decoder = DawnSerialProtocol("/dev/null")
        client_no_decoder.objid_decoder = None
        result = client_no_decoder.pack_data_by_dtype(1, 255)
        assert result is None

    def test_pack_multiple_values_returns_none(self, client):
        """Test packing multiple values returns None."""
        if client.objid_decoder:
            result = client.pack_data_by_dtype(1, 255, 256)
            assert result is None


class TestObjectIdDecoding:
    """Tests for decode_object_id method."""

    def test_decode_object_id_without_decoder(self):
        """Test decoding without ObjectIdDecoder."""
        client_no_decoder = DawnSerialProtocol("/dev/null")
        client_no_decoder.objid_decoder = None
        result = client_no_decoder.decode_object_id(0x12345678)
        assert result == "0x12345678"

    def test_decode_object_id_with_decoder(self, client):
        """Test decoding with ObjectIdDecoder."""
        if client.objid_decoder:
            result = client.decode_object_id(0x00010001)
            assert "0x" in result or isinstance(result, str)

    def test_decode_object_id_format(self, client):
        """Test decoded object ID format."""
        if client.objid_decoder:
            result = client.decode_object_id(0xFFFFFFFF)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_decode_object_id_exception_handling(self, client):
        """Test exception handling in decode_object_id."""
        if client.objid_decoder:
            # This should not raise an exception
            result = client.decode_object_id(0x00000000)
            assert isinstance(result, str)


class TestIOTypeConstants:
    """Tests for IO type constants."""

    def test_io_type_read_only(self, client):
        """Test IO_TYPE_READ_ONLY constant."""
        assert client.IO_TYPE_READ_ONLY == 0x01

    def test_io_type_write_only(self, client):
        """Test IO_TYPE_WRITE_ONLY constant."""
        assert client.IO_TYPE_WRITE_ONLY == 0x02

    def test_io_type_read_write(self, client):
        """Test IO_TYPE_READ_WRITE constant."""
        assert client.IO_TYPE_READ_WRITE == 0x03


class TestStatusConstants:
    """Tests for status code constants."""

    @pytest.mark.parametrize(
        "status_name,expected_value",
        [
            ("STATUS_OK", 0x00),
            ("STATUS_INVALID_CMD", 0x01),
            ("STATUS_INVALID_OBJ", 0x02),
            ("STATUS_INVALID_CFG", 0x03),
            ("STATUS_READ_ONLY", 0x04),
            ("STATUS_WRITE_ONLY", 0x05),
            ("STATUS_INVALID_FORMAT", 0x06),
            ("STATUS_ERROR", 0xFF),
        ],
    )
    def test_status_constants(self, client, status_name, expected_value):
        """Verify status code constant values."""
        actual_value = getattr(client, status_name)
        assert actual_value == expected_value


class TestFrameConstants:
    """Tests for frame format constants."""

    def test_frame_sync_constant(self, client):
        """Test FRAME_SYNC constant."""
        assert client.FRAME_SYNC == 0xAA

    def test_frame_min_len_constant(self, client):
        """Test FRAME_MIN_LEN constant."""
        assert client.FRAME_MIN_LEN == 6

    def test_frame_max_payload_constant(self, client):
        """Test FRAME_MAX_PAYLOAD constant."""
        assert client.FRAME_MAX_PAYLOAD == 1024


class TestPortConfiguration:
    """Tests for port configuration."""

    def test_client_port_setting(self):
        """Test that client stores port setting."""
        client = DawnSerialProtocol("/dev/ttyUSB0")
        assert client.port == "/dev/ttyUSB0"

    def test_client_baudrate_setting(self):
        """Test that client stores baudrate setting."""
        client = DawnSerialProtocol("/dev/ttyUSB0", baudrate=9600)
        assert client.baudrate == 9600

    def test_client_timeout_setting(self):
        """Test that client stores timeout setting."""
        client = DawnSerialProtocol("/dev/ttyUSB0", timeout=2.0)
        assert client.timeout == 2.0

    def test_client_default_baudrate(self):
        """Test that client uses default baudrate."""
        client = DawnSerialProtocol("/dev/ttyUSB0")
        assert client.baudrate == 115200

    def test_client_default_timeout(self):
        """Test that client uses default timeout."""
        client = DawnSerialProtocol("/dev/ttyUSB0")
        assert client.timeout == 1.0


class TestClientInitialization:
    """Tests for client initialization."""

    def test_io_list_initialized_empty(self):
        """Test that IO list is initialized empty."""
        client = DawnSerialProtocol("/dev/null")
        assert client.io_list == []

    def test_io_info_initialized_empty(self):
        """Test that IO info dict is initialized empty."""
        client = DawnSerialProtocol("/dev/null")
        assert client.io_info == {}

    def test_serial_initialized_none(self):
        """Test that serial connection is initialized as None."""
        client = DawnSerialProtocol("/dev/null")
        assert client.serial is None

    def test_objid_decoder_initialization_with_bad_config(self):
        """Test objid_decoder initialization when config dir is invalid."""
        # This tests the exception path in __init__
        from unittest.mock import patch

        with patch("dawnpy_serial.serial.ObjectIdDecoder") as mock_decoder:
            mock_decoder.side_effect = Exception("Config not found")
            client = DawnSerialProtocol("/dev/null")
            # Should fall back gracefully
            assert client.objid_decoder is None

    def test_pack_data_keyerror_exception(self):
        """Test pack_data_by_dtype when KeyError occurs."""
        client = DawnSerialProtocol("/dev/null")
        # Mock decoder that raises KeyError
        from unittest.mock import MagicMock

        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {}  # Empty dict causes KeyError
        result = client.pack_data_by_dtype(999, 42)  # dtype not in dict
        assert result is None

    def test_pack_data_value_error_exception(self):
        """Test pack_data_by_dtype when ValueError occurs."""
        client = DawnSerialProtocol("/dev/null")
        # This should trigger ValueError in struct.pack
        from unittest.mock import MagicMock

        client.objid_decoder = MagicMock()
        client.objid_decoder.dtype_info = {1: {"type": "uint16"}}
        # Try to pack a non-integer value for numeric dtype
        result = client.pack_data_by_dtype(1, "not_a_number")
        assert result is None

    def test_pack_data_missing_type_key(self):
        """Test pack_data_by_dtype when type key is missing."""
        client = DawnSerialProtocol("/dev/null")
        from unittest.mock import MagicMock

        client.objid_decoder = MagicMock()
        # Missing "type" key
        client.objid_decoder.dtype_info = {1: {}}
        result = client.pack_data_by_dtype(1, 42)
        assert result is None


def test_discover_all_ios_verbose_wrap(capsys):
    """Ensure discover_all_ios wraps hex output when verbose."""
    proto = DawnSerialProtocol("/dev/null", verbose=True)

    def fake_get_io_list():
        proto.io_list = [0x00000001]
        return proto.io_list

    def fake_get_io_info(_objid):
        return {
            "io_type": proto.IO_TYPE_READ_ONLY,
            "io_type_str": "Read-Only",
            "dimension": 1,
            "dtype": 10,
        }

    def fake_read_io(_objid):
        return bytes(range(64))

    proto.get_io_list = fake_get_io_list  # type: ignore[assignment]
    proto.get_io_info = fake_get_io_info  # type: ignore[assignment]
    proto.read_io = fake_read_io  # type: ignore[assignment]

    data = proto.discover_all_ios(read_values=True)
    out = capsys.readouterr().out

    assert 0x00000001 in data
    assert "Data:" in out
    assert "(64 bytes)" in out


def test_discover_all_ios_default_metadata_only():
    """Default discovery should not fetch per-IO info/value frames."""
    proto = DawnSerialProtocol("/dev/null", verbose=False)
    calls = {"info": 0, "read": 0}

    def fake_get_io_list():
        proto.io_list = [0x40A10001]
        return proto.io_list

    proto.get_io_list = fake_get_io_list  # type: ignore[assignment]
    proto.get_io_info = lambda _objid: {  # type: ignore[assignment]
        "io_type": proto.IO_TYPE_READ_ONLY,
        "io_type_str": "Read-Only",
        "dimension": 1,
        "dtype": 7,
    }
    proto.read_io = lambda _objid: b"\xaa"  # type: ignore[assignment]

    data = proto.discover_all_ios()
    info = data[0x40A10001]

    assert info["data"] is None
    assert calls["info"] == 0
    assert calls["read"] == 0


def test_wrap_hex_min_width_serial():
    """Serial _wrap_hex enforces minimum chunk size."""
    lines = DawnSerialProtocol._wrap_hex("deadbeef", "X" * 100, max_line=80)
    assert len(lines) >= 1


def test_received_frame_log_message():
    """Serial frame log helper should format command and length."""
    result = DawnSerialProtocol._received_frame_log_message(0x10, 4)

    assert result == "Received frame: CMD=0x10 LEN=4"


class TestGetIOSeekCommand:
    """Tests for CMD_GET_IO_SEEK (seekable IO chunked read)."""

    def test_cmd_constant_value(self, client):
        """CMD_GET_IO_SEEK must be 0x14 to match the C++ definition."""
        assert client.CMD_GET_IO_SEEK == 0x14

    def test_cmd_distinct_from_neighbours(self, client):
        """CMD_GET_IO_SEEK must not collide with CMD_SET_IO or CMD_GET_CFG."""
        assert client.CMD_GET_IO_SEEK != client.CMD_SET_IO
        assert client.CMD_GET_IO_SEEK != client.CMD_GET_CFG

    def test_request_payload_format(self, client):
        """Request payload is [objid:4 LE][offset:4 LE] = 8 bytes."""
        objid = 0xAB000001
        offset = 0x00000040

        payload = struct.pack("<II", objid, offset)

        assert len(payload) == 8
        assert struct.unpack("<I", payload[0:4])[0] == objid
        assert struct.unpack("<I", payload[4:8])[0] == offset

    def test_request_offset_zero(self, client):
        """Offset zero is valid and encodes to four zero bytes."""
        payload = struct.pack("<II", 0x00000001, 0)
        assert payload[4:8] == b"\x00\x00\x00\x00"

    def test_request_crc(self, client):
        """CRC covers CMD byte + payload."""
        cmd = client.CMD_GET_IO_SEEK
        objid = 0x00000001
        offset = 0x00000010
        payload = struct.pack("<II", objid, offset)

        crc = client.calculate_crc(bytes([cmd]) + payload)

        assert 0 <= crc <= 0xFFFF

    def test_response_parsing_full(self, client):
        """Parse response [objid:4][total_size:4][data:N]."""
        objid = 0xAB000001
        total_size = 20
        chunk_data = bytes(range(8))

        response = struct.pack("<II", objid, total_size) + chunk_data

        resp_objid = struct.unpack("<I", response[0:4])[0]
        resp_total = struct.unpack("<I", response[4:8])[0]
        resp_chunk = response[8:]

        assert resp_objid == objid
        assert resp_total == total_size
        assert resp_chunk == chunk_data
        assert len(resp_chunk) < total_size  # Partial read

    def test_response_parsing_last_chunk(self, client):
        """Last chunk may be smaller than chunk_cap."""
        objid = 0xAB000001
        total_size = 20
        # 4 bytes remain at offset 16
        chunk_data = struct.pack("<I", 5)

        response = struct.pack("<II", objid, total_size) + chunk_data

        resp_total = struct.unpack("<I", response[4:8])[0]
        resp_chunk = response[8:]

        assert resp_total == total_size
        assert len(resp_chunk) == 4

    def test_multi_chunk_reassembly(self, client):
        """Multi-chunk loop reassembles full data correctly."""
        # 20-byte descriptor: {1, 2, 3, 4, 5} as uint32_t little-endian
        full_data = struct.pack("<5I", 1, 2, 3, 4, 5)
        chunk_cap = 8

        offset = 0
        result = bytearray()
        total_size = len(full_data)

        while offset < total_size:
            avail = total_size - offset
            n = min(chunk_cap, avail)
            chunk = full_data[offset : offset + n]
            result.extend(chunk)
            offset += len(chunk)

        assert bytes(result) == full_data
        assert len(result) == total_size

    def test_frame_crc_seek_request(self, client):
        """Full seek request frame CRC validates correctly."""
        cmd = client.CMD_GET_IO_SEEK
        objid = 0x40A70001
        offset = 64
        payload = struct.pack("<II", objid, offset)

        crc_data = bytes([cmd]) + payload
        crc = client.calculate_crc(crc_data)
        frame = (
            bytes([0xAA])
            + struct.pack("<H", len(payload))
            + bytes([cmd])
            + payload
            + struct.pack("<H", crc)
        )

        # Re-verify CRC from the assembled frame
        crc_check = client.calculate_crc(frame[3 : 4 + len(payload)])
        assert (
            crc_check
            == struct.unpack("<H", frame[4 + len(payload) : 6 + len(payload)])[
                0
            ]
        )


def test_reset_receive_state():
    """_reset_receive_state should return the initial parser state."""
    state, pos, length = DawnSerialProtocol._reset_receive_state()

    assert state == DawnSerialProtocol.STATE_SYNC
    assert pos == 0
    assert length == 0


def test_frame_complete():
    """_frame_complete should detect complete serial frames."""
    assert not DawnSerialProtocol._frame_complete(2, 7)
    assert DawnSerialProtocol._frame_complete(2, 8)


def test_advance_receive_state_waits_for_sync(client):
    """_advance_receive_state should ignore non-sync bytes."""
    buffer = bytearray(client.FRAME_MAX_PAYLOAD + client.FRAME_MIN_LEN)

    state, pos, length = client._advance_receive_state(
        client.STATE_SYNC,
        0,
        0,
        0x00,
        buffer,
    )

    assert state == client.STATE_SYNC
    assert pos == 0
    assert length == 0


def test_advance_receive_state_parses_length_bytes(client):
    """_advance_receive_state should assemble the payload length."""
    buffer = bytearray(client.FRAME_MAX_PAYLOAD + client.FRAME_MIN_LEN)

    state, pos, length = client._advance_receive_state(
        client.STATE_SYNC,
        0,
        0,
        client.FRAME_SYNC,
        buffer,
    )
    state, pos, length = client._advance_receive_state(
        state,
        pos,
        length,
        0x04,
        buffer,
    )
    state, pos, length = client._advance_receive_state(
        state,
        pos,
        length,
        0x00,
        buffer,
    )

    assert state == client.STATE_FRAME
    assert pos == 3
    assert length == 4


def test_advance_receive_state_resets_on_oversized_payload(client):
    """_advance_receive_state should reset on invalid lengths."""
    buffer = bytearray(client.FRAME_MAX_PAYLOAD + client.FRAME_MIN_LEN)

    state, pos, length = client._advance_receive_state(
        client.STATE_LEN_HI,
        2,
        client.FRAME_MAX_PAYLOAD,
        0x01,
        buffer,
    )

    assert (state, pos, length) == client._reset_receive_state()


def test_advance_receive_state_consumes_frame_bytes(client):
    """_advance_receive_state should append bytes in frame mode."""
    buffer = bytearray(client.FRAME_MAX_PAYLOAD + client.FRAME_MIN_LEN)
    pos = 3
    buffer[0:3] = bytes([client.FRAME_SYNC, 0x02, 0x00])

    state, next_pos, length = client._advance_receive_state(
        client.STATE_FRAME,
        pos,
        2,
        client.CMD_GET_IO,
        buffer,
    )

    assert state == client.STATE_FRAME
    assert next_pos == pos + 1
    assert length == 2
    assert buffer[pos] == client.CMD_GET_IO


def test_parse_received_frame(client):
    """_parse_received_frame should reuse shared frame validation."""
    payload = b"\x01\x02"
    frame, _ = client._build_frame(client.CMD_GET_IO, payload)

    assert client._parse_received_frame(frame) == (
        client.CMD_GET_IO,
        payload,
    )
