"""Schema node types for esplib record definitions.

These classes define the *structure* of records -- what fields they contain,
what types those fields are, and how to interpret raw bytes. They do NOT hold
record data; they are applied to raw bytes to produce typed values.

Hierarchy:
  Value types (operate on raw bytes):
    EspInteger, EspFloat, EspString, EspFormID, EspByteArray,
    EspStruct, EspUnion, EspArray

  Formatters (attached to EspInteger for display/validation):
    EspFlags, EspEnum

  Container types (map signatures to value types):
    EspSubRecord -- maps a 4-char signature to a value type
    EspRecord    -- maps a record signature to a list of EspSubRecord defs
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..utils import BinaryReader, BinaryWriter, FormID, BaseFormID
from ..exceptions import ParseError
from .context import EspContext


# ---------------------------------------------------------------------------
# IntType enum -- maps xEdit's itU8..itS64 to struct format and size
# ---------------------------------------------------------------------------

class IntType(Enum):
    """Integer type specifiers matching xEdit's itXX constants."""
    U8 = ('B', 1)
    S8 = ('b', 1)
    U16 = ('H', 2)
    S16 = ('h', 2)
    U32 = ('I', 4)
    S32 = ('i', 4)
    U64 = ('Q', 8)
    S64 = ('q', 8)

    def __init__(self, fmt: str, size: int):
        self.fmt = fmt
        self.byte_size = size


# ---------------------------------------------------------------------------
# Formatters -- EspFlags, EspEnum
# ---------------------------------------------------------------------------

def _flag_attr_name(name: str) -> str:
    """Normalize a flag name for attribute access: strip spaces, hyphens,
    apostrophes. 'Auto-calc Stats' -> 'AutocalcStats'."""
    return name.replace(' ', '').replace("'", '').replace('-', '')


class FlagSet:
    """A mutable set of flags supporting attribute, item, and containment access.

    Usage:
        flags.Female              # read
        flags.Female = True       # write
        flags['Female']           # read by original name
        flags['Non-Equippable']   # read by original name
        flags.NonEquippable        # read by normalized attribute
        'Female' in flags         # True if the flag is set
        int(flags)                # raw integer value
        for name in flags:        # iterate over set flag names
    """

    def __init__(self, value: int, names: Dict[int, str]):
        # Use object.__setattr__ for internal state to bypass our own __setattr__
        object.__setattr__(self, '_value', value)
        object.__setattr__(self, '_names', names)  # bit -> name
        object.__setattr__(self, '_flags', {})     # original_name -> bool
        object.__setattr__(self, '_name_to_bit', {})  # name or attr -> bit
        object.__setattr__(self, '_attr_to_name', {})  # attr -> original_name
        for bit, name in names.items():
            self._flags[name] = bool(value & (1 << bit))
            self._name_to_bit[name] = bit
            attr = _flag_attr_name(name)
            self._name_to_bit[attr] = bit
            self._attr_to_name[attr] = name


    def __getattr__(self, key: str) -> bool:
        # __getattr__ only fires when normal lookup fails, so internal
        # state (_value etc.) still reads normally.
        attr_to_name = object.__getattribute__(self, '_attr_to_name')
        if key in attr_to_name:
            return self._flags[attr_to_name[key]]
        raise AttributeError(key)


    def __setattr__(self, key: str, value) -> None:
        # Internal state starts with '_'
        if key.startswith('_'):
            object.__setattr__(self, key, value)
            return
        attr_to_name = object.__getattribute__(self, '_attr_to_name')
        if key in attr_to_name:
            self[attr_to_name[key]] = value
            return
        raise AttributeError(
            f"FlagSet has no flag named {key!r}; known: "
            f"{sorted(attr_to_name)}")


    def __getitem__(self, name: str) -> bool:
        if name in self._flags:
            return self._flags[name]
        attr = _flag_attr_name(name)
        if attr in self._attr_to_name:
            return self._flags[self._attr_to_name[attr]]
        raise KeyError(name)


    def __setitem__(self, name: str, is_set) -> None:
        is_set = bool(is_set)
        bit = self._name_to_bit.get(name)
        if bit is None:
            attr = _flag_attr_name(name)
            bit = self._name_to_bit.get(attr)
        if bit is None:
            raise KeyError(f"Unknown flag: {name}")
        original = self._names[bit]
        self._flags[original] = is_set
        if is_set:
            self._value |= (1 << bit)
        else:
            self._value &= ~(1 << bit)


    def __contains__(self, name: str) -> bool:
        """True if the named flag is set (not just defined)."""
        try:
            return self[name]
        except KeyError:
            return False


    def __iter__(self):
        """Iterate over names of flags that are set."""
        return (name for name, is_set in self._flags.items() if is_set)


    def __int__(self) -> int:
        return self._value


    def __repr__(self) -> str:
        set_flags = [name for name, is_set in self._flags.items() if is_set]
        return f"FlagSet({', '.join(set_flags)})"


    def __eq__(self, other) -> bool:
        if isinstance(other, FlagSet):
            return self._value == other._value
        if isinstance(other, int):
            return self._value == other
        return NotImplemented


    def __hash__(self):
        return hash(self._value)


