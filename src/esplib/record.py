"""Record and SubRecord classes for esplib."""

from __future__ import annotations

import struct
from typing import List, Optional, Union, TYPE_CHECKING
from .utils import FormID, BaseFormID, BinaryReader, BinaryWriter, decompress_zlib, compress_zlib
from .exceptions import ParseError, ValidationError

if TYPE_CHECKING:
    from .defs.types import EspGroup

# Record flag for compressed data
COMPRESSED_FLAG = 0x00040000


class SubRecord:
    """Represents a subrecord within a main record."""

    def __init__(self, signature: str, data: bytes = b''):
        if len(signature) != 4:
            raise ValidationError(
                f"Subrecord signature must be 4 characters, got {len(signature)}")
        self.signature = signature
        self._data = bytearray(data)
        self.modified = False

    @property
    def data(self) -> bytes:
        return bytes(self._data)

    @data.setter
    def data(self, value: bytes) -> None:
        self._data = bytearray(value)
        self.modified = True

    @property
    def size(self) -> int:
        return len(self._data)

    def get_reader(self) -> BinaryReader:
        return BinaryReader(self.data)

    # --- Getters ---

    def get_uint8(self, offset: int = 0) -> int:
        if offset + 1 > len(self._data):
            raise ParseError(f"Offset {offset} out of range for subrecord {self.signature}")
        return struct.unpack('<B', self._data[offset:offset + 1])[0]

    def get_uint16(self, offset: int = 0) -> int:
        if offset + 2 > len(self._data):
            raise ParseError(f"Offset {offset} out of range for subrecord {self.signature}")
        return struct.unpack('<H', self._data[offset:offset + 2])[0]

    def get_uint32(self, offset: int = 0) -> int:
        if offset + 4 > len(self._data):
            raise ParseError(f"Offset {offset} out of range for subrecord {self.signature}")
        return struct.unpack('<I', self._data[offset:offset + 4])[0]

    def get_int32(self, offset: int = 0) -> int:
        if offset + 4 > len(self._data):
            raise ParseError(f"Offset {offset} out of range for subrecord {self.signature}")
        return struct.unpack('<i', self._data[offset:offset + 4])[0]

    def get_float(self, offset: int = 0) -> float:
        if offset + 4 > len(self._data):
            raise ParseError(f"Offset {offset} out of range for subrecord {self.signature}")
        return struct.unpack('<f', self._data[offset:offset + 4])[0]

    def get_string(self, encoding: str = 'cp1252') -> str:
        data = self._data.rstrip(b'\x00')
        return data.decode(encoding, errors='replace')

    def get_lstring(self, encoding: str = 'cp1252') -> str:
        if len(self._data) < 2:
            return ""
        length = struct.unpack('<H', self._data[:2])[0]
        if length == 0:
            return ""
        if 2 + length > len(self._data):
            raise ParseError(f"String length {length} exceeds subrecord data size")
        return self._data[2:2 + length].decode(encoding, errors='replace')

    def get_form_id(self, offset: int = 0) -> FormID:
        return FormID(self.get_uint32(offset))

    def get_form_id_array(self) -> List[FormID]:
        if len(self._data) % 4 != 0:
            raise ParseError(
                f"FormID array size must be multiple of 4, got {len(self._data)}")
        form_ids = []
        for i in range(0, len(self._data), 4):
            form_ids.append(FormID(struct.unpack('<I', self._data[i:i + 4])[0]))
        return form_ids

    # --- Setters ---

    def set_uint8(self, offset: int, value: int) -> None:
        self._ensure_size(offset + 1)
        struct.pack_into('<B', self._data, offset, value)
        self.modified = True

    def set_uint16(self, offset: int, value: int) -> None:
        self._ensure_size(offset + 2)
        struct.pack_into('<H', self._data, offset, value)
        self.modified = True

    def set_uint32(self, offset: int, value: int) -> None:
        self._ensure_size(offset + 4)
        struct.pack_into('<I', self._data, offset, value)
        self.modified = True

    def set_int32(self, offset: int, value: int) -> None:
        self._ensure_size(offset + 4)
        struct.pack_into('<i', self._data, offset, value)
        self.modified = True

    def set_float(self, offset: int, value: float) -> None:
        self._ensure_size(offset + 4)
        struct.pack_into('<f', self._data, offset, value)
        self.modified = True

    def set_string(self, value: str, encoding: str = 'cp1252') -> None:
        encoded = value.encode(encoding, errors='replace')
        self._data = bytearray(encoded + b'\x00')
        self.modified = True

    def set_lstring(self, value: str, encoding: str = 'cp1252') -> None:
        encoded = value.encode(encoding, errors='replace')
        self._data = bytearray(struct.pack('<H', len(encoded)) + encoded)
        self.modified = True

    def set_form_id(self, offset: int, form_id: Union[BaseFormID, int]) -> None:
        if isinstance(form_id, BaseFormID):
            self.set_uint32(offset, form_id.value)
        else:
            self.set_uint32(offset, form_id)

    def set_form_id_array(self, form_ids: List[Union[BaseFormID, int]]) -> None:
        self._data = bytearray()
        for form_id in form_ids:
            if isinstance(form_id, BaseFormID):
                self._data.extend(struct.pack('<I', form_id.value))
            else:
                self._data.extend(struct.pack('<I', form_id))
        self.modified = True

    def _ensure_size(self, required_size: int) -> None:
        if len(self._data) < required_size:
            self._data.extend(b'\x00' * (required_size - len(self._data)))

    def to_bytes(self) -> bytes:
        """Convert subrecord to binary format, using XXXX overflow if needed."""
        writer = BinaryWriter()
        data_len = len(self._data)

        if data_len > 0xFFFF:
            # Write XXXX marker with real size
            writer.write_bytes(b'XXXX')
            writer.write_uint16(4)
            writer.write_uint32(data_len)
            # Write actual subrecord with size=0
            writer.write_bytes(self.signature.encode('ascii'))
            writer.write_uint16(0)
            writer.write_bytes(self._data)
        else:
            writer.write_bytes(self.signature.encode('ascii'))
            writer.write_uint16(data_len)
            writer.write_bytes(self._data)

        return writer.get_bytes()

    def __str__(self) -> str:
        return f"SubRecord({self.signature}, {len(self._data)} bytes)"

    def __repr__(self) -> str:
        return f"SubRecord(signature='{self.signature}', size={len(self._data)})"


