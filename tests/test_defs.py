"""Tests for the schema/definition system."""

import struct
import pytest

from esplib.defs import (
    IntType, EspFlags, EspEnum,
    EspInteger, EspFloat, EspString, EspFormID, EspByteArray,
    EspStruct, EspArray, EspUnion,
    EspSubRecord, EspRecord, EspContext,
)
from esplib.utils import BinaryReader, FormID
from esplib.record import Record, SubRecord


# ---------------------------------------------------------------------------
# EspFlags
# ---------------------------------------------------------------------------

class TestEspFlags:
    def test_decode(self):
        flags = EspFlags.new({0: 'Playable', 1: 'Non-Equippable', 4: 'Special'})
        result = flags.decode(0b10001)  # bits 0 and 4
        assert result['Playable'] is True
        assert result['Non-Equippable'] is False
        assert result['Special'] is True

    def test_encode_from_set(self):
        flags = EspFlags.new({0: 'A', 1: 'B', 2: 'C'})
        assert flags.encode({'A', 'C'}) == 0b101

    def test_encode_from_dict(self):
        flags = EspFlags.new({0: 'A', 1: 'B'})
        assert flags.encode({'A': True, 'B': False}) == 1

    def test_encode_passthrough_int(self):
        flags = EspFlags.new({0: 'A'})
        assert flags.encode(42) == 42

    def test_roundtrip_dict(self):
        flags = EspFlags.new({0: 'X', 3: 'Y'})
        d = flags.to_dict()
        flags2 = EspFlags.from_dict(d)
        assert flags2.names == flags.names


# ---------------------------------------------------------------------------
# EspEnum
# ---------------------------------------------------------------------------

class TestEspEnum:
    def test_decode_known(self):
        enum = EspEnum.new({0: 'None', 1: 'Sword', 2: 'Axe'})
        assert enum.decode(1) == 'Sword'

    def test_decode_unknown(self):
        enum = EspEnum.new({0: 'None'})
        assert 'Unknown' in enum.decode(99)

    def test_encode_by_name(self):
        enum = EspEnum.new({0: 'None', 1: 'Sword'})
        assert enum.encode('Sword') == 1

    def test_encode_passthrough_int(self):
        enum = EspEnum.new({0: 'None'})
        assert enum.encode(5) == 5

    def test_encode_unknown_name_raises(self):
        enum = EspEnum.new({0: 'None'})
        with pytest.raises(ValueError):
            enum.encode('Blaster')

    def test_roundtrip_dict(self):
        enum = EspEnum.new({0: 'A', 1: 'B'})
        d = enum.to_dict()
        enum2 = EspEnum.from_dict(d)
        assert enum2.values == enum.values


# ---------------------------------------------------------------------------
# EspInteger
# ---------------------------------------------------------------------------

class TestEspInteger:
    def test_uint8(self):
        defn = EspInteger.new('val', IntType.U8)
        reader = BinaryReader(b'\xFF')
        assert defn.from_bytes(reader) == 255
        assert defn.to_bytes(255) == b'\xFF'

    def test_int32(self):
        defn = EspInteger.new('val', IntType.S32)
        data = struct.pack('<i', -42)
        reader = BinaryReader(data)
        assert defn.from_bytes(reader) == -42
        assert defn.to_bytes(-42) == data

    def test_uint16(self):
        defn = EspInteger.new('val', IntType.U16)
        data = struct.pack('<H', 1000)
        reader = BinaryReader(data)
        assert defn.from_bytes(reader) == 1000
        assert defn.to_bytes(1000) == data

    def test_uint64(self):
        defn = EspInteger.new('val', IntType.U64)
        data = struct.pack('<Q', 2**40)
        reader = BinaryReader(data)
        assert defn.from_bytes(reader) == 2**40

    def test_with_enum_formatter(self):
        enum = EspEnum.new({0: 'None', 1: 'Sword', 2: 'Axe'})
        defn = EspInteger.new('type', IntType.U8, formatter=enum)
        reader = BinaryReader(b'\x01')
        val = defn.from_bytes(reader)
        assert val == 1
        assert enum.decode(val) == 'Sword'

    def test_to_bytes_with_enum_encode(self):
        enum = EspEnum.new({0: 'None', 1: 'Sword'})
        defn = EspInteger.new('type', IntType.U8, formatter=enum)
        assert defn.to_bytes('Sword') == b'\x01'

    def test_roundtrip_all_types(self):
        for it in IntType:
            defn = EspInteger.new('x', it)
            val = 42 if it.fmt.isupper() or it.fmt == 'b' else -1
            if it == IntType.S8:
                val = -1
            data = defn.to_bytes(val)
            reader = BinaryReader(data)
            assert defn.from_bytes(reader) == val