class FlagConst:
    """Named flag constants for building flag values.

    Each attribute is the bit mask (int), so they can be OR'd together:
        ACBS.Female | ACBS.Essential  # -> 0x03
    """

    def __init__(self, names: Dict[int, str]):
        self._names = names
        for bit, name in names.items():
            attr = name.replace(' ', '_').replace("'", '').replace('-', '_')
            object.__setattr__(self, attr, 1 << bit)

    def __repr__(self) -> str:
        return f"FlagConst({list(self._names.values())})"


@dataclass
class EspFlags:
    """Bit flag names for an integer field."""
    names: Dict[int, str]


    @classmethod
    def new(cls, names: Dict[int, str]) -> EspFlags:
        return cls(names=names)


    def constants(self) -> FlagConst:
        """Create a FlagConst namespace for building flag values."""
        return FlagConst(self.names)


    def decode(self, value: int) -> FlagSet:
        """Decode an integer into a FlagSet."""
        return FlagSet(value, self.names)


    def encode(self, flags) -> int:
        """Encode flags back to an integer.

        Accepts:
          - int: pass through
          - FlagSet: extract int value
          - dict of {name: bool}: set named flags
          - set of names: set those flags
        """
        if isinstance(flags, int):
            return flags
        if isinstance(flags, FlagSet):
            return int(flags)
        if isinstance(flags, set):
            flags = {name: True for name in flags}

        # Build reverse lookup
        name_to_bit = {name: bit for bit, name in self.names.items()}
        value = 0
        for name, is_set in flags.items():
            if is_set and name in name_to_bit:
                value |= (1 << name_to_bit[name])
        return value


    def to_dict(self) -> dict:
        return {'type': 'flags', 'names': {str(k): v for k, v in self.names.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> EspFlags:
        return cls(names={int(k): v for k, v in d['names'].items()})


@dataclass
class EspEnum:
    """Value enumeration for an integer field."""
    values: Dict[int, str]

    @classmethod
    def new(cls, values: Dict[int, str]) -> EspEnum:
        return cls(values=values)

    def decode(self, value: int) -> str:
        """Get the name for a value, or a hex string if unknown."""
        return self.values.get(value, f"Unknown (0x{value:X})")

    def encode(self, name_or_value: Union[int, str]) -> int:
        """Encode a name or int back to an integer."""
        if isinstance(name_or_value, int):
            return name_or_value
        # Reverse lookup
        for val, name in self.values.items():
            if name == name_or_value:
                return val
        raise ValueError(f"Unknown enum name: {name_or_value}")

    def to_dict(self) -> dict:
        return {'type': 'enum', 'values': {str(k): v for k, v in self.values.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> EspEnum:
        return cls(values={int(k): v for k, v in d['values'].items()})


# ---------------------------------------------------------------------------
# Value types -- the building blocks
# ---------------------------------------------------------------------------

@dataclass
class EspInteger:
    """Integer field definition."""
    name: str
    int_type: IntType
    formatter: Union[EspFlags, EspEnum, None] = None

    @classmethod
    def new(cls, name: str, int_type: IntType,
            formatter: Union[EspFlags, EspEnum, None] = None) -> EspInteger:
        return cls(name=name, int_type=int_type, formatter=formatter)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None):
        data = reader.read_bytes(self.int_type.byte_size)
        value = struct.unpack(f'<{self.int_type.fmt}', data)[0]
        if self.formatter:
            return self.formatter.decode(value)
        return value

    def to_bytes(self, value: int) -> bytes:
        if self.formatter and not isinstance(value, int):
            value = self.formatter.encode(value)
        return struct.pack(f'<{self.int_type.fmt}', value)

    @property
    def byte_size(self) -> int:
        return self.int_type.byte_size

    def to_dict(self) -> dict:
        d = {'type': 'integer', 'name': self.name, 'int_type': self.int_type.name}
        if self.formatter:
            d['formatter'] = self.formatter.to_dict()
        return d


@dataclass
class EspFloat:
    """32-bit float field definition."""
    name: str

    @classmethod
    def new(cls, name: str) -> EspFloat:
        return cls(name=name)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None) -> float:
        return struct.unpack('<f', reader.read_bytes(4))[0]

    def to_bytes(self, value: float) -> bytes:
        return struct.pack('<f', value)

    @property
    def byte_size(self) -> int:
        return 4

    def to_dict(self) -> dict:
        return {'type': 'float', 'name': self.name}


@dataclass
class EspString:
    """String field definition."""
    name: str
    # 'zstring' = null-terminated, 'lstring' = uint16 length prefix,
    # 'wstring' = uint32 length prefix
    string_type: str = 'zstring'
    encoding: str = 'cp1252'

    @classmethod
    def new(cls, name: str, string_type: str = 'zstring',
            encoding: str = 'cp1252') -> EspString:
        return cls(name=name, string_type=string_type, encoding=encoding)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None,
                   available: int = None) -> str:
        if self.string_type == 'zstring':
            if available is not None:
                # Read fixed number of bytes, strip nulls
                data = reader.read_bytes(available)
                null_pos = data.find(b'\x00')
                if null_pos >= 0:
                    data = data[:null_pos]
                return data.decode(self.encoding, errors='replace')
            else:
                return reader.read_string(encoding=self.encoding)
        elif self.string_type == 'lstring':
            length = struct.unpack('<H', reader.read_bytes(2))[0]
            if length == 0:
                return ""
            return reader.read_bytes(length).decode(self.encoding, errors='replace')
        elif self.string_type == 'wstring':
            length = struct.unpack('<I', reader.read_bytes(4))[0]
            if length == 0:
                return ""
            return reader.read_bytes(length).decode(self.encoding, errors='replace')
        else:
            raise ParseError(f"Unknown string type: {self.string_type}")

    def to_bytes(self, value: str) -> bytes:
        encoded = value.encode(self.encoding, errors='replace')
        if self.string_type == 'zstring':
            return encoded + b'\x00'
        elif self.string_type == 'lstring':
            return struct.pack('<H', len(encoded)) + encoded
        elif self.string_type == 'wstring':
            return struct.pack('<I', len(encoded)) + encoded
        else:
            raise ParseError(f"Unknown string type: {self.string_type}")

    def to_dict(self) -> dict:
        return {'type': 'string', 'name': self.name, 'string_type': self.string_type}


@dataclass
class EspFormID:
    """FormID reference field definition."""
    name: str
    # Optional list of valid reference record types (e.g. ['WEAP', 'ARMO'])
    valid_refs: Optional[List[str]] = None

    @classmethod
    def new(cls, name: str, valid_refs: Optional[List[str]] = None) -> EspFormID:
        return cls(name=name, valid_refs=valid_refs)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None) -> FormID:
        return FormID(struct.unpack('<I', reader.read_bytes(4))[0])

    def to_bytes(self, value: Union[BaseFormID, int]) -> bytes:
        if isinstance(value, BaseFormID):
            return struct.pack('<I', value.value)
        return struct.pack('<I', value)

    @property
    def byte_size(self) -> int:
        return 4

    def to_dict(self) -> dict:
        d = {'type': 'formid', 'name': self.name}
        if self.valid_refs:
            d['valid_refs'] = self.valid_refs
        return d