class GroupInstance:
    """One runtime instance of a repeating EspGroup.

    For example, an HDPT record's "Part" group has instances like:
        GroupInstance('Part', [SubRecord('NAM0', ...), SubRecord('NAM1', ...)])

    The caller manipulates group instances via Record.get_group(), which
    returns the live list. Reorder, append, delete directly on that list.
    Create new instances with GroupInstance.new().
    """

    def __init__(self, group_def: EspGroup, children: list = None):
        self.group_def = group_def
        self.name = group_def.name
        # children: list of SubRecord | list[GroupInstance] mirroring
        # group_def.members (but only populated entries)
        self.children: list = children if children is not None else []

    @classmethod
    def new(cls, group_def: EspGroup) -> GroupInstance:
        """Create a new empty group instance."""
        return cls(group_def)

    def add_subrecord(self, signature: str, data: bytes = b'') -> SubRecord:
        sr = SubRecord(signature, data)
        self.children.append(sr)
        return sr

    def get_subrecord(self, signature: str) -> Optional[SubRecord]:
        for child in self.children:
            if isinstance(child, SubRecord) and child.signature == signature:
                return child
        return None

    def get_subrecords(self, signature: str) -> List[SubRecord]:
        return [c for c in self.children
                if isinstance(c, SubRecord) and c.signature == signature]

    def flatten(self) -> List[SubRecord]:
        """Flatten this instance to an ordered list of SubRecords for serialization.

        Sorts children by the group_def's member order, then recursively
        flattens any nested group instance lists.
        """
        return _sort_and_flatten(self.children, self.group_def.members)

    def __repr__(self) -> str:
        n = sum(1 for c in self.children if isinstance(c, SubRecord))
        return f"GroupInstance({self.name!r}, {n} subrecords)"


