"""Tests for load order, plugin sets, and override resolution."""

import struct
import pytest
from pathlib import Path

from esplib import (
    Plugin, Record, SubRecord, FormID,
    LoadOrder, PluginSet, OverrideChain,
)
from esplib.game_discovery import find_game

from tests.conftest import (
    make_subrecord, make_record, make_group, make_tes4_record,
    find_skyrim_esm,
)


# ---------------------------------------------------------------------------
# LoadOrder tests
# ---------------------------------------------------------------------------

class TestLoadOrder:
    def test_from_list(self):
        lo = LoadOrder.from_list(['Skyrim.esm', 'Update.esm', 'MyMod.esp'])
        assert len(lo) == 3
        assert lo[0] == 'Skyrim.esm'
        assert lo[2] == 'MyMod.esp'

    def test_index_of(self):
        lo = LoadOrder.from_list(['Skyrim.esm', 'Update.esm', 'MyMod.esp'])
        assert lo.index_of('Update.esm') == 1
        assert lo.index_of('update.esm') == 1  # case insensitive
        assert lo.index_of('NotHere.esp') == -1

    def test_iteration(self):
        lo = LoadOrder.from_list(['A.esm', 'B.esp'])
        assert list(lo) == ['A.esm', 'B.esp']

    @pytest.mark.gamefiles
    def test_from_game_skyrim(self):
        game = find_game('tes5')
        if game is None:
            pytest.skip("Skyrim SE not installed")
        lo = LoadOrder.from_game('tes5')
        assert len(lo) > 0
        # Implicit masters should be first
        assert lo[0] == 'Skyrim.esm'
        assert 'Update.esm' in lo.plugins[:5]


# ---------------------------------------------------------------------------
# PluginSet / OverrideChain synthetic tests
# ---------------------------------------------------------------------------

def _make_test_plugin(name: str, masters: list, records: list, tmp_path: Path) -> Path:
    """Create a minimal test plugin file on disk."""
    plugin = Plugin()
    plugin.header.version = 1.71
    plugin.header.masters = masters
    plugin.header.master_sizes = [0] * len(masters)
    if name.lower().endswith('.esm'):
        plugin.header.is_esm = True

    for sig, fid, sub_bytes in records:
        rec = Record(sig, FormID(fid), 0)
        rec.version = 44
        # Parse subrecord bytes manually
        from esplib.utils import BinaryReader
        reader = BinaryReader(sub_bytes)
        while not reader.at_end() and reader.remaining() >= 6:
            sr_sig = reader.read_bytes(4).decode('ascii')
            sr_size = reader.read_uint16()
            sr_data = reader.read_bytes(sr_size)
            rec.subrecords.append(SubRecord(sr_sig, sr_data))
        plugin.add_record(rec)

    path = tmp_path / name
    plugin.save(path)
    return path