@dataclass
class EspByteArray:
    """Raw byte array field definition."""
    name: str
    # Fixed size, or None for "rest of data"
    size: Optional[int] = None

    @classmethod
    def new(cls, name: str, size: Optional[int] = None) -> EspByteArray:
        return cls(name=name, size=size)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None,
                   available: int = None) -> bytes:
        if self.size is not None:
            return reader.read_bytes(self.size)
        elif available is not None:
            return reader.read_bytes(available)
        else:
            return reader.read_bytes(reader.remaining())

    def to_bytes(self, value: bytes) -> bytes:
        return value

    def to_dict(self) -> dict:
        d = {'type': 'bytes', 'name': self.name}
        if self.size is not None:
            d['size'] = self.size
        return d


@dataclass
class EspGmstValue:
    """GMST DATA value — type determined by EDID prefix.

    f = float32, i = int32, s = uint32 (string ID), b = uint32 (bool).
    Reads/writes the appropriate type based on the first character of
    the record's editor ID, passed via ctx.extra['editor_id'].
    """
    name: str

    @classmethod
    def new(cls, name: str) -> 'EspGmstValue':
        return cls(name=name)

    @staticmethod
    def _edid_type(ctx) -> str:
        edid = ''
        if ctx is not None:
            edid = ctx.extra.get('editor_id', '')
        if edid:
            return edid[0].lower()
        return 'f'

    def from_bytes(self, reader: BinaryReader, ctx=None,
                   available: int = None) -> Any:
        t = self._edid_type(ctx)
        if t == 'f':
            return struct.unpack('<f', reader.read_bytes(4))[0]
        elif t == 'i':
            return struct.unpack('<i', reader.read_bytes(4))[0]
        elif t == 'b':
            return bool(struct.unpack('<I', reader.read_bytes(4))[0])
        else:
            # 's' = string ID (uint32), or unknown prefix
            return struct.unpack('<I', reader.read_bytes(4))[0]

    def to_bytes(self, value, ctx=None) -> bytes:
        t = self._edid_type(ctx)
        if t == 'f':
            return struct.pack('<f', float(value))
        elif t == 'i':
            return struct.pack('<i', int(value))
        elif t == 'b':
            return struct.pack('<I', 1 if value else 0)
        elif t == 's':
            if isinstance(value, str):
                return value.encode('cp1252') + b'\x00'
            return struct.pack('<I', int(value))
        # Unknown prefix — infer from Python type
        if isinstance(value, float):
            return struct.pack('<f', value)
        elif isinstance(value, bool):
            return struct.pack('<I', 1 if value else 0)
        elif isinstance(value, int):
            return struct.pack('<i', value)
        raise TypeError(
            f"EspGmstValue: cannot serialize {type(value).__name__}")

    @property
    def byte_size(self) -> int:
        return 4

    def to_dict(self) -> dict:
        return {'type': 'gmst_value', 'name': self.name}