# Type alias for Record.children entries
ChildEntry = Union[SubRecord, list]  # list is list[GroupInstance]


class Record:
    """Represents a main record in a Bethesda plugin.

    Supports schema-aware field access via __getitem__/__setitem__ when
    a schema (EspRecord) is bound via the `schema` attribute:

        weapon['DATA']['damage']       # read a field
        weapon['DATA']['damage'] = 20  # write a field

    Without a schema, __getitem__ falls back to returning raw SubRecords
    by signature.

    When a schema is bound, the flat subrecords list is restructured into
    `children` -- a mixed list of SubRecords and list[GroupInstance] that
    mirrors the schema's member list. Auto-sort works hierarchically at
    each level.
    """

    def __init__(self, signature: str, form_id: Union[FormID, int] = 0, flags: int = 0):
        if len(signature) != 4:
            raise ValidationError(
                f"Record signature must be 4 characters, got {len(signature)}")
        self.signature = signature
        self.form_id = FormID(form_id) if isinstance(form_id, int) else form_id
        self.flags = flags
        self.timestamp: int = 0
        self.version: int = 44
        self.version_control_info: int = 0
        self.subrecords: List[SubRecord] = []
        self.children: Optional[List[ChildEntry]] = None
        self.modified = False
        # For compressed records: store the original raw payload so we can
        # write it back verbatim if the record hasn't been modified.
        self._original_compressed_payload: Optional[bytes] = None
        # Schema binding (set by Plugin.set_game() or manually)
        self.schema = None  # Optional[EspRecord] -- set externally
        # Cache for resolved subrecord values
        self._resolved_cache: dict = {}
        # Back-reference to owning Plugin (set by Plugin._link_records)
        self.plugin = None

    def normalize_form_id(self, form_id) -> 'AbsoluteFormID':
        """Convert a FormID from this record's plugin indexing to
        load-order indexing. Delegates to the owning plugin."""
        if self.plugin is not None:
            return self.plugin.normalize_form_id(form_id)
        from .utils import AbsoluteFormID as _AbsoluteFormID
        if isinstance(form_id, int):
            return _AbsoluteFormID(form_id)
        return _AbsoluteFormID(form_id.value)


    def _normalize_value(self, value):
        """Normalize FormIDs in a parsed schema value to load-order indexing."""
        if self.plugin is None or self.plugin.plugin_set is None:
            return value
        from .utils import BaseFormID as _BaseFormID
        if isinstance(value, _BaseFormID):
            return self.normalize_form_id(value)
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._normalize_value(v) for v in value]
        return value


    @property
    def is_compressed(self) -> bool:
        return bool(self.flags & COMPRESSED_FLAG)

    @property
    def editor_id(self) -> Optional[str]:
        edid = self.get_subrecord("EDID")
        return edid.get_string() if edid else None

    @editor_id.setter
    def editor_id(self, value: str) -> None:
        edid = self.get_subrecord("EDID")
        if edid:
            edid.set_string(value)
        else:
            self.add_subrecord("EDID").set_string(value)

    @property
    def full_name(self) -> Optional[str]:
        """Get full name from FULL subrecord.

        For localized plugins, resolves the string table ID automatically
        if the record has a back-reference to its Plugin.
        """
        full = self.get_subrecord("FULL")
        if not full:
            return None
        if full.size == 4 and self.plugin and self.plugin.is_localized:
            string_id = full.get_uint32()
            resolved = self.plugin.resolve_string(string_id)
            if resolved is not None:
                return resolved
            return None
        return full.get_string()

    @full_name.setter
    def full_name(self, value: str) -> None:
        full = self.get_subrecord("FULL")
        if full:
            full.set_lstring(value)
        else:
            self.add_subrecord("FULL").set_lstring(value)

    def get_localized_string_id(self, subrecord_sig: str) -> Optional[int]:
        """Get a localized string table ID from a subrecord.
        For localized plugins, certain subrecords (FULL, DESC, etc.) store
        a uint32 string ID instead of inline text.
        """
        sr = self.get_subrecord(subrecord_sig)
        if sr and sr.size == 4:
            return sr.get_uint32()
        return None

    def __getitem__(self, key: str):
        """Schema-aware field access by subrecord signature.

        With schema: returns parsed value (dict for structs, int for integers, etc.)
        Without schema: returns the raw SubRecord object.
        """
        if self.schema is not None:
            # Check cache first
            if key in self._resolved_cache:
                return self._resolved_cache[key]

            member = self.schema.get_member(key)
            if member is not None:
                subrecord = self.get_subrecord(key)
                if subrecord is not None:
                    from .defs.context import EspContext
                    ctx = EspContext(
                        flags=self.flags,
                        form_version=self.version,
                        record_signature=self.signature,
                        extra={'editor_id': self.editor_id or ''},
                    )
                    value = member.from_subrecord(subrecord, ctx)
                    value = self._normalize_value(value)
                    self._resolved_cache[key] = value
                    return value
                return None
            # Unknown subrecord sig -- fall through to raw access

        # Fallback: return raw SubRecord
        sr = self.get_subrecord(key)
        if sr is None:
            raise KeyError(f"No subrecord with signature '{key}'")
        return sr

    def __setitem__(self, key: str, value):
        """Schema-aware field write by subrecord signature.

        With schema: serializes the value back to subrecord bytes.
        Without schema: expects a SubRecord or bytes.
        """
        if self.schema is not None:
            member = self.schema.get_member(key)
            if member is not None:
                from .defs.context import EspContext as _Ctx
                ctx = _Ctx(
                    flags=self.flags,
                    form_version=self.version,
                    record_signature=self.signature,
                    extra={'editor_id': self.editor_id or ''},
                )
                raw = member.to_subrecord_data(value, ctx=ctx)
                if isinstance(raw, (bytes, bytearray)):
                    subrecord = self.get_subrecord(key)
                    if subrecord is not None:
                        subrecord.data = bytearray(raw)
                    else:
                        self.add_subrecord(key, raw)
                    self._resolved_cache.pop(key, None)
                    self.modified = True
                    return
                # Schema couldn't serialize — fall through

        # Fallback: set raw data
        if isinstance(value, str):
            value = value.encode('cp1252') + b'\x00'
        elif isinstance(value, float):
            value = struct.pack('<f', value)
        elif isinstance(value, int) and not isinstance(value, bool):
            # Auto-size: 1/2/4 bytes based on magnitude
            if -128 <= value <= 255:
                value = struct.pack('<B', value & 0xFF)
            elif -32768 <= value <= 65535:
                value = struct.pack('<H', value & 0xFFFF)
            else:
                value = struct.pack('<I', value & 0xFFFFFFFF)
        if isinstance(value, (bytes, bytearray)):
            subrecord = self.get_subrecord(key)
            if subrecord is not None:
                subrecord.data = bytearray(value)
            else:
                self.add_subrecord(key, value)
            self.modified = True
        elif isinstance(value, SubRecord):
            # Replace or add
            for i, sr in enumerate(self.subrecords):
                if sr.signature == key:
                    self.subrecords[i] = value
                    self.modified = True
                    return
            self.subrecords.append(value)
            self.modified = True
        else:
            raise TypeError(
                f"Without a schema, value must be bytes, str, or SubRecord, "
                f"got {type(value)}")

    def __contains__(self, key: str) -> bool:
        """Check if a subrecord with the given signature exists."""
        return any(sr.signature == key for sr in self.subrecords)

    def has_subrecord(self, signature: str) -> bool:
        """Check if a subrecord with the given signature exists."""
        return signature in self

    def copy(self) -> 'Record':
        """Deep copy this record and all its subrecords."""
        new = Record(self.signature, FormID(self.form_id.value), self.flags)
        new.timestamp = self.timestamp
        new.version = self.version
        new.version_control_info = self.version_control_info
        new.schema = self.schema
        for sr in self.subrecords:
            new.subrecords.append(SubRecord(sr.signature, sr.data))
        return new

    def get_subrecord(self, signature: str) -> Optional[SubRecord]:
        for subrecord in self.subrecords:
            if subrecord.signature == signature:
                return subrecord
        return None

    def get_subrecords(self, signature: str) -> List[SubRecord]:
        return [sr for sr in self.subrecords if sr.signature == signature]

    def add_subrecord(self, signature: str, data=b'') -> SubRecord:
        formid_sentinel = (isinstance(data, FormID) and data.file_index == 0xFF)
        if isinstance(data, str):
            data = data.encode('cp1252') + b'\x00'
        elif isinstance(data, BaseFormID):
            import struct as _struct
            data = _struct.pack('<I', data.value)
        subrecord = SubRecord(signature, data)
        self.subrecords.append(subrecord)
        self.modified = True
        if formid_sentinel and self.plugin is not None:
            self.plugin._local_formid_fixups.append((subrecord, 0))
        return subrecord

    def add_tint_layer(self, tini: int, tinc: list, tinv: int, tias: int) -> None:
        """Add a tint layer (TINI + TINC + TINV + TIAS subrecords).

        tini: tint index (U16)
        tinc: color as [R, G, B, A] (4 x U8)
        tinv: interpolation value (S32)
        tias: preset index (S16)
        """
        import struct as _struct
        self.add_subrecord('TINI', _struct.pack('<H', tini))
        self.add_subrecord('TINC', bytes(tinc))
        self.add_subrecord('TINV', _struct.pack('<i', tinv))
        self.add_subrecord('TIAS', _struct.pack('<h', tias))


    def insert_subrecord(self, index: int, signature: str, data: bytes = b'') -> SubRecord:
        subrecord = SubRecord(signature, data)
        self.subrecords.insert(index, subrecord)
        self.modified = True
        return subrecord

    def remove_subrecord(self, subrecord: SubRecord) -> bool:
        if subrecord in self.subrecords:
            self.subrecords.remove(subrecord)
            self.modified = True

            return True
        return False

    def remove_subrecords(self, signature: str) -> int:
        original = len(self.subrecords)
        self.subrecords = [sr for sr in self.subrecords if sr.signature != signature]
        removed = original - len(self.subrecords)
        if removed > 0:
            self.modified = True

        return removed

    def clear_subrecords(self) -> None:
        self.subrecords.clear()
        self.modified = True

    def bind_schema(self, schema) -> None:
        """Bind a schema definition to this record.

        Children are built lazily on first access (get_group or modify+save),
        so binding is cheap.
        """
        self.schema = schema
        self._resolved_cache.clear()
        self.children = None

    def _ensure_children(self) -> List:
        """Build the children structure from subrecords if not yet done."""
        if self.children is None:
            if self.schema is None:
                raise ValueError("No schema bound -- call bind_schema() first")
            self.children = _restructure(self.subrecords, self.schema.members)
        return self.children

    def get_group(self, name: str) -> list:
        """Get the live list of GroupInstances for a named group.

        Returns the actual list -- append, reorder, delete directly.
        Create new instances with GroupInstance.new(group_def).
        """
        self._ensure_children()
        for child in self.children:
            if isinstance(child, list) and child and isinstance(child[0], GroupInstance):
                if child[0].name == name:
                    return child
            elif isinstance(child, list) and not child:
                # Empty list -- need to check schema to find which group this is
                pass
        # Search schema to find empty group lists
        from .defs.types import EspGroup
        for i, member in enumerate(self.schema.members):
            if isinstance(member, EspGroup) and member.name == name:
                # Return the corresponding children entry
                return self.children[i]
        raise KeyError(f"No group named {name!r} in schema")

    def _flatten_children(self) -> List[SubRecord]:
        """Flatten children back to a sorted list of SubRecords for serialization.

        Only sort when the record has been modified. Unmodified records
        preserve original disk order for byte-perfect round-trips.
        """
        if not self.modified:
            return self.subrecords
        if self.schema is not None:
            return _sort_and_flatten(self._ensure_children(), self.schema.members)
        return self.subrecords

    def _serialize_subrecords(self) -> bytes:
        """Serialize all subrecords to bytes (handles XXXX overflow).

        If a schema is bound, flattens children (with hierarchical sort)
        back to an ordered subrecord list. Otherwise uses the flat subrecords
        list as-is.
        """
        writer = BinaryWriter()
        for subrecord in self._flatten_children():
            writer.write_bytes(subrecord.to_bytes())
        return writer.get_bytes()

    @classmethod
    def from_bytes(cls, reader: BinaryReader) -> 'Record':
        """Parse a record from binary data."""
        signature = reader.read_bytes(4).decode('ascii')
        data_size = reader.read_uint32()
        flags = reader.read_uint32()
        form_id = FormID(reader.read_uint32())
        timestamp = reader.read_uint32()
        version = reader.read_uint16()
        version_control_info = reader.read_uint16()

        record = cls(signature, form_id, flags)
        record.timestamp = timestamp
        record.version = version
        record.version_control_info = version_control_info

        # Read the raw data payload
        if data_size == 0:
            return record

        raw_data = reader.read_bytes(data_size)

        # Decompress if needed
        if flags & COMPRESSED_FLAG:
            if len(raw_data) < 4:
                raise ParseError(f"Compressed record {signature} too small for size prefix")
            # Preserve the original compressed payload for verbatim round-trip
            record._original_compressed_payload = raw_data
            uncompressed_size = struct.unpack('<I', raw_data[:4])[0]
            compressed_data = raw_data[4:]
            subrecord_data = decompress_zlib(compressed_data)
            if len(subrecord_data) != uncompressed_size:
                raise ParseError(
                    f"Decompressed size {len(subrecord_data)} != "
                    f"expected {uncompressed_size} for {signature}")
        else:
            subrecord_data = raw_data

        # Parse subrecords with XXXX overflow support
        sub_reader = BinaryReader(subrecord_data)
        pending_xxxx_size = None

        while not sub_reader.at_end():
            if sub_reader.remaining() < 6:
                break

            sub_sig = sub_reader.read_bytes(4).decode('ascii', errors='replace')
            sub_size = sub_reader.read_uint16()

            # Handle XXXX overflow marker
            if sub_sig == 'XXXX':
                if sub_size != 4:
                    raise ParseError(f"XXXX subrecord should have size 4, got {sub_size}")
                pending_xxxx_size = struct.unpack('<I', sub_reader.read_bytes(4))[0]
                continue

            # Use XXXX size if pending
            actual_size = sub_size
            if pending_xxxx_size is not None:
                actual_size = pending_xxxx_size
                pending_xxxx_size = None

            if sub_reader.remaining() < actual_size:
                raise ParseError(
                    f"Subrecord {sub_sig} size {actual_size} "
                    f"exceeds remaining data {sub_reader.remaining()}")

            sub_data = sub_reader.read_bytes(actual_size)
            record.subrecords.append(SubRecord(sub_sig, sub_data))

        return record

    def to_bytes(self) -> bytes:
        """Convert record to binary format."""
        writer = BinaryWriter()

        # For compressed records: use original payload if unmodified
        if (self.flags & COMPRESSED_FLAG and
                self._original_compressed_payload is not None and
                not self.modified and
                not any(sr.modified for sr in self.subrecords)):
            payload = self._original_compressed_payload
        elif self.flags & COMPRESSED_FLAG:
            subrecord_bytes = self._serialize_subrecords()
            uncompressed_size = len(subrecord_bytes)
            compressed = compress_zlib(subrecord_bytes)
            payload = struct.pack('<I', uncompressed_size) + compressed
        else:
            payload = self._serialize_subrecords()

        # Write record header
        writer.write_bytes(self.signature.encode('ascii'))
        writer.write_uint32(len(payload))
        writer.write_uint32(self.flags)
        writer.write_form_id(self.form_id)
        writer.write_uint32(self.timestamp)
        writer.write_uint16(self.version)
        writer.write_uint16(self.version_control_info)

        # Write payload
        writer.write_bytes(payload)

        return writer.get_bytes()

    def __str__(self) -> str:
        editor_id = self.editor_id or "<no EDID>"
        return f"Record({self.signature}, {self.form_id}, {editor_id})"

    def __repr__(self) -> str:
        return (f"Record(signature='{self.signature}', form_id={self.form_id!r}, "
                f"flags=0x{self.flags:08X}, subrecords={len(self.subrecords)})")


