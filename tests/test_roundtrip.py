"""Round-trip fidelity tests for esplib.

Tests that loading and saving produces identical bytes.
"""

import struct
import zlib
import pytest
from pathlib import Path

from esplib import Plugin, Record, SubRecord, GroupRecord, FormID
from esplib.utils import BinaryReader, BinaryWriter
from esplib.record import COMPRESSED_FLAG

from tests.conftest import (
    make_subrecord, make_xxxx_subrecord, make_record, make_group,
    make_tes4_record, make_simple_plugin, find_skyrim_esm,
)


class TestRecordHeaderPreservation:
    """Test that record header fields survive round-trip."""

    def test_record_preserves_timestamp(self):
        sub = make_subrecord('EDID', b'TestItem\x00')
        raw = make_record('WEAP', 0x100, 0, sub, timestamp=0xDEADBEEF)

        reader = BinaryReader(raw)
        record = Record.from_bytes(reader)

        assert record.timestamp == 0xDEADBEEF
        output = record.to_bytes()
        assert output == raw

    def test_record_preserves_version_and_vci(self):
        sub = make_subrecord('EDID', b'Test\x00')
        raw = make_record('ARMO', 0x200, 0, sub, version=44, vci=0xBEEF)

        reader = BinaryReader(raw)
        record = Record.from_bytes(reader)

        assert record.version == 44
        assert record.version_control_info == 0xBEEF
        assert record.to_bytes() == raw

    def test_group_preserves_header_fields(self):
        sub = make_subrecord('EDID', b'Test\x00')
        rec = make_record('WEAP', 0x100, 0, sub)
        raw = make_group('WEAP', 0, rec, timestamp=0xCAFEBABE, version=1, vci=0x1234)

        reader = BinaryReader(raw)
        group = GroupRecord.from_bytes(reader)

        assert group.timestamp == 0xCAFEBABE
        assert group.version == 1
        assert group.version_control_info == 0x1234
        assert group.to_bytes() == raw


class TestCompression:
    """Test compressed record handling."""

    def test_load_compressed_record(self):
        """Compressed records should be decompressed and subrecords parsed."""
        sub_bytes = make_subrecord('EDID', b'CompressedItem\x00')
        sub_bytes += make_subrecord('DATA', struct.pack('<I', 42))

        raw = make_record('WEAP', 0x300, COMPRESSED_FLAG, sub_bytes)

        reader = BinaryReader(raw)
        record = Record.from_bytes(reader)

        assert record.is_compressed
        assert len(record.subrecords) == 2
        assert record.subrecords[0].signature == 'EDID'
        assert record.subrecords[0].get_string() == 'CompressedItem'
        assert record.subrecords[1].get_uint32() == 42

    def test_compressed_record_roundtrip(self):
        """Compressed records should re-compress on save."""
        sub_bytes = make_subrecord('EDID', b'TestCompress\x00')
        sub_bytes += make_subrecord('DATA', struct.pack('<f', 3.14))

        raw = make_record('WEAP', 0x400, COMPRESSED_FLAG, sub_bytes)

        reader = BinaryReader(raw)
        record = Record.from_bytes(reader)
        output = record.to_bytes()

        # Re-parse the output to verify correctness
        reader2 = BinaryReader(output)
        record2 = Record.from_bytes(reader2)

        assert record2.is_compressed
        assert record2.subrecords[0].get_string() == 'TestCompress'
        assert abs(record2.subrecords[1].get_float() - 3.14) < 0.001

    def test_uncompressed_record_stays_uncompressed(self):
        sub = make_subrecord('EDID', b'Plain\x00')
        raw = make_record('MISC', 0x500, 0, sub)

        reader = BinaryReader(raw)
        record = Record.from_bytes(reader)
        output = record.to_bytes()

        assert output == raw
        assert not record.is_compressed


