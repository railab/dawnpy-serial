#!/usr/bin/env python3
#
# SPDX-License-Identifier: Apache-2.0
#

"""Test-local ObjectId header definitions for the standalone serial package."""

import dawnpy.headerdefs.bundle as header_bundle
import pytest
from dawnpy.headerdefs.bundle import HeaderBundle, HeaderDefinitionGroups

_HEADER_DEFS = {
    "bit_fields": {
        "priv": {"shift": 0, "width": 14, "max": 0x3FFF},
        "flags": {"shift": 14, "width": 2, "max": 0x3},
        "dtype": {"shift": 16, "width": 4, "max": 0xF},
        "ext": {"shift": 20, "width": 1, "max": 0x1},
        "cls": {"shift": 21, "width": 9, "max": 0x1FF},
        "type": {"shift": 30, "width": 2, "max": 0x3},
    },
    "object_types": {
        0: "ANY",
        1: "IO",
        2: "PROTO",
        3: "PROG",
    },
    "dtype": [
        {"value": 0, "type": "invalid", "size": 0},
        {"value": 1, "type": "bool", "size": 8},
        {"value": 2, "type": "int8", "size": 8},
        {"value": 3, "type": "uint8", "size": 8},
        {"value": 4, "type": "int16", "size": 16},
        {"value": 5, "type": "uint16", "size": 16},
        {"value": 6, "type": "int32", "size": 32},
        {"value": 7, "type": "uint32", "size": 32},
        {"value": 8, "type": "int64", "size": 64},
        {"value": 9, "type": "uint64", "size": 64},
        {"value": 10, "type": "float", "size": 32},
        {"value": 11, "type": "double", "size": 64},
        {"value": 12, "type": "b16", "size": 32},
        {"value": 13, "type": "ub16", "size": 32},
        {"value": 14, "type": "char", "size": 8},
        {"value": 15, "type": "block", "size": 8},
    ],
    "io_classes": {
        5: "dummy",
        100: "virt",
    },
    "proto_classes": {},
    "prog_classes": {},
}


@pytest.fixture(autouse=True)
def objectid_header_defs(monkeypatch):
    """Keep serial tests independent from Dawn C++ checkout headers."""

    def _load_header_bundle():
        return HeaderBundle(
            HeaderDefinitionGroups(
                header_defs=_HEADER_DEFS,
                type_defs={},
                metadata_defs=[],
                component_defs={},
            )
        )

    header_bundle.load_header_bundle.cache_clear()
    monkeypatch.setattr(
        header_bundle, "load_header_bundle", _load_header_bundle
    )
    yield