def _restructure(subrecords: List[SubRecord], members: list) -> List[ChildEntry]:
    """Restructure a flat subrecord list into a children list matching schema members.

    Processes sequentially: walks through the subrecord list once, matching
    each subrecord to the current or next schema member. This ensures that
    when the same signature (e.g. MNAM) appears in multiple groups, each
    group only consumes sigs at its position in the sequence.
    """
    from .defs.types import EspGroup, EspSubRecord

    # Initialize children: one slot per member
    children: List[ChildEntry] = []
    for member in members:
        if isinstance(member, EspGroup):
            children.append([])  # list[GroupInstance]
        else:
            children.append(None)  # will be SubRecord or list[SubRecord]

    # Build lookup: for each member, what sigs does it accept?
    member_accepts: list[set[str]] = []
    member_leaders: list[Optional[str]] = []  # leader sig for groups
    for member in members:
        if isinstance(member, EspGroup):
            flat = member.flat_subrecords()
            member_accepts.append({sr.signature for sr in flat})
            member_leaders.append(flat[0].signature if flat else None)
        else:
            member_accepts.append({member.signature})
            member_leaders.append(None)

    # All sigs accepted by any member
    all_known = set()
    for s in member_accepts:
        all_known |= s

    # Walk subrecords sequentially, consuming into the current member
    pos = 0  # position in subrecords
    mi = 0   # current member index
    subs = subrecords

    while pos < len(subs):
        sig = subs[pos].signature

        # Find which member (at or after mi) accepts this sig
        found_mi = None
        for candidate in range(mi, len(members)):
            if sig in member_accepts[candidate]:
                found_mi = candidate
                break

        if found_mi is None:
            # Sig doesn't match any remaining member.
            # Check if it matches an earlier member (repeat of a sig like KWDA
            # that we already passed).
            for candidate in range(mi):
                if sig in member_accepts[candidate]:
                    found_mi = candidate
                    break

        if found_mi is None:
            # Unknown subrecord -- append at end
            children.append(subs[pos])
            pos += 1
            continue

        mi = found_mi
        member = members[mi]

        if isinstance(member, EspGroup):
            leader = member_leaders[mi]
            group_sigs = member_accepts[mi]

            if sig == leader:
                # Start a new group instance
                instance_subs = [subs[pos]]
                pos += 1
                while pos < len(subs):
                    s = subs[pos].signature
                    if s not in group_sigs or s == leader:
                        break
                    instance_subs.append(subs[pos])
                    pos += 1
                inst = GroupInstance(member)
                inst.children = _restructure(instance_subs, member.members)
                children[mi].append(inst)
                # Don't advance mi -- more instances of same group may follow
            else:
                # Non-leader sig that belongs to this group but appeared
                # without a leader. Treat as unknown.
                children.append(subs[pos])
                pos += 1
        else:
            # EspSubRecord: consume this subrecord
            existing = children[mi]
            if existing is None:
                children[mi] = subs[pos]
            elif isinstance(existing, SubRecord):
                children[mi] = [existing, subs[pos]]
            else:
                existing.append(subs[pos])
            pos += 1
            # Advance mi to next member (unless this sig can repeat)
            # We stay at mi if the next subrecord also matches this member

    return children