class TestXXXXOverflow:
    """Test XXXX subrecord overflow handling."""

    def test_read_xxxx_subrecord(self):
        """XXXX marker should set the size for the next subrecord."""
        # Build a subrecord larger than 65535 bytes using XXXX
        big_data = bytes(range(256)) * 300  # 76800 bytes
        sub_bytes = make_xxxx_subrecord('NAVM', big_data)

        raw = make_record('NAVM', 0x600, 0, sub_bytes)

        reader = BinaryReader(raw)
        record = Record.from_bytes(reader)

        assert len(record.subrecords) == 1
        assert record.subrecords[0].signature == 'NAVM'
        assert record.subrecords[0].size == len(big_data)
        assert record.subrecords[0].data == big_data

    def test_write_xxxx_subrecord(self):
        """Subrecords > 65535 bytes should use XXXX overflow on write."""
        big_data = b'\xAB' * 70000
        record = Record('TEST', FormID(0x700))
        record.subrecords.append(SubRecord('BIGX', big_data))

        output = record.to_bytes()

        # Re-parse and verify
        reader = BinaryReader(output)
        record2 = Record.from_bytes(reader)

        assert len(record2.subrecords) == 1
        assert record2.subrecords[0].signature == 'BIGX'
        assert record2.subrecords[0].data == big_data

    def test_normal_subrecord_no_xxxx(self):
        """Subrecords <= 65535 bytes should NOT use XXXX."""
        small_data = b'\x00' * 100
        sr = SubRecord('DATA', small_data)
        raw = sr.to_bytes()

        # Should be: sig(4) + size(2) + data(100) = 106 bytes, no XXXX
        assert len(raw) == 106
        assert raw[:4] == b'DATA'
        assert struct.unpack('<H', raw[4:6])[0] == 100

    def test_boundary_65535_no_xxxx(self):
        """Exactly 65535 bytes should fit without XXXX."""
        data = b'\xFF' * 65535
        sr = SubRecord('BNDY', data)
        raw = sr.to_bytes()

        assert raw[:4] == b'BNDY'
        assert struct.unpack('<H', raw[4:6])[0] == 65535
        assert len(raw) == 6 + 65535

    def test_boundary_65536_uses_xxxx(self):
        """65536 bytes should trigger XXXX."""
        data = b'\xFF' * 65536
        sr = SubRecord('OVER', data)
        raw = sr.to_bytes()

        assert raw[:4] == b'XXXX'


class TestGroupOffsetParsing:
    """Test that GroupRecord uses offset-based end detection."""

    def test_nested_groups(self):
        """Nested groups should parse correctly with offset tracking."""
        inner_sub = make_subrecord('EDID', b'InnerRec\x00')
        inner_rec = make_record('WEAP', 0x100, 0, inner_sub)
        inner_group = make_group('WEAP', 2, inner_rec, timestamp=0xAAAA)

        outer_sub = make_subrecord('EDID', b'OuterRec\x00')
        outer_rec = make_record('WEAP', 0x200, 0, outer_sub)
        content = inner_group + outer_rec
        outer_group = make_group('WEAP', 0, content, timestamp=0xBBBB)

        reader = BinaryReader(outer_group)
        group = GroupRecord.from_bytes(reader)

        assert len(group.records) == 2
        assert isinstance(group.records[0], GroupRecord)
        assert isinstance(group.records[1], Record)
        assert group.records[0].timestamp == 0xAAAA
        assert group.timestamp == 0xBBBB

    def test_empty_group(self):
        """Empty group (header only) should parse correctly."""
        raw = make_group('EMTY', 0, b'')
        reader = BinaryReader(raw)
        group = GroupRecord.from_bytes(reader)

        assert len(group.records) == 0
        assert group.to_bytes() == raw

    def test_multiple_groups_sequential(self):
        """Multiple groups in sequence should each parse to their boundary."""
        sub1 = make_subrecord('EDID', b'Weapon1\x00')
        rec1 = make_record('WEAP', 0x100, 0, sub1)
        group1 = make_group('WEAP', 0, rec1, timestamp=0x1111)

        sub2 = make_subrecord('EDID', b'Armor1\x00')
        rec2 = make_record('ARMO', 0x200, 0, sub2)
        group2 = make_group('ARMO', 0, rec2, timestamp=0x2222)

        combined = group1 + group2
        reader = BinaryReader(combined)

        g1 = GroupRecord.from_bytes(reader)
        g2 = GroupRecord.from_bytes(reader)

        assert g1.label == 'WEAP'
        assert g2.label == 'ARMO'
        assert g1.timestamp == 0x1111
        assert g2.timestamp == 0x2222
        assert reader.at_end()