# ---------------------------------------------------------------------------
# EspFloat
# ---------------------------------------------------------------------------

class TestEspFloat:
    def test_roundtrip(self):
        defn = EspFloat.new('weight')
        data = struct.pack('<f', 3.14)
        reader = BinaryReader(data)
        val = defn.from_bytes(reader)
        assert abs(val - 3.14) < 0.001
        assert defn.to_bytes(val) == data

    def test_zero(self):
        defn = EspFloat.new('x')
        data = defn.to_bytes(0.0)
        assert EspFloat.new('x').from_bytes(BinaryReader(data)) == 0.0


# ---------------------------------------------------------------------------
# EspString
# ---------------------------------------------------------------------------

class TestEspString:
    def test_zstring(self):
        defn = EspString.new('name', 'zstring')
        data = b'Hello\x00'
        reader = BinaryReader(data)
        assert defn.from_bytes(reader, available=len(data)) == 'Hello'
        assert defn.to_bytes('Hello') == b'Hello\x00'

    def test_lstring(self):
        defn = EspString.new('name', 'lstring')
        text = 'Test'
        data = struct.pack('<H', 4) + b'Test'
        reader = BinaryReader(data)
        assert defn.from_bytes(reader) == 'Test'
        assert defn.to_bytes('Test') == data

    def test_wstring(self):
        defn = EspString.new('name', 'wstring')
        text = 'Wide'
        data = struct.pack('<I', 4) + b'Wide'
        reader = BinaryReader(data)
        assert defn.from_bytes(reader) == 'Wide'
        assert defn.to_bytes('Wide') == data

    def test_empty_zstring(self):
        defn = EspString.new('name', 'zstring')
        assert defn.to_bytes('') == b'\x00'

    def test_zstring_with_fixed_available(self):
        defn = EspString.new('name', 'zstring')
        data = b'Hi\x00\x00\x00'
        reader = BinaryReader(data)
        assert defn.from_bytes(reader, available=5) == 'Hi'


# ---------------------------------------------------------------------------
# EspFormID
# ---------------------------------------------------------------------------

class TestEspFormID:
    def test_roundtrip(self):
        defn = EspFormID.new('race')
        data = struct.pack('<I', 0x00013746)
        reader = BinaryReader(data)
        fid = defn.from_bytes(reader)
        assert isinstance(fid, FormID)
        assert fid.value == 0x00013746
        assert defn.to_bytes(fid) == data

    def test_from_int(self):
        defn = EspFormID.new('race')
        assert defn.to_bytes(0x00013746) == struct.pack('<I', 0x00013746)


# ---------------------------------------------------------------------------
# EspByteArray
# ---------------------------------------------------------------------------

class TestEspByteArray:
    def test_fixed_size(self):
        defn = EspByteArray.new('data', size=8)
        data = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        reader = BinaryReader(data)
        assert defn.from_bytes(reader) == data
        assert defn.to_bytes(data) == data

    def test_remaining(self):
        defn = EspByteArray.new('data')
        data = b'\xAA\xBB\xCC'
        reader = BinaryReader(data)
        assert defn.from_bytes(reader, available=3) == data

    def test_to_bytes_passthrough(self):
        defn = EspByteArray.new('data')
        raw = b'\x00\x01\x02'
        assert defn.to_bytes(raw) == raw


# ---------------------------------------------------------------------------
# EspStruct
# ---------------------------------------------------------------------------

class TestEspStruct:
    def test_simple_struct(self):
        defn = EspStruct.new('weapon_data', [
            EspInteger.new('damage', IntType.U16),
            EspFloat.new('weight'),
            EspInteger.new('value', IntType.U32),
        ])
        data = struct.pack('<H', 15) + struct.pack('<f', 7.5) + struct.pack('<I', 100)
        reader = BinaryReader(data)
        result = defn.from_bytes(reader)

        assert result['damage'] == 15
        assert abs(result['weight'] - 7.5) < 0.001
        assert result['value'] == 100

    def test_struct_roundtrip(self):
        defn = EspStruct.new('data', [
            EspInteger.new('a', IntType.U8),
            EspInteger.new('b', IntType.U32),
            EspFloat.new('c'),
        ])
        original = struct.pack('<B', 10) + struct.pack('<I', 200) + struct.pack('<f', 1.5)
        reader = BinaryReader(original)
        values = defn.from_bytes(reader)
        output = defn.to_bytes(values)
        assert output == original

    def test_nested_struct(self):
        inner = EspStruct.new('pos', [
            EspFloat.new('x'),
            EspFloat.new('y'),
            EspFloat.new('z'),
        ])
        outer = EspStruct.new('placement', [
            EspFormID.new('base'),
            inner,
        ])
        data = struct.pack('<I', 0x12345678)
        data += struct.pack('<fff', 1.0, 2.0, 3.0)

        reader = BinaryReader(data)
        result = outer.from_bytes(reader)

        assert result['base'].value == 0x12345678
        assert result['pos']['x'] == 1.0
        assert result['pos']['z'] == 3.0