def _sort_and_flatten(children: List[ChildEntry], members: list) -> List[SubRecord]:
    """Flatten a children list back to sorted SubRecords for serialization.

    At this level:
    - SubRecord entries are sorted by their schema member position
    - list[GroupInstance] entries are placed at their schema position as a block
    - Within each GroupInstance, sort recursively by group member order
    - Order of GroupInstances within a list is preserved (caller's responsibility)
    - Unknown entries (past the schema member count) go at the end
    """
    from .defs.types import EspGroup

    result: list[tuple[int, list[SubRecord]]] = []

    for i, child in enumerate(children):
        if child is None:
            continue
        elif isinstance(child, SubRecord):
            result.append((i, [child]))
        elif isinstance(child, list):
            if not child:
                continue
            if isinstance(child[0], GroupInstance):
                # Flatten each instance, preserving instance order
                flat = []
                for inst in child:
                    if i < len(members):
                        flat.extend(inst.flatten())
                    else:
                        flat.extend(_collect_subrecords(inst))
                result.append((i, flat))
            else:
                # list[SubRecord] (repeating ungrouped sig)
                result.append((i, child))

    result.sort(key=lambda t: t[0])
    return [sr for _, srs in result for sr in srs]


def _collect_subrecords(inst: GroupInstance) -> List[SubRecord]:
    """Recursively collect all SubRecords from a GroupInstance without sorting."""
    result = []
    for child in inst.children:
        if isinstance(child, SubRecord):
            result.append(child)
        elif isinstance(child, list):
            for sub_inst in child:
                if isinstance(sub_inst, GroupInstance):
                    result.extend(_collect_subrecords(sub_inst))
        elif isinstance(child, GroupInstance):
            result.extend(_collect_subrecords(child))
    return result