class TestPluginRoundTrip:
    """Test full plugin load/save round-trips."""

    def test_simple_plugin_roundtrip(self):
        """A simple synthetic plugin should round-trip exactly."""
        edid = make_subrecord('EDID', b'TestWeapon\x00')
        data = make_subrecord('DATA', struct.pack('<I', 10))
        sub_bytes = edid + data

        raw = make_simple_plugin(
            records=[('WEAP', 0x800, sub_bytes)],
            tes4_flags=0x01,  # ESM
        )

        reader = BinaryReader(raw)
        plugin = Plugin.__new__(Plugin)
        plugin.file_path = None
        plugin.header = None
        plugin.groups = []
        plugin.records = []
        plugin.load_order = -1
        plugin.modified = False
        plugin._form_id_index = {}
        plugin._editor_id_index = {}
        plugin._signature_index = {}
        plugin._parse_plugin(reader)
        plugin._build_indexes()

        output = plugin.to_bytes()
        assert output == raw

    def test_plugin_with_compressed_records(self):
        """Plugin with compressed records should round-trip (subrecord content preserved)."""
        edid_bytes = make_subrecord('EDID', b'CompressedWeapon\x00')
        data_bytes = make_subrecord('DATA', struct.pack('<II', 15, 100))
        sub_bytes = edid_bytes + data_bytes

        rec = make_record('WEAP', 0x800, COMPRESSED_FLAG, sub_bytes)
        group = make_group('WEAP', 0, rec)
        tes4 = make_tes4_record(flags=0x01, num_records=1)
        raw = tes4 + group

        reader = BinaryReader(raw)
        plugin = Plugin.__new__(Plugin)
        plugin.file_path = None
        plugin.header = None
        plugin.groups = []
        plugin.records = []
        plugin.load_order = -1
        plugin.modified = False
        plugin._form_id_index = {}
        plugin._editor_id_index = {}
        plugin._signature_index = {}
        plugin._parse_plugin(reader)
        plugin._build_indexes()

        output = plugin.to_bytes()

        # Re-parse the output and verify content
        reader2 = BinaryReader(output)
        plugin2 = Plugin.__new__(Plugin)
        plugin2.file_path = None
        plugin2.header = None
        plugin2.groups = []
        plugin2.records = []
        plugin2.load_order = -1
        plugin2.modified = False
        plugin2._form_id_index = {}
        plugin2._editor_id_index = {}
        plugin2._signature_index = {}
        plugin2._parse_plugin(reader2)
        plugin2._build_indexes()

        assert len(plugin2.records) == 1
        assert plugin2.records[0].editor_id == 'CompressedWeapon'
        assert plugin2.records[0].is_compressed

    def test_plugin_with_masters(self):
        """Plugin with master files should preserve master list."""
        raw = make_simple_plugin(
            masters=['Skyrim.esm', 'Update.esm'],
            tes4_flags=0x01,
        )

        reader = BinaryReader(raw)
        plugin = Plugin.__new__(Plugin)
        plugin.file_path = None
        plugin.header = None
        plugin.groups = []
        plugin.records = []
        plugin.load_order = -1
        plugin.modified = False
        plugin._form_id_index = {}
        plugin._editor_id_index = {}
        plugin._signature_index = {}
        plugin._parse_plugin(reader)
        plugin._build_indexes()

        assert plugin.header.masters == ['Skyrim.esm', 'Update.esm']
        assert plugin.is_esm

        output = plugin.to_bytes()
        assert output == raw


class TestSkyrimRoundTrip:
    """Integration tests with real Skyrim.esm."""

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_skyrim_esm_roundtrip(self):
        """Load Skyrim.esm, save to bytes, compare checksums."""
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")

        with open(esm_path, 'rb') as f:
            original_data = f.read()

        plugin = Plugin(esm_path)
        output = plugin.to_bytes()

        assert len(output) == len(original_data), (
            f"Size mismatch: original={len(original_data)}, output={len(output)}")
        assert output == original_data, "Byte-for-byte comparison failed"