@dataclass
class EspAlternateTextures:
    """Alternate texture array (MO2S/MO3S/MO4S/MO5S).

    Binary format: uint32 count, then repeated entries of:
        uint32 name_length
        char[name_length] name (null-terminated)
        uint32 FormID (TXST reference)
        uint32 3D index

    Treated as raw bytes for round-trip, but the schema type lets
    FormID discovery code find and remap embedded FormIDs without
    hardcoded signature checks.
    """
    name: str

    @classmethod
    def new(cls, name: str) -> 'EspAlternateTextures':
        return cls(name=name)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None,
                   available: int = None) -> bytes:
        if available is not None:
            return reader.read_bytes(available)
        return reader.read_bytes(reader.remaining())

    def to_bytes(self, value: bytes) -> bytes:
        return value

    def to_dict(self) -> dict:
        return {'type': 'alternate_textures', 'name': self.name}


# ---------------------------------------------------------------------------
# Composite types -- EspStruct, EspArray, EspUnion
# ---------------------------------------------------------------------------

# Type alias for any value definition
ValueDef = Union[EspInteger, EspFloat, EspString, EspFormID, EspByteArray,
                 EspAlternateTextures, 'EspStruct', 'EspArray', 'EspUnion']


@dataclass
class EspStruct:
    """Ordered sequence of named fields."""
    name: str
    members: List[ValueDef]

    @classmethod
    def new(cls, name: str, members: List[ValueDef]) -> EspStruct:
        return cls(name=name, members=members)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None,
                   available: int = None) -> Dict[str, Any]:
        result = {}
        start = reader.tell()
        for i, member in enumerate(self.members):
            # For the last member, pass remaining available bytes
            if available is not None and i == len(self.members) - 1:
                remaining = available - (reader.tell() - start)
                if hasattr(member, 'from_bytes'):
                    try:
                        result[member.name] = member.from_bytes(
                            reader, ctx, available=remaining)
                    except TypeError:
                        result[member.name] = member.from_bytes(reader, ctx)
            else:
                result[member.name] = member.from_bytes(reader, ctx)
        return result

    def to_bytes(self, value: Dict[str, Any]) -> bytes:
        writer = BinaryWriter()
        for member in self.members:
            if member.name in value:
                writer.write_bytes(member.to_bytes(value[member.name]))
            else:
                # Zero-fill missing fields so the struct is full-size
                size = getattr(member, 'byte_size', None)
                if size is None:
                    size = getattr(member, 'size', None)
                if size is not None:
                    writer.write_bytes(b'\x00' * size)
                else:
                    break  # Variable-size field, can't pad
        return writer.get_bytes()

    def to_dict(self) -> dict:
        return {
            'type': 'struct',
            'name': self.name,
            'members': [m.to_dict() for m in self.members],
        }