# ---------------------------------------------------------------------------
# EspArray
# ---------------------------------------------------------------------------

class TestEspArray:
    def test_fixed_count(self):
        defn = EspArray.new('items', EspFormID.new('ref'), count=3)
        data = struct.pack('<III', 0x100, 0x200, 0x300)
        reader = BinaryReader(data)
        result = defn.from_bytes(reader)

        assert len(result) == 3
        assert result[0].value == 0x100
        assert result[2].value == 0x300

    def test_exhaustive(self):
        defn = EspArray.new('items', EspFormID.new('ref'))
        data = struct.pack('<II', 0xAAA, 0xBBB)
        reader = BinaryReader(data)
        result = defn.from_bytes(reader, available=8)

        assert len(result) == 2

    def test_roundtrip(self):
        defn = EspArray.new('vals', EspInteger.new('v', IntType.U16), count=4)
        data = struct.pack('<HHHH', 10, 20, 30, 40)
        reader = BinaryReader(data)
        values = defn.from_bytes(reader)
        output = defn.to_bytes(values)
        assert output == data

    def test_resolved_count(self):
        defn = EspArray.new('items', EspInteger.new('v', IntType.U8))
        data = b'\x01\x02\x03'
        reader = BinaryReader(data)
        result = defn.from_bytes(reader, resolved_count=2)
        assert result == [1, 2]


# ---------------------------------------------------------------------------
# EspUnion
# ---------------------------------------------------------------------------

class TestEspUnion:
    def test_basic_union(self):
        defn = EspUnion.new(
            'value',
            decider=lambda ctx: 0 if ctx.form_version < 40 else 1,
            members=[
                EspInteger.new('old_val', IntType.U16),
                EspInteger.new('new_val', IntType.U32),
            ],
        )
        # Old version
        ctx_old = EspContext(form_version=39)
        reader = BinaryReader(struct.pack('<H', 100))
        assert defn.from_bytes(reader, ctx_old) == 100

        # New version
        ctx_new = EspContext(form_version=44)
        reader = BinaryReader(struct.pack('<I', 99999))
        assert defn.from_bytes(reader, ctx_new) == 99999

    def test_union_with_structs(self):
        defn = EspUnion.new(
            'data',
            decider=lambda ctx: ctx.extra.get('variant', 0),
            members=[
                EspStruct.new('v1', [EspInteger.new('a', IntType.U8)]),
                EspStruct.new('v2', [
                    EspInteger.new('a', IntType.U16),
                    EspInteger.new('b', IntType.U16),
                ]),
            ],
        )
        ctx = EspContext(extra={'variant': 1})
        data = struct.pack('<HH', 10, 20)
        reader = BinaryReader(data)
        result = defn.from_bytes(reader, ctx)
        assert result == {'a': 10, 'b': 20}

    def test_invalid_index_raises(self):
        defn = EspUnion.new(
            'x',
            decider=lambda ctx: 5,
            members=[EspInteger.new('a', IntType.U8)],
        )
        with pytest.raises(Exception):
            defn.from_bytes(BinaryReader(b'\x00'), EspContext())


# ---------------------------------------------------------------------------
# EspSubRecord
# ---------------------------------------------------------------------------

class TestEspSubRecord:
    def test_from_subrecord(self):
        defn = EspSubRecord.new('DATA', 'Damage', EspInteger.new('damage', IntType.U16))
        sr = SubRecord('DATA', struct.pack('<H', 42))
        assert defn.from_subrecord(sr) == 42

    def test_to_subrecord_data(self):
        defn = EspSubRecord.new('DATA', 'Damage', EspInteger.new('damage', IntType.U16))
        data = defn.to_subrecord_data(42)
        assert data == struct.pack('<H', 42)

    def test_struct_subrecord(self):
        defn = EspSubRecord.new('DATA', 'Weapon Data', EspStruct.new('data', [
            EspInteger.new('damage', IntType.U16),
            EspFloat.new('weight'),
            EspInteger.new('value', IntType.U32),
        ]))
        raw = struct.pack('<H', 15) + struct.pack('<f', 7.5) + struct.pack('<I', 100)
        sr = SubRecord('DATA', raw)
        result = defn.from_subrecord(sr)

        assert result['damage'] == 15
        assert abs(result['weight'] - 7.5) < 0.001
        assert result['value'] == 100

        # Round-trip
        output = defn.to_subrecord_data(result)
        assert output == raw


