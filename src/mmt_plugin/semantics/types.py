"""PDL type facts: wire widths, integer types and the C storage of fields.

Widths are the PDL ones of the corpus README (Struct layout), not the SDK's
in-memory sizes: ``MMT_BINARY_DATA`` and ``MMT_DATA_PATH`` are 68-byte SDK
structs and most other types have no wire width at all, so they have none
here (the decided rule on an omitted ``data_len``).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import NamedTuple

from mmt_plugin.pdl.model import DataType

__all__ = [
    "BITFIELD_TYPES",
    "FIXED_WIDTHS",
    "INTEGER_TYPES",
    "CStorage",
    "c_storage",
]

D = DataType

#: The wire width in bytes of each type that has a fixed one. ``T*`` struct
#: fields read as ``MMT_DATA_POINTER``, 4 bytes on the wire (decided rule).
FIXED_WIDTHS = MappingProxyType(
    {
        D.MMT_U8_DATA: 1,
        D.MMT_U16_DATA: 2,
        D.MMT_U32_DATA: 4,
        D.MMT_U64_DATA: 8,
        D.MMT_DATA_CHAR: 1,
        D.MMT_DATA_PORT: 2,
        D.MMT_DATA_MAC_ADDR: 6,
        D.MMT_DATA_IP_ADDR: 4,
        D.MMT_DATA_IP_NET: 4,
        D.MMT_DATA_IP6_ADDR: 16,
        D.MMT_DATA_POINTER: 4,
    }
)

#: The types whose value is an integer: what ``val()`` can read.
INTEGER_TYPES = frozenset(
    {
        D.MMT_U8_DATA,
        D.MMT_U16_DATA,
        D.MMT_U32_DATA,
        D.MMT_U64_DATA,
        D.MMT_DATA_CHAR,
        D.MMT_DATA_PORT,
    }
)

#: The types a bitfield's storage unit can have.
BITFIELD_TYPES = frozenset({D.MMT_U8_DATA, D.MMT_U16_DATA, D.MMT_U32_DATA, D.MMT_U64_DATA})


class CStorage(NamedTuple):
    """How a field is declared in an emitted C struct: its type, size and
    natural alignment (LP64)."""

    c_type: str
    size: int
    align: int


_C_STORAGE = MappingProxyType(
    {
        D.MMT_U8_DATA: CStorage("uint8_t", 1, 1),
        D.MMT_U16_DATA: CStorage("uint16_t", 2, 2),
        D.MMT_U32_DATA: CStorage("uint32_t", 4, 4),
        D.MMT_U64_DATA: CStorage("uint64_t", 8, 8),
        D.MMT_DATA_CHAR: CStorage("char", 1, 1),
        D.MMT_DATA_PORT: CStorage("uint16_t", 2, 2),
        D.MMT_DATA_MAC_ADDR: CStorage("uint8_t[6]", 6, 1),
        D.MMT_DATA_IP_ADDR: CStorage("uint8_t[4]", 4, 1),
        D.MMT_DATA_IP_NET: CStorage("uint8_t[4]", 4, 1),
        D.MMT_DATA_IP6_ADDR: CStorage("uint8_t[16]", 16, 1),
        # The 4 wire bytes of a T* field: a C pointer is 8 bytes on LP64.
        D.MMT_DATA_POINTER: CStorage("uint32_t", 4, 4),
    }
)


def c_storage(data_type: DataType) -> CStorage:
    """The C storage of a fixed-width type; ``KeyError`` for any other."""
    return _C_STORAGE[data_type]