@dataclass
class EspArray:
    """Repeated element definition."""
    name: str
    element: ValueDef
    # How to determine count:
    #   int: fixed count
    #   str: name of a preceding field that holds the count
    #   None: repeat until data is exhausted
    count: Union[int, str, None] = None

    @classmethod
    def new(cls, name: str, element: ValueDef,
            count: Union[int, str, None] = None) -> EspArray:
        return cls(name=name, element=element, count=count)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None,
                   available: int = None, resolved_count: int = None) -> List[Any]:
        result = []

        if resolved_count is not None:
            n = resolved_count
        elif isinstance(self.count, int):
            n = self.count
        else:
            n = None  # Read until exhausted

        if n is not None:
            for _ in range(n):
                result.append(self.element.from_bytes(reader, ctx))
        else:
            # Read until end of available data
            end = reader.tell() + available if available else len(reader.data)
            while reader.tell() < end:
                if reader.remaining() == 0:
                    break
                result.append(self.element.from_bytes(reader, ctx))

        return result

    def to_bytes(self, value: List[Any]) -> bytes:
        writer = BinaryWriter()
        for item in value:
            writer.write_bytes(self.element.to_bytes(item))
        return writer.get_bytes()

    def to_dict(self) -> dict:
        d = {
            'type': 'array',
            'name': self.name,
            'element': self.element.to_dict(),
        }
        if self.count is not None:
            d['count'] = self.count
        return d


@dataclass
class EspUnion:
    """Conditional field -- picks one of several definitions based on a decider.

    The decider is a callable that receives an EspContext and returns
    an index into the members list.
    """
    name: str
    decider: Callable[[EspContext], int]
    members: List[ValueDef]

    @classmethod
    def new(cls, name: str, decider: Callable[[EspContext], int],
            members: List[ValueDef]) -> EspUnion:
        return cls(name=name, decider=decider, members=members)

    def from_bytes(self, reader: BinaryReader, ctx: EspContext = None,
                   available: int = None) -> Any:
        index = self.decider(ctx or EspContext())
        if index < 0 or index >= len(self.members):
            raise ParseError(
                f"Union decider returned index {index}, "
                f"but only {len(self.members)} members defined")
        member = self.members[index]
        try:
            return member.from_bytes(reader, ctx, available=available)
        except TypeError:
            return member.from_bytes(reader, ctx)

    def to_bytes(self, value: Any) -> bytes:
        # Caller must know which member was active and serialize accordingly.
        # For simple cases, delegate to the value's type.
        # For round-trip, the original bytes are preserved.
        if isinstance(value, bytes):
            return value
        # Try each member until one succeeds
        for member in self.members:
            if hasattr(member, 'to_bytes'):
                try:
                    return member.to_bytes(value)
                except (KeyError, TypeError, struct.error):
                    continue
        raise TypeError(
            f"Union '{self.name}': cannot serialize {type(value).__name__}")

    def to_dict(self) -> dict:
        return {
            'type': 'union',
            'name': self.name,
            'members': [m.to_dict() for m in self.members],
            # decider is a callable, can't serialize -- note it
            'decider': '<callable>',
        }


# ---------------------------------------------------------------------------
# Container types -- EspSubRecord, EspGroup, EspRecord
# ---------------------------------------------------------------------------

# Type alias for members that can appear in an EspRecord or EspGroup
MemberDef = Union['EspSubRecord', 'EspGroup']


@dataclass
class EspSubRecord:
    """Maps a 4-char subrecord signature to a value definition."""
    signature: str
    name: str
    value_def: ValueDef
    required: bool = False

    @classmethod
    def new(cls, signature: str, name: str, value_def: ValueDef,
            required: bool = False) -> EspSubRecord:
        return cls(signature=signature, name=name, value_def=value_def,
                   required=required)

    def from_subrecord(self, subrecord, ctx: EspContext = None) -> Any:
        """Interpret a SubRecord's raw bytes using this definition."""
        if ctx is None:
            ctx = EspContext()
        # Pass subrecord size into context for union deciders that need it
        ctx.extra['subrecord_size'] = subrecord.size
        reader = BinaryReader(subrecord.data)
        try:
            return self.value_def.from_bytes(
                reader, ctx, available=subrecord.size)
        except TypeError:
            return self.value_def.from_bytes(reader, ctx)

    def to_subrecord_data(self, value: Any, ctx: EspContext = None) -> bytes:
        """Serialize a value back to raw subrecord data bytes."""
        try:
            return self.value_def.to_bytes(value, ctx=ctx)
        except TypeError:
            return self.value_def.to_bytes(value)

    def to_dict(self) -> dict:
        return {
            'type': 'subrecord',
            'signature': self.signature,
            'name': self.name,
            'value_def': self.value_def.to_dict(),
            'required': self.required,
        }