# ---------------------------------------------------------------------------
# EspRecord
# ---------------------------------------------------------------------------

class TestEspRecord:
    def _make_weapon_schema(self):
        return EspRecord.new('WEAP', 'Weapon', [
            EspSubRecord.new('EDID', 'Editor ID',
                             EspString.new('edid', 'zstring')),
            EspSubRecord.new('FULL', 'Name',
                             EspString.new('name', 'lstring')),
            EspSubRecord.new('DATA', 'Data', EspStruct.new('data', [
                EspInteger.new('damage', IntType.U16),
                EspFloat.new('weight'),
                EspInteger.new('value', IntType.U32),
            ])),
            EspSubRecord.new('KWDA', 'Keywords',
                             EspArray.new('keywords', EspFormID.new('kw'))),
        ])

    def test_from_record(self):
        schema = self._make_weapon_schema()

        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'IronSword\x00')
        record.add_subrecord('FULL', struct.pack('<H', 10) + b'Iron Sword')
        record.add_subrecord('DATA',
                             struct.pack('<H', 7) +
                             struct.pack('<f', 9.0) +
                             struct.pack('<I', 25))
        record.add_subrecord('KWDA', struct.pack('<II', 0x1E711, 0x1E712))

        result = schema.from_record(record)

        assert result['Editor ID'] == 'IronSword'
        assert result['Name'] == 'Iron Sword'
        assert result['Data']['damage'] == 7
        assert abs(result['Data']['weight'] - 9.0) < 0.001
        assert result['Data']['value'] == 25
        assert len(result['Keywords']) == 2
        assert result['Keywords'][0].value == 0x1E711

    def test_unknown_subrecords_skipped(self):
        schema = EspRecord.new('WEAP', 'Weapon', [
            EspSubRecord.new('EDID', 'Editor ID',
                             EspString.new('edid', 'zstring')),
        ])
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        record.add_subrecord('ZZZZ', b'\x00\x00\x00\x00')  # unknown

        result = schema.from_record(record)
        assert 'Editor ID' in result
        assert len(result) == 1  # ZZZZ skipped

    def test_get_member(self):
        schema = self._make_weapon_schema()
        assert schema.get_member('EDID') is not None
        assert schema.get_member('EDID').name == 'Editor ID'
        assert schema.get_member('ZZZZ') is None

    def test_data_roundtrip(self):
        """Resolve a record's DATA subrecord and compose it back."""
        schema = self._make_weapon_schema()
        data_def = schema.get_member('DATA')

        raw = struct.pack('<H', 15) + struct.pack('<f', 5.0) + struct.pack('<I', 50)
        sr = SubRecord('DATA', raw)

        values = data_def.from_subrecord(sr)
        output = data_def.to_subrecord_data(values)
        assert output == raw

    def test_to_dict(self):
        schema = self._make_weapon_schema()
        d = schema.to_dict()
        assert d['type'] == 'record'
        assert d['signature'] == 'WEAP'
        assert len(d['members']) == 4
        assert d['members'][0]['signature'] == 'EDID'


# ---------------------------------------------------------------------------
# JSON serialization round-trip (to_dict)
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_integer_to_dict(self):
        defn = EspInteger.new('x', IntType.U32)
        d = defn.to_dict()
        assert d['type'] == 'integer'
        assert d['int_type'] == 'U32'

    def test_float_to_dict(self):
        d = EspFloat.new('x').to_dict()
        assert d['type'] == 'float'

    def test_string_to_dict(self):
        d = EspString.new('x', 'lstring').to_dict()
        assert d['type'] == 'string'
        assert d['string_type'] == 'lstring'

    def test_struct_to_dict(self):
        defn = EspStruct.new('s', [
            EspInteger.new('a', IntType.U8),
            EspFloat.new('b'),
        ])
        d = defn.to_dict()
        assert d['type'] == 'struct'
        assert len(d['members']) == 2

    def test_array_to_dict(self):
        defn = EspArray.new('a', EspFormID.new('ref'), count=5)
        d = defn.to_dict()
        assert d['type'] == 'array'
        assert d['count'] == 5

    def test_formid_to_dict(self):
        defn = EspFormID.new('race', valid_refs=['RACE'])
        d = defn.to_dict()
        assert d['type'] == 'formid'
        assert d['valid_refs'] == ['RACE']
