"""esplib.defs -- Schema/definition system for Bethesda record types."""

from .types import (
    IntType,
    EspFlags, EspEnum,
    EspInteger, EspFloat, EspString, EspFormID, EspByteArray,
    EspStruct, EspArray, EspUnion,
    EspSubRecord, EspGroup, EspRecord,
)
from .context import EspContext
from .game import GameRegistry
from . import tes5 as _tes5  # noqa: F401 -- triggers auto-registration

__all__ = [
    'IntType',
    'EspFlags', 'EspEnum',
    'EspInteger', 'EspFloat', 'EspString', 'EspFormID', 'EspByteArray',
    'EspStruct', 'EspArray', 'EspUnion',
    'EspSubRecord', 'EspGroup', 'EspRecord',
    'EspContext',
    'GameRegistry',
]