@dataclass
class EspGroup:
    """A structural group of subrecords that appear together in a fixed order.

    Mirrors xEdit's wbRStruct -- defines sections within a record where the
    same subrecord signature can have different meanings based on position
    (e.g. MNAM as 'Male Marker' in one group, MNAM as 'Male Data Marker'
    in another).

    Groups participate in canonical_order() so that auto-sort can correctly
    place subrecords even when signatures are reused across sections.
    """
    name: str
    members: List[MemberDef]

    @classmethod
    def new(cls, name: str, members: List[MemberDef]) -> 'EspGroup':
        return cls(name=name, members=members)

    def flat_subrecords(self) -> List[EspSubRecord]:
        """Recursively flatten this group into an ordered list of EspSubRecords."""
        result = []
        for m in self.members:
            if isinstance(m, EspGroup):
                result.extend(m.flat_subrecords())
            else:
                result.append(m)
        return result

    def to_dict(self) -> dict:
        return {
            'type': 'group',
            'name': self.name,
            'members': [m.to_dict() for m in self.members],
        }


@dataclass
class EspRecord:
    """Top-level record schema -- defines what subrecords a record type contains.

    Members can be EspSubRecord or EspGroup. Groups define structural sections
    where subrecords appear together in a fixed order. The canonical_order()
    method flattens groups to produce the full signature sequence for auto-sort.
    """
    signature: str
    name: str
    members: List[MemberDef]
    flags_def: Optional[EspFlags] = None

    @classmethod
    def new(cls, signature: str, name: str, members: List[MemberDef],
            flags_def: Optional[EspFlags] = None) -> 'EspRecord':
        return cls(signature=signature, name=name, members=members,
                   flags_def=flags_def)

    def canonical_order(self) -> List[str]:
        """Flatten all members (including groups) into the canonical
        signature sequence. This is the authoritative subrecord order."""
        result = []
        for m in self.members:
            if isinstance(m, EspGroup):
                result.extend(sr.signature for sr in m.flat_subrecords())
            else:
                result.append(m.signature)
        return result

    def get_member(self, signature: str) -> Optional[EspSubRecord]:
        """Find member definition by subrecord signature (searches into groups)."""
        return _find_member(self.members, signature)

    def from_record(self, record, ctx: EspContext = None) -> Dict[str, Any]:
        """Interpret a Record's subrecords using this schema.

        Returns a dict of {subrecord_name: parsed_value}.
        Subrecords not in the schema are skipped.
        Subrecords that appear multiple times produce a list.
        """
        if ctx is None:
            ctx = EspContext()
        ctx.record_signature = self.signature
        ctx.flags = record.flags
        ctx.form_version = record.version

        result = {}
        # Track which signatures can repeat
        seen = set()

        for subrecord in record.subrecords:
            member = self.get_member(subrecord.signature)
            if member is None:
                continue

            value = member.from_subrecord(subrecord, ctx)

            if subrecord.signature in seen:
                # Multiple subrecords with same sig -> list
                existing = result.get(member.name)
                if not isinstance(existing, list):
                    result[member.name] = [existing, value]
                else:
                    existing.append(value)
            else:
                result[member.name] = value
                seen.add(subrecord.signature)

        return result

    def to_dict(self) -> dict:
        d = {
            'type': 'record',
            'signature': self.signature,
            'name': self.name,
            'members': [m.to_dict() for m in self.members],
        }
        if self.flags_def:
            d['flags_def'] = self.flags_def.to_dict()
        return d


def _find_member(members: List[MemberDef], signature: str) -> Optional[EspSubRecord]:
    """Recursively search a member list for an EspSubRecord matching signature."""
    for m in members:
        if isinstance(m, EspGroup):
            found = _find_member(m.members, signature)
            if found is not None:
                return found
        elif m.signature == signature:
            return m
    return None