class TestPluginSetSynthetic:
    def test_override_chain_basic(self, tmp_path):
        """Master defines a record, plugin overrides it."""
        edid_sub = make_subrecord('EDID', b'TestWeapon\x00')
        data_sub = make_subrecord('DATA', struct.pack('<Ifh', 10, 0, 5))  # val, weight, dmg

        # Master: defines WEAP at FormID 0x00000800
        # (file_index=0 = self since no masters)
        master_path = _make_test_plugin(
            'TestMaster.esm', [], [('WEAP', 0x00000800, edid_sub + data_sub)], tmp_path)

        # Override: masters=[TestMaster.esm], overrides FormID
        # file_index=0 = TestMaster.esm, so FormID 0x00000800
        data_sub2 = make_subrecord('DATA', struct.pack('<Ifh', 99, 0, 50))
        override_path = _make_test_plugin(
            'TestOverride.esp', ['TestMaster.esm'],
            [('WEAP', 0x00000800, edid_sub + data_sub2)], tmp_path)

        lo = LoadOrder.from_list(
            ['TestMaster.esm', 'TestOverride.esp'],
            data_dir=tmp_path)
        ps = PluginSet(lo)
        ps.load_all()

        # The FormID 0x00000800 in the master maps to absolute (0 << 24) | 0x800
        chain = ps.get_override_chain(0x00000800)
        assert chain is not None
        assert len(chain) == 2
        # Base is from master
        assert chain[0].get_subrecord('DATA').get_uint32() == 10  # value=10
        # Winner is from override
        assert chain[-1].get_subrecord('DATA').get_uint32() == 99  # value=99

    def test_single_record_no_override(self, tmp_path):
        """A record with no overrides has chain length 1."""
        edid_sub = make_subrecord('EDID', b'Unique\x00')
        master_path = _make_test_plugin(
            'Solo.esm', [], [('MISC', 0x00000800, edid_sub)], tmp_path)

        lo = LoadOrder.from_list(['Solo.esm'], data_dir=tmp_path)
        ps = PluginSet(lo)
        ps.load_all()

        chain = ps.get_override_chain(0x00000800)
        assert chain is not None
        assert len(chain) == 1
        assert chain[0] is chain[-1]

    def test_three_way_override(self, tmp_path):
        """Three plugins: master, patch A, patch B."""
        edid_sub = make_subrecord('EDID', b'Item\x00')

        data_base = make_subrecord('DATA', struct.pack('<I', 10))
        data_a = make_subrecord('DATA', struct.pack('<I', 20))
        data_b = make_subrecord('DATA', struct.pack('<I', 30))

        _make_test_plugin('Base.esm', [],
                          [('MISC', 0x00000800, edid_sub + data_base)], tmp_path)
        _make_test_plugin('PatchA.esp', ['Base.esm'],
                          [('MISC', 0x00000800, edid_sub + data_a)], tmp_path)
        _make_test_plugin('PatchB.esp', ['Base.esm'],
                          [('MISC', 0x00000800, edid_sub + data_b)], tmp_path)

        lo = LoadOrder.from_list(
            ['Base.esm', 'PatchA.esp', 'PatchB.esp'], data_dir=tmp_path)
        ps = PluginSet(lo)
        ps.load_all()

        chain = ps.get_override_chain(0x00000800)
        assert len(chain) == 3
        assert chain[0].get_subrecord('DATA').get_uint32() == 10
        assert chain[1].get_subrecord('DATA').get_uint32() == 20
        assert chain[-1].get_subrecord('DATA').get_uint32() == 30

    def test_overridden_records_iterator(self, tmp_path):
        """overridden_records() yields only FormIDs with multiple entries."""
        edid1 = make_subrecord('EDID', b'Shared\x00')
        edid2 = make_subrecord('EDID', b'Unique\x00')
        data = make_subrecord('DATA', struct.pack('<I', 1))

        _make_test_plugin('M.esm', [], [
            ('MISC', 0x00000800, edid1 + data),
            ('MISC', 0x00000801, edid2 + data),
        ], tmp_path)
        _make_test_plugin('P.esp', ['M.esm'], [
            ('MISC', 0x00000800, edid1 + data),  # override only 800
        ], tmp_path)

        lo = LoadOrder.from_list(['M.esm', 'P.esp'], data_dir=tmp_path)
        ps = PluginSet(lo)
        ps.load_all()

        overridden = list(ps.overridden_records())
        assert len(overridden) == 1
        fid, chain = overridden[0]
        assert (fid & 0x00FFFFFF) == 0x800

    def test_missing_plugin_skipped(self, tmp_path):
        """Plugins not on disk are skipped gracefully."""
        edid = make_subrecord('EDID', b'Test\x00')
        _make_test_plugin('Real.esm', [], [('MISC', 0x800, edid)], tmp_path)

        lo = LoadOrder.from_list(
            ['Real.esm', 'Missing.esp'], data_dir=tmp_path)
        ps = PluginSet(lo)
        loaded = ps.load_all()
        assert loaded == 1


# ---------------------------------------------------------------------------
# Real game file tests
# ---------------------------------------------------------------------------

class TestPluginSetSkyrim:
    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_load_skyrim_with_dlc(self):
        """Load Skyrim.esm + DLC masters."""
        game = find_game('tes5')
        if game is None:
            pytest.skip("Skyrim SE not installed")

        lo = LoadOrder.from_list(
            ['Skyrim.esm', 'Update.esm', 'Dawnguard.esm'],
            data_dir=game.data_dir, game_id='tes5')
        ps = PluginSet(lo)
        loaded = ps.load_all()
        assert loaded >= 2  # At least Skyrim.esm + something

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_override_in_update_esm(self):
        """Update.esm should override some Skyrim.esm records."""
        game = find_game('tes5')
        if game is None:
            pytest.skip("Skyrim SE not installed")

        lo = LoadOrder.from_list(
            ['Skyrim.esm', 'Update.esm'],
            data_dir=game.data_dir, game_id='tes5')
        ps = PluginSet(lo)
        ps.load_all()

        # Count overrides
        overrides = list(ps.overridden_records())
        assert len(overrides) > 0, "Update.esm should override some Skyrim.esm records"