class GroupRecord:
    """Represents a GRUP record that contains other records."""

    def __init__(self, group_type: int = 0, label: Union[str, int] = 0):
        self.group_type = group_type
        self.label = label
        self.timestamp: int = 0
        self.version: int = 0
        self.version_control_info: int = 0
        self.records: List[Union[Record, 'GroupRecord']] = []
        self.modified = False

    def add_record(self, record: Union[Record, 'GroupRecord']) -> None:
        self.records.append(record)
        self.modified = True

    def remove_record(self, record: Union[Record, 'GroupRecord']) -> bool:
        if record in self.records:
            self.records.remove(record)
            self.modified = True
            return True
        return False

    @classmethod
    def from_bytes(cls, reader: BinaryReader) -> 'GroupRecord':
        """Parse a group record from binary data."""
        start_position = reader.tell()

        signature = reader.read_bytes(4)
        if signature != b'GRUP':
            raise ParseError(f"Expected GRUP signature, got {signature}")

        group_size = reader.read_uint32()
        label_bytes = reader.read_bytes(4)
        group_type = reader.read_int32()
        timestamp = reader.read_uint32()
        version = reader.read_uint16()
        version_control_info = reader.read_uint16()

        # Determine label based on group type
        if group_type == 0:
            label = label_bytes.decode('ascii', errors='replace').rstrip('\x00')
        else:
            label = struct.unpack('<I', label_bytes)[0]

        group = cls(group_type, label)
        group.timestamp = timestamp
        group.version = version
        group.version_control_info = version_control_info

        # Read records using offset-based end detection
        end_position = start_position + group_size

        while reader.tell() < end_position:
            if reader.remaining() < 4:
                break

            next_sig = reader.data[reader.position:reader.position + 4]

            if next_sig == b'GRUP':
                subgroup = GroupRecord.from_bytes(reader)
                group.records.append(subgroup)
            else:
                record = Record.from_bytes(reader)
                group.records.append(record)

        return group

    def to_bytes(self) -> bytes:
        """Convert group to binary format."""
        # Serialize all contained records first
        content = bytearray()
        for record in self.records:
            content.extend(record.to_bytes())

        writer = BinaryWriter()
        writer.write_bytes(b'GRUP')
        writer.write_uint32(24 + len(content))  # group_size includes header

        if isinstance(self.label, str):
            label_bytes = self.label.encode('ascii')[:4].ljust(4, b'\x00')
        else:
            label_bytes = struct.pack('<I', self.label)
        writer.write_bytes(label_bytes)

        writer.write_int32(self.group_type)
        writer.write_uint32(self.timestamp)
        writer.write_uint16(self.version)
        writer.write_uint16(self.version_control_info)

        writer.write_bytes(content)

        return writer.get_bytes()

    def __str__(self) -> str:
        return f"GroupRecord({self.group_type}, {self.label}, {len(self.records)} records)"

    def __repr__(self) -> str:
        return (f"GroupRecord(group_type={self.group_type}, label={self.label!r}, "
                f"records={len(self.records)})")
