"""VMAD (Virtual Machine Adapter) subrecord parser.

Reads and writes Papyrus script data attached to records. The VMAD
subrecord appears on QUST, PERK, PACK, INFO, SCEN, and many other
record types.

Binary format reference:
    http://www.uesp.net/wiki/Tes5Mod:Mod_File_Format/VMAD_Field
    xEdit: wbDefinitionsTES5.pas (wbScriptEntry, wbScriptProperty, etc.)

Supports:
    - All property types (Object, String, Int32, Float, Bool + arrays)
    - Object format v1 and v2
    - Fragment data for QUST, PERK, PACK, INFO, SCEN
    - QUST alias scripts
    - Round-trip read/write (byte-identical serialization)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, Optional


# Property type constants
PROP_NONE = 0
PROP_OBJECT = 1
PROP_STRING = 2
PROP_INT32 = 3
PROP_FLOAT = 4
PROP_BOOL = 5
PROP_OBJECT_ARRAY = 11
PROP_STRING_ARRAY = 12
PROP_INT32_ARRAY = 13
PROP_FLOAT_ARRAY = 14
PROP_BOOL_ARRAY = 15


@dataclass
class VmadObject:
    """Object reference in VMAD (FormID + alias)."""
    form_id: int = 0
    alias: int = -1
    unused: int = 0


@dataclass
class VmadProperty:
    """A single script property."""
    name: str = ''
    type: int = 0
    flags: int = 1  # 1 = Edited
    value: Any = None


@dataclass
class VmadScript:
    """A script attached to a record."""
    name: str = ''
    flags: int = 0  # 0=Local, 1=Inherited, 2=Removed
    properties: list[VmadProperty] = field(default_factory=list)

    def get_property(self, name: str) -> Optional[VmadProperty]:
        """Find a property by name (case-insensitive)."""
        name_lower = name.lower()
        for prop in self.properties:
            if prop.name.lower() == name_lower:
                return prop
        return None


@dataclass
class VmadFragment:
    """A single script fragment."""
    script_name: str = ''
    fragment_name: str = ''
    unknown: int = 0


@dataclass
class VmadQuestFragment(VmadFragment):
    """Quest-specific fragment with stage info."""
    quest_stage: int = 0
    unknown2: int = 0
    quest_stage_index: int = 0


@dataclass
class VmadScenePhaseFragment:
    """Scene phase fragment."""
    phase_flag: int = 0
    phase_index: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    script_name: str = ''
    fragment_name: str = ''


@dataclass
class VmadFragmentData:
    """Fragment data section (type depends on record signature)."""
    extra_bind_version: int = 2
    filename: str = ''
    fragments: list = field(default_factory=list)
    # QUST-specific
    fragment_count: int = 0
    # INFO/PACK/SCEN-specific
    flags: int = 0
    # SCEN-specific
    phase_fragments: list[VmadScenePhaseFragment] = field(default_factory=list)


@dataclass
class VmadAliasScripts:
    """QUST alias script block."""
    alias_obj: VmadObject = field(default_factory=VmadObject)
    version: int = 5
    obj_format: int = 2
    scripts: list[VmadScript] = field(default_factory=list)


@dataclass
class VmadData:
    """Parsed VMAD subrecord data."""
    version: int = 5
    obj_format: int = 2
    scripts: list[VmadScript] = field(default_factory=list)
    fragment_data: Optional[VmadFragmentData] = None
    alias_scripts: list[VmadAliasScripts] = field(default_factory=list)

    def get_script(self, name: str) -> Optional[VmadScript]:
        """Find a script by name (case-insensitive)."""
        name_lower = name.lower()
        for script in self.scripts:
            if script.name.lower() == name_lower:
                return script
        return None

    @classmethod
    def from_record(cls, record, sig: str = None) -> Optional['VmadData']:
        """Parse VMAD from a record's VMAD subrecord.

        sig: record signature (e.g. 'QUST') for correct fragment parsing.
             If None, uses record.signature.
        """
        vmad_sr = record.get_subrecord('VMAD')
        if vmad_sr is None:
            return None
        record_sig = sig or record.signature
        return cls.parse(vmad_sr.data, record_sig)

    @classmethod
    def parse(cls, data: bytes, record_sig: str = None) -> 'VmadData':
        """Parse VMAD from raw bytes."""
        r = _Reader(data)
        vmad = cls()
        vmad.version = r.int16()
        vmad.obj_format = r.int16()

        script_count = r.uint16()
        for _ in range(script_count):
            vmad.scripts.append(_read_script(r, vmad.obj_format))

        # Parse fragment data if there's remaining data and we know the type
        if record_sig and r.remaining() > 0:
            vmad.fragment_data = _read_fragments(r, record_sig, vmad.obj_format)

            # QUST has alias scripts after fragments
            if record_sig == 'QUST' and r.remaining() > 0:
                alias_count = r.uint16()
                for _ in range(alias_count):
                    vmad.alias_scripts.append(
                        _read_alias_scripts(r, vmad.obj_format))

        return vmad

    def to_bytes(self, record_sig: str = None) -> bytes:
        """Serialize VMAD back to bytes."""
        w = _Writer()
        w.int16(self.version)
        w.int16(self.obj_format)
        w.uint16(len(self.scripts))
        for script in self.scripts:
            _write_script(w, script, self.obj_format)

        if self.fragment_data is not None and record_sig:
            _write_fragments(w, self.fragment_data, record_sig,
                             self.obj_format)

            if record_sig == 'QUST':
                w.uint16(len(self.alias_scripts))
                for alias in self.alias_scripts:
                    _write_alias_scripts(w, alias, self.obj_format)

        return w.get_bytes()


# ---- Internal reader/writer helpers ----

class _Reader:

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def uint8(self) -> int:
        val = self._data[self._pos]
        self._pos += 1
        return val

    def int8(self) -> int:
        val = struct.unpack_from('<b', self._data, self._pos)[0]
        self._pos += 1
        return val

    def uint16(self) -> int:
        val = struct.unpack_from('<H', self._data, self._pos)[0]
        self._pos += 2
        return val

    def int16(self) -> int:
        val = struct.unpack_from('<h', self._data, self._pos)[0]
        self._pos += 2
        return val

    def uint32(self) -> int:
        val = struct.unpack_from('<I', self._data, self._pos)[0]
        self._pos += 4
        return val

    def int32(self) -> int:
        val = struct.unpack_from('<i', self._data, self._pos)[0]
        self._pos += 4
        return val

    def float32(self) -> float:
        val = struct.unpack_from('<f', self._data, self._pos)[0]
        self._pos += 4
        return val

    def wstring(self) -> str:
        """Read a uint16-length-prefixed string."""
        length = self.uint16()
        raw = self._data[self._pos:self._pos + length]
        self._pos += length
        return raw.decode('utf-8', errors='replace')


class _Writer:

    def __init__(self):
        self._parts: list[bytes] = []

    def get_bytes(self) -> bytes:
        return b''.join(self._parts)

    def uint8(self, val: int):
        self._parts.append(struct.pack('<B', val))

    def int8(self, val: int):
        self._parts.append(struct.pack('<b', val))

    def uint16(self, val: int):
        self._parts.append(struct.pack('<H', val))

    def int16(self, val: int):
        self._parts.append(struct.pack('<h', val))

    def uint32(self, val: int):
        self._parts.append(struct.pack('<I', val))

    def int32(self, val: int):
        self._parts.append(struct.pack('<i', val))

    def float32(self, val: float):
        self._parts.append(struct.pack('<f', val))

    def wstring(self, val: str):
        """Write a uint16-length-prefixed string."""
        encoded = val.encode('utf-8')
        self.uint16(len(encoded))
        self._parts.append(encoded)


# ---- Script reading/writing ----

def _read_object(r: _Reader, obj_format: int) -> VmadObject:
    obj = VmadObject()
    if obj_format >= 2:
        obj.unused = r.uint16()
        obj.alias = r.int16()
        obj.form_id = r.uint32()
    else:
        obj.form_id = r.uint32()
        obj.alias = r.int16()
        obj.unused = r.uint16()
    return obj


def _write_object(w: _Writer, obj: VmadObject, obj_format: int):
    if obj_format >= 2:
        w.uint16(obj.unused)
        w.int16(obj.alias)
        w.uint32(obj.form_id)
    else:
        w.uint32(obj.form_id)
        w.int16(obj.alias)
        w.uint16(obj.unused)


def _read_property_value(r: _Reader, prop_type: int,
                         obj_format: int) -> Any:
    if prop_type == PROP_NONE:
        return None
    elif prop_type == PROP_OBJECT:
        return _read_object(r, obj_format)
    elif prop_type == PROP_STRING:
        return r.wstring()
    elif prop_type == PROP_INT32:
        return r.int32()
    elif prop_type == PROP_FLOAT:
        return r.float32()
    elif prop_type == PROP_BOOL:
        return bool(r.uint8())
    elif prop_type == PROP_OBJECT_ARRAY:
        count = r.uint32()
        return [_read_object(r, obj_format) for _ in range(count)]
    elif prop_type == PROP_STRING_ARRAY:
        count = r.uint32()
        return [r.wstring() for _ in range(count)]
    elif prop_type == PROP_INT32_ARRAY:
        count = r.uint32()
        return [r.int32() for _ in range(count)]
    elif prop_type == PROP_FLOAT_ARRAY:
        count = r.uint32()
        return [r.float32() for _ in range(count)]
    elif prop_type == PROP_BOOL_ARRAY:
        count = r.uint32()
        return [bool(r.uint8()) for _ in range(count)]
    else:
        raise ValueError(f"Unknown VMAD property type: {prop_type}")


def _write_property_value(w: _Writer, prop_type: int, value: Any,
                          obj_format: int):
    if prop_type == PROP_NONE:
        pass
    elif prop_type == PROP_OBJECT:
        _write_object(w, value, obj_format)
    elif prop_type == PROP_STRING:
        w.wstring(value)
    elif prop_type == PROP_INT32:
        w.int32(value)
    elif prop_type == PROP_FLOAT:
        w.float32(value)
    elif prop_type == PROP_BOOL:
        w.uint8(1 if value else 0)
    elif prop_type == PROP_OBJECT_ARRAY:
        w.uint32(len(value))
        for obj in value:
            _write_object(w, obj, obj_format)
    elif prop_type == PROP_STRING_ARRAY:
        w.uint32(len(value))
        for s in value:
            w.wstring(s)
    elif prop_type == PROP_INT32_ARRAY:
        w.uint32(len(value))
        for v in value:
            w.int32(v)
    elif prop_type == PROP_FLOAT_ARRAY:
        w.uint32(len(value))
        for v in value:
            w.float32(v)
    elif prop_type == PROP_BOOL_ARRAY:
        w.uint32(len(value))
        for v in value:
            w.uint8(1 if v else 0)


def _read_script(r: _Reader, obj_format: int) -> VmadScript:
    script = VmadScript()
    script.name = r.wstring()
    script.flags = r.uint8()
    prop_count = r.uint16()
    for _ in range(prop_count):
        prop = VmadProperty()
        prop.name = r.wstring()
        prop.type = r.uint8()
        prop.flags = r.uint8()
        prop.value = _read_property_value(r, prop.type, obj_format)
        script.properties.append(prop)
    return script


def _write_script(w: _Writer, script: VmadScript, obj_format: int):
    w.wstring(script.name)
    w.uint8(script.flags)
    w.uint16(len(script.properties))
    for prop in script.properties:
        w.wstring(prop.name)
        w.uint8(prop.type)
        w.uint8(prop.flags)
        _write_property_value(w, prop.type, prop.value, obj_format)


# ---- Fragment reading/writing ----

def _read_basic_fragment(r: _Reader) -> VmadFragment:
    frag = VmadFragment()
    frag.unknown = r.int8()
    frag.script_name = r.wstring()
    frag.fragment_name = r.wstring()
    return frag


def _write_basic_fragment(w: _Writer, frag: VmadFragment):
    w.int8(frag.unknown)
    w.wstring(frag.script_name)
    w.wstring(frag.fragment_name)


def _count_flag_bits(flags: int, num_bits: int = 8) -> int:
    """Count set bits in a flags byte."""
    count = 0
    for i in range(num_bits):
        if flags & (1 << i):
            count += 1
    return count


def _read_fragments(r: _Reader, record_sig: str,
                    obj_format: int) -> VmadFragmentData:
    fd = VmadFragmentData()
    fd.extra_bind_version = r.int8()

    if record_sig == 'QUST':
        fd.fragment_count = r.uint16()
        fd.filename = r.wstring()
        for _ in range(fd.fragment_count):
            frag = VmadQuestFragment()
            frag.quest_stage = r.uint16()
            frag.unknown2 = r.int16()
            frag.quest_stage_index = r.int32()
            frag.unknown = r.int8()
            frag.script_name = r.wstring()
            frag.fragment_name = r.wstring()
            fd.fragments.append(frag)

    elif record_sig == 'INFO':
        fd.flags = r.uint8()
        fd.filename = r.wstring()
        frag_count = _count_flag_bits(fd.flags, 3)
        for _ in range(frag_count):
            fd.fragments.append(_read_basic_fragment(r))

    elif record_sig == 'PACK':
        fd.flags = r.uint8()
        fd.filename = r.wstring()
        frag_count = _count_flag_bits(fd.flags, 3)
        for _ in range(frag_count):
            fd.fragments.append(_read_basic_fragment(r))

    elif record_sig == 'PERK':
        fd.filename = r.wstring()
        frag_count = r.uint16()
        for _ in range(frag_count):
            frag = VmadFragment()
            frag.unknown = r.uint16()  # Fragment Index (uint16 for PERK)
            unknown2 = r.int16()
            unknown3 = r.int8()
            frag.script_name = r.wstring()
            frag.fragment_name = r.wstring()
            # Store extra unknowns in a tuple for round-trip
            frag._perk_extra = (unknown2, unknown3)
            fd.fragments.append(frag)

    elif record_sig == 'SCEN':
        fd.flags = r.uint8()
        fd.filename = r.wstring()
        frag_count = _count_flag_bits(fd.flags, 3)
        for _ in range(frag_count):
            fd.fragments.append(_read_basic_fragment(r))
        # Phase fragments
        phase_count = r.uint16()
        for _ in range(phase_count):
            pf = VmadScenePhaseFragment()
            pf.phase_flag = r.uint8()
            pf.phase_index = r.uint8()
            pf.unknown1 = r.int16()
            pf.unknown2 = r.int8()
            pf.unknown3 = r.int8()
            pf.script_name = r.wstring()
            pf.fragment_name = r.wstring()
            fd.phase_fragments.append(pf)

    return fd


def _write_fragments(w: _Writer, fd: VmadFragmentData, record_sig: str,
                     obj_format: int):
    w.int8(fd.extra_bind_version)

    if record_sig == 'QUST':
        w.uint16(fd.fragment_count)
        w.wstring(fd.filename)
        for frag in fd.fragments:
            w.uint16(frag.quest_stage)
            w.int16(frag.unknown2)
            w.int32(frag.quest_stage_index)
            w.int8(frag.unknown)
            w.wstring(frag.script_name)
            w.wstring(frag.fragment_name)

    elif record_sig == 'INFO':
        w.uint8(fd.flags)
        w.wstring(fd.filename)
        for frag in fd.fragments:
            _write_basic_fragment(w, frag)

    elif record_sig == 'PACK':
        w.uint8(fd.flags)
        w.wstring(fd.filename)
        for frag in fd.fragments:
            _write_basic_fragment(w, frag)

    elif record_sig == 'PERK':
        w.wstring(fd.filename)
        w.uint16(len(fd.fragments))
        for frag in fd.fragments:
            w.uint16(frag.unknown)  # Fragment Index
            extra = getattr(frag, '_perk_extra', (0, 0))
            w.int16(extra[0])
            w.int8(extra[1])
            w.wstring(frag.script_name)
            w.wstring(frag.fragment_name)

    elif record_sig == 'SCEN':
        w.uint8(fd.flags)
        w.wstring(fd.filename)
        for frag in fd.fragments:
            _write_basic_fragment(w, frag)
        w.uint16(len(fd.phase_fragments))
        for pf in fd.phase_fragments:
            w.uint8(pf.phase_flag)
            w.uint8(pf.phase_index)
            w.int16(pf.unknown1)
            w.int8(pf.unknown2)
            w.int8(pf.unknown3)
            w.wstring(pf.script_name)
            w.wstring(pf.fragment_name)


def _read_alias_scripts(r: _Reader, parent_obj_format: int) -> VmadAliasScripts:
    alias = VmadAliasScripts()
    alias.alias_obj = _read_object(r, parent_obj_format)
    alias.version = r.int16()
    alias.obj_format = r.int16()
    script_count = r.uint16()
    for _ in range(script_count):
        alias.scripts.append(_read_script(r, alias.obj_format))
    return alias


def _write_alias_scripts(w: _Writer, alias: VmadAliasScripts,
                         parent_obj_format: int):
    _write_object(w, alias.alias_obj, parent_obj_format)
    w.int16(alias.version)
    w.int16(alias.obj_format)
    w.uint16(len(alias.scripts))
    for script in alias.scripts:
        _write_script(w, script, alias.obj_format)
