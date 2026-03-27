"""Tests for Phase C: Auto-sort subrecords on save."""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.utils import BinaryReader
from esplib.defs import tes5

from tests.conftest import find_skyrim_esm, find_game_file


class TestAutoSort:
    def test_wrong_order_gets_sorted(self):
        """Subrecords added in wrong order should be sorted by schema on save."""
        record = Record('WEAP', FormID(0x01000800), 0)
        record.schema = tes5.WEAP

        # Add in wrong order: DATA before EDID, DESC before OBND
        record.add_subrecord('DATA', struct.pack('<Ifh', 25, 0, 7))
        record.add_subrecord('DESC', b'A sword.\x00')
        record.add_subrecord('EDID', b'TestSword\x00')
        record.add_subrecord('OBND', struct.pack('<6h', 0, 0, 0, 0, 0, 0))

        # Serialize and re-parse
        raw = record.to_bytes()
        reader = BinaryReader(raw)
        reparsed = Record.from_bytes(reader)

        # Verify order matches schema: EDID, OBND, ..., DESC, ..., DATA
        sigs = [sr.signature for sr in reparsed.subrecords]
        edid_idx = sigs.index('EDID')
        obnd_idx = sigs.index('OBND')
        desc_idx = sigs.index('DESC')
        data_idx = sigs.index('DATA')

        assert edid_idx < obnd_idx, "EDID should come before OBND"
        assert obnd_idx < desc_idx, "OBND should come before DESC"
        assert desc_idx < data_idx, "DESC should come before DATA"

    def test_unknown_subrecords_at_end(self):
        """Subrecords not in schema should appear at the end."""
        record = Record('WEAP', FormID(0x01000800), 0)
        record.schema = tes5.WEAP

        record.add_subrecord('ZZZZ', b'\x00\x00\x00\x00')  # unknown
        record.add_subrecord('EDID', b'Test\x00')
        record.add_subrecord('XXYZ', b'\x01\x02')  # another unknown

        raw = record.to_bytes()
        reader = BinaryReader(raw)
        reparsed = Record.from_bytes(reader)

        sigs = [sr.signature for sr in reparsed.subrecords]
        # EDID should be first (known), unknowns at end
        assert sigs[0] == 'EDID'
        assert 'ZZZZ' in sigs
        assert 'XXYZ' in sigs
        assert sigs.index('ZZZZ') > sigs.index('EDID')
        assert sigs.index('XXYZ') > sigs.index('EDID')

    def test_unknown_subrecords_preserve_relative_order(self):
        """Unknown subrecords should keep their relative order."""
        record = Record('WEAP', FormID(0x01000800), 0)
        record.schema = tes5.WEAP

        record.add_subrecord('AAAA', b'\x01')
        record.add_subrecord('EDID', b'Test\x00')
        record.add_subrecord('BBBB', b'\x02')
        record.add_subrecord('CCCC', b'\x03')

        raw = record.to_bytes()
        reader = BinaryReader(raw)
        reparsed = Record.from_bytes(reader)

        sigs = [sr.signature for sr in reparsed.subrecords]
        # Unknown order among themselves preserved
        unknowns = [s for s in sigs if s not in ['EDID']]
        assert unknowns == ['AAAA', 'BBBB', 'CCCC']

    def test_no_schema_no_sort(self):
        """Without a schema, subrecords stay in original order."""
        record = Record('WEAP', FormID(0x800), 0)
        # No schema bound

        record.add_subrecord('DATA', b'\x00' * 10)
        record.add_subrecord('EDID', b'Test\x00')
        record.add_subrecord('OBND', b'\x00' * 12)

        raw = record.to_bytes()
        reader = BinaryReader(raw)
        reparsed = Record.from_bytes(reader)

        sigs = [sr.signature for sr in reparsed.subrecords]
        assert sigs == ['DATA', 'EDID', 'OBND']  # Original order

    def test_roundtrip_dawnguard_preserved(self):
        """Loading and saving Dawnguard.esm should still produce identical bytes
        (auto-sort shouldn't affect already-correct order).
        Uses Dawnguard (~24MB) instead of Skyrim (~250MB) for speed."""
        esm_path = find_game_file('Dawnguard.esm')
        if not esm_path:
            pytest.skip("Dawnguard.esm not found")

        with open(esm_path, 'rb') as f:
            original = f.read()

        plugin = Plugin(esm_path)
        # Bind schemas -- this should NOT change output since vanilla order is correct
        import esplib.defs.tes5
        plugin.set_game('tes5')

        output = plugin.to_bytes()
        assert len(output) == len(original), (
            f"Size mismatch: original={len(original)}, output={len(output)}")
        assert output == original, "Round-trip broken by auto-sort"

    test_roundtrip_dawnguard_preserved = pytest.mark.gamefiles(
        pytest.mark.slow(test_roundtrip_dawnguard_preserved))
