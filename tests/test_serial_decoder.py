#!/usr/bin/env python3
# tools/dawnpy/tests/test_serial_decoder.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for serial value decoding."""

import struct

import pytest
from dawnpy.device.decode import _wrap_hex, decode_value
from dawnpy.objectid import ObjectIdDecoder


@pytest.fixture
def decoder():
    return ObjectIdDecoder()


def test_decode_float_vector(decoder):
    """Decode float vectors into list output."""
    data = struct.pack("<4f", 1.0, 2.0, 3.0, 4.0)
    lines = decode_value(data, 10, decoder, include_objid=True, objid=0x1)
    assert lines == ["0x00000001: [1.0, 2.0, 3.0, 4.0]"]


def test_decode_char_string(decoder):
    """Decode null-terminated strings."""
    data = b"hello\x00ignored"
    lines = decode_value(data, 14, decoder, include_objid=False)
    assert lines == ["hello"]


def test_decode_char_word_padded(decoder):
    """Decode word-padded char arrays (first byte)."""
    data = b"h\x00\x00\x00i\x00\x00\x00\x00\x00\x00\x00"
    lines = decode_value(data, 14, decoder, include_objid=False)
    assert lines == ["hi"]


def test_decode_char_word_padded_last_byte(decoder):
    """Decode word-padded char arrays (last byte)."""
    data = b"\x00\x00\x00h\x00\x00\x00i\x00\x00\x00\x00"
    lines = decode_value(data, 14, decoder, include_objid=False)
    assert lines == ["hi"]


def test_decode_char_empty(decoder):
    """Decode empty char strings."""
    data = b"\x00\x00\x00\x00"
    lines = decode_value(data, 14, decoder, include_objid=False)
    assert lines == ['""']


def test_decode_debug_includes_value(decoder):
    """Debug output includes decoded value."""
    data = struct.pack("<H", 513)
    lines = decode_value(
        data, 5, decoder, include_objid=True, objid=0x2, debug=True
    )
    assert lines[0].startswith("DEBUG:")
    assert lines[1] == "0x00000002: 513"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\x7f", "0x00000003: 127"),
        (b"\x01\x00", "0x00000003: 1"),
        (b"\x01\x00\x00\x00", "0x00000003: 1"),
        (b"\x01\x00\x00\x00\x00\x00\x00\x00", "0x00000003: 1"),
    ],
)
def test_decode_fallback_sizes(data, expected):
    """Fallback decoding uses integer sizes."""
    lines = decode_value(data, 99, None, include_objid=True, objid=0x3)
    assert lines == [expected]


def test_decode_hex_wrap():
    """Hex output wraps long lines."""
    data = bytes(range(64))
    lines = decode_value(data, 99, None, include_objid=True, objid=0x4)
    assert len(lines) > 1
    assert lines[0].startswith("0x00000004: 0x")


def test_decode_numeric_mismatch(decoder):
    """Numeric mismatch falls back to hex."""
    data = b"\x01\x02\x03"
    lines = decode_value(data, 5, decoder, include_objid=True, objid=0x5)
    assert lines[0].startswith("0x00000005: 0x")


def test_decode_char_unicode_error(decoder):
    """Invalid utf-8 uses printable fallback."""
    data = b"\xff\xfe\x00"
    lines = decode_value(data, 14, decoder, include_objid=False)
    assert "." in lines[0]


def test_decode_char_empty_after_null(decoder):
    """Null at start yields empty string."""
    data = b"\x00ABC"
    lines = decode_value(data, 14, decoder, include_objid=False)
    assert lines == ['""']


def test_wrap_hex_min_width():
    """Wrap hex enforces minimum chunk size."""
    lines = _wrap_hex("deadbeef", "X" * 100, max_line=80)
    assert len(lines) >= 1
