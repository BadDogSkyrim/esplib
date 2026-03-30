"""Tests for plugin operations: copy/patch, localized strings, masters,
FormID remap, and tint auto-sort.
"""

import struct
import tempfile
import pytest
from pathlib import Path

from esplib import Plugin, Record, FormID
from esplib.record import SubRecord
from esplib.game_discovery import find_game

from tests.conftest import (
    find_skyrim_esm, find_skyrim_data, find_strings_dir,
    make_simple_plugin, make_subrecord, make_record, make_group,
    make_tes4_record,
)


# ===================================================================
# Copy / Patch
# ===================================================================


class TestStructCopy:


    def test_copy_preserves_fields(self):
        record = Record('WEAP', FormID(0x800), 0x10)
        record.timestamp = 0xDEAD
        record.version = 44
        record.version_control_info = 0xBEEF
        record.add_subrecord('EDID', b'TestWeapon\x00')
        record.add_subrecord('DATA', struct.pack('<Ifh', 25, 0, 7))

        copy = record.copy()
        assert copy.signature == 'WEAP'
        assert copy.form_id.value == 0x800
        assert copy.flags == 0x10
        assert copy.timestamp == 0xDEAD
        assert copy.version == 44
        assert copy.version_control_info == 0xBEEF
        assert len(copy.subrecords) == 2
        assert copy.subrecords[0].get_string() == 'TestWeapon'


    def test_copy_is_independent(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Original\x00')

        copy = record.copy()
        copy.subrecords[0].set_string('Modified')

        assert record.subrecords[0].get_string() == 'Original'
        assert copy.subrecords[0].get_string() == 'Modified'


    def test_copy_preserves_schema(self):
        from esplib.defs import tes5

        record = Record('WEAP', FormID(0x800), 0)
        record.schema = tes5.WEAP
        copy = record.copy()
        assert copy.schema is tes5.WEAP


    def test_has_subrecord(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        assert record.has_subrecord('EDID')
        assert not record.has_subrecord('DATA')


class TestStructNewPlugin:


    def test_new_plugin_basic(self, tmp_path):
        plugin = Plugin.new_plugin(tmp_path / 'test.esp',
                                   masters=['Skyrim.esm'])
        assert plugin.header.masters == ['Skyrim.esm']
        assert plugin.header.version == 1.71
        assert not plugin.header.is_esm


    def test_new_plugin_esm(self, tmp_path):
        plugin = Plugin.new_plugin(tmp_path / 'test.esm',
                                   masters=['Skyrim.esm'],
                                   is_esm=True)
        assert plugin.header.is_esm


    def test_new_plugin_no_masters(self, tmp_path):
        plugin = Plugin.new_plugin(tmp_path / 'test.esm')
        assert plugin.header.masters == []


class TestStructAddMaster:


    def test_add_master(self):
        plugin = Plugin()
        plugin.add_master('Skyrim.esm')
        assert plugin.header.masters == ['Skyrim.esm']


    def test_add_master_dedup(self):
        plugin = Plugin()
        plugin.add_master('Skyrim.esm')
        plugin.add_master('Skyrim.esm')
        assert len(plugin.header.masters) == 1


    def test_add_master_case_insensitive_dedup(self):
        plugin = Plugin()
        plugin.add_master('Skyrim.esm')
        plugin.add_master('skyrim.esm')
        assert len(plugin.header.masters) == 1


    def test_add_multiple_masters(self):
        plugin = Plugin()
        plugin.add_master('Skyrim.esm')
        plugin.add_master('Update.esm')
        plugin.add_master('Dawnguard.esm')
        assert len(plugin.header.masters) == 3


class TestPluginAddRecursiveMasters:


    def test_recursive_masters(self, tmp_path):
        source = Plugin.new_plugin(tmp_path / 'source.esp',
                                   masters=['Skyrim.esm', 'Update.esm'])
        source.save()

        target = Plugin.new_plugin(tmp_path / 'target.esp')
        target.add_recursive_masters(source)

        assert 'Skyrim.esm' in target.header.masters
        assert 'Update.esm' in target.header.masters
        assert 'source.esp' in target.header.masters


    def test_recursive_no_duplicates(self, tmp_path):
        source = Plugin.new_plugin(tmp_path / 'mod.esp',
                                   masters=['Skyrim.esm'])
        source.save()

        target = Plugin.new_plugin(tmp_path / 'patch.esp',
                                   masters=['Skyrim.esm'])
        target.add_recursive_masters(source)

        assert target.header.masters.count('Skyrim.esm') == 1
        assert 'mod.esp' in target.header.masters


class TestPluginCopyRecord:


    def test_copy_record_to_plugin(self, tmp_path):
        source = Plugin.new_plugin(tmp_path / 'source.esp',
                                   masters=['Skyrim.esm'])
        weap = Record('WEAP', FormID(0x01000800), 0)
        weap.add_subrecord('EDID', b'TestSword\x00')
        weap.add_subrecord('DATA', struct.pack('<Ifh', 25, 0, 7))
        source.add_record(weap)
        source.save()

        target = Plugin.new_plugin(tmp_path / 'target.esp')
        copied = target.copy_record(weap, source)

        assert copied.editor_id == 'TestSword'
        assert len(target.records) == 1
        assert 'Skyrim.esm' in target.header.masters
        assert 'source.esp' in target.header.masters


    def test_copy_record_preserves_data(self, tmp_path):
        source = Plugin.new_plugin(tmp_path / 'src.esp')
        rec = Record('MISC', FormID(0x800), 0)
        rec.add_subrecord('EDID', b'Gold\x00')
        rec.add_subrecord('DATA', struct.pack('<if', 1, 0.0))
        source.add_record(rec)

        target = Plugin.new_plugin(tmp_path / 'tgt.esp')
        copied = target.copy_record(rec)

        rec.subrecords[0].set_string('Changed')
        assert copied.editor_id == 'Gold'


    def test_save_and_reload_copied_plugin(self, tmp_path):
        source = Plugin.new_plugin(tmp_path / 'src.esp',
                                   masters=['Skyrim.esm'])
        rec = Record('WEAP', FormID(0x00012EB7), 0)
        rec.add_subrecord('EDID', b'IronSword\x00')
        source.add_record(rec)
        source.save()

        target = Plugin.new_plugin(tmp_path / 'patch.esp')
        target.copy_record(rec, source)
        target.save()

        reloaded = Plugin(tmp_path / 'patch.esp')
        assert len(reloaded.records) == 1
        assert reloaded.records[0].editor_id == 'IronSword'
        assert 'Skyrim.esm' in reloaded.header.masters


class TestCopyFromSkyrim:


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_copy_iron_sword(self, skyrim_plugin, tmp_path):
        skyrim = skyrim_plugin
        sword = skyrim.get_record_by_editor_id('IronSword')
        assert sword is not None

        patch = Plugin.new_plugin(tmp_path / 'test_patch.esp')
        copied = patch.copy_record(sword, skyrim)
        patch.save()

        reloaded = Plugin(tmp_path / 'test_patch.esp')
        assert len(reloaded.records) == 1
        assert reloaded.records[0].form_id.value == sword.form_id.value


# ===================================================================
# Localized Strings
# ===================================================================


class TestLocalizedFullName:
    """full_name resolves correctly for localized plugins."""


    @pytest.mark.gamefiles
    def test_plugin_is_localized(self, skyrim_plugin):
        assert skyrim_plugin.is_localized


    @pytest.mark.gamefiles
    def test_string_tables_loaded(self, skyrim_plugin):
        assert skyrim_plugin.string_tables is not None
        assert skyrim_plugin.string_tables.strings is not None


    @pytest.mark.gamefiles
    def test_nord_race_name(self, skyrim_plugin):
        for r in skyrim_plugin.get_records_by_signature('RACE'):
            if r.editor_id == 'NordRace':
                assert r.full_name == 'Nord'
                return
        pytest.fail("NordRace not found")


    @pytest.mark.gamefiles
    def test_breton_race_name(self, skyrim_plugin):
        for r in skyrim_plugin.get_records_by_signature('RACE'):
            if r.editor_id == 'BretonRace':
                assert r.full_name == 'Breton'
                return
        pytest.fail("BretonRace not found")


    @pytest.mark.gamefiles
    def test_dark_elf_race_name(self, skyrim_plugin):
        for r in skyrim_plugin.get_records_by_signature('RACE'):
            if r.editor_id == 'DarkElfRace':
                assert r.full_name == 'Dark Elf'
                return
        pytest.fail("DarkElfRace not found")


    @pytest.mark.gamefiles
    def test_iron_sword_name(self, skyrim_plugin):
        for r in skyrim_plugin.get_records_by_signature('WEAP'):
            if r.editor_id == 'IronSword':
                assert r.full_name == 'Iron Sword'
                return
        pytest.fail("IronSword not found")


class TestStructCopyDelocalization:
    """copy_record converts localized string IDs to inline strings."""


    def _make_localized_plugin(self, strings_dict):
        """Create a minimal localized plugin with string tables in memory."""
        from esplib.strings import StringTable, StringTableManager

        p = Plugin()
        p.header.is_localized = True
        p.file_path = Path(tempfile.mkdtemp()) / 'Localized.esm'

        mgr = StringTableManager()
        mgr.strings = StringTable(StringTable.STRINGS)
        for sid, text in strings_dict.items():
            mgr.strings.set(sid, text)
        p.string_tables = mgr

        return p


    def test_delocalize_full(self):
        """FULL subrecord is converted from string ID to inline string."""
        source = self._make_localized_plugin({42: 'Iron Sword'})

        rec = Record('WEAP', FormID(0x100), 0)
        rec.add_subrecord('EDID', b'IronSword\x00')
        rec.add_subrecord('FULL', struct.pack('<I', 42))
        rec._plugin = source

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esp',
                                 masters=['Localized.esm'])

        copied = dest.copy_record(rec)
        full = copied.get_subrecord('FULL')
        assert full.get_string() == 'Iron Sword'


    def test_delocalize_shrt(self):
        """SHRT subrecord is also delocalized."""
        source = self._make_localized_plugin({99: 'Balgruuf'})

        rec = Record('NPC_', FormID(0x100), 0)
        rec.add_subrecord('EDID', b'TestNPC\x00')
        rec.add_subrecord('SHRT', struct.pack('<I', 99))
        rec._plugin = source

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esp',
                                 masters=['Localized.esm'])

        copied = dest.copy_record(rec)
        shrt = copied.get_subrecord('SHRT')
        assert shrt.get_string() == 'Balgruuf'


    def test_no_delocalize_when_dest_localized(self):
        """If destination is also localized, string IDs are preserved."""
        source = self._make_localized_plugin({42: 'Iron Sword'})

        rec = Record('WEAP', FormID(0x100), 0)
        rec.add_subrecord('FULL', struct.pack('<I', 42))
        rec._plugin = source

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esm')
        dest.header.is_localized = True

        copied = dest.copy_record(rec)
        full = copied.get_subrecord('FULL')
        assert full.size == 4
        assert struct.unpack('<I', full.data)[0] == 42


    def test_no_delocalize_nonlocalized_source(self):
        """Non-localized source records are copied as-is."""
        rec = Record('WEAP', FormID(0x100), 0)
        rec.add_subrecord('FULL', b'Iron Sword\x00')

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esp')

        copied = dest.copy_record(rec)
        full = copied.get_subrecord('FULL')
        assert full.get_string() == 'Iron Sword'


class TestDelocalizeGamefiles:
    """String delocalization with real Skyrim.esm."""


    @pytest.mark.gamefiles
    def test_copy_race_delocalizes_full(self, skyrim_plugin):
        """Copying NordRace from Skyrim.esm delocalizes FULL to 'Nord'."""
        if not skyrim_plugin.string_tables:
            assert False, "String tables not loaded"

        nord = None
        for r in skyrim_plugin.get_records_by_signature('RACE'):
            if r.editor_id == 'NordRace':
                nord = r
                break
        assert nord is not None

        dest = Plugin.new_plugin(
            Path(tempfile.mkdtemp()) / 'Patch.esp',
            masters=['Skyrim.esm'])

        copied = dest.copy_record(nord)
        full = copied.get_subrecord('FULL')
        assert full is not None
        assert full.size > 4, "FULL should be delocalized inline string"
        assert full.get_string() == 'Nord'


# ===================================================================
# Masters / Overrides
# ===================================================================


class TestStructLoadOrder:


    def test_from_list(self):
        from esplib import LoadOrder
        lo = LoadOrder.from_list(['Skyrim.esm', 'Update.esm', 'MyMod.esp'])
        assert len(lo) == 3
        assert lo[0] == 'Skyrim.esm'
        assert lo[2] == 'MyMod.esp'


    def test_index_of(self):
        from esplib import LoadOrder
        lo = LoadOrder.from_list(['Skyrim.esm', 'Update.esm', 'MyMod.esp'])
        assert lo.index_of('Update.esm') == 1
        assert lo.index_of('update.esm') == 1  # case insensitive
        assert lo.index_of('NotHere.esp') == -1


    def test_iteration(self):
        from esplib import LoadOrder
        lo = LoadOrder.from_list(['A.esm', 'B.esp'])
        assert list(lo) == ['A.esm', 'B.esp']


class TestLoadOrderSkyrim:


    @pytest.mark.gamefiles
    def test_from_game_skyrim(self):
        from esplib import LoadOrder
        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"
        lo = LoadOrder.from_game('tes5')
        assert len(lo) > 0
        assert lo[0] == 'Skyrim.esm'
        assert 'Update.esm' in lo.plugins[:5]


def _make_test_plugin(name: str, masters: list, records: list, tmp_path: Path) -> Path:
    """Create a minimal test plugin file on disk."""
    from esplib.utils import BinaryReader

    plugin = Plugin()
    plugin.header.version = 1.71
    plugin.header.masters = masters
    plugin.header.master_sizes = [0] * len(masters)
    if name.lower().endswith('.esm'):
        plugin.header.is_esm = True

    for sig, fid, sub_bytes in records:
        rec = Record(sig, FormID(fid), 0)
        rec.version = 44
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
        from esplib import LoadOrder, PluginSet

        edid_sub = make_subrecord('EDID', b'TestWeapon\x00')
        data_sub = make_subrecord('DATA', struct.pack('<Ifh', 10, 0, 5))

        _make_test_plugin(
            'TestMaster.esm', [], [('WEAP', 0x00000800, edid_sub + data_sub)], tmp_path)

        data_sub2 = make_subrecord('DATA', struct.pack('<Ifh', 99, 0, 50))
        _make_test_plugin(
            'TestOverride.esp', ['TestMaster.esm'],
            [('WEAP', 0x00000800, edid_sub + data_sub2)], tmp_path)

        lo = LoadOrder.from_list(
            ['TestMaster.esm', 'TestOverride.esp'],
            data_dir=tmp_path)
        ps = PluginSet(lo)
        ps.load_all()

        chain = ps.get_override_chain(0x00000800)
        assert chain is not None
        assert len(chain) == 2
        assert chain[0].get_subrecord('DATA').get_uint32() == 10
        assert chain[-1].get_subrecord('DATA').get_uint32() == 99


    def test_single_record_no_override(self, tmp_path):
        """A record with no overrides has chain length 1."""
        from esplib import LoadOrder, PluginSet

        edid_sub = make_subrecord('EDID', b'Unique\x00')
        _make_test_plugin(
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
        from esplib import LoadOrder, PluginSet

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
        from esplib import LoadOrder, PluginSet

        edid1 = make_subrecord('EDID', b'Shared\x00')
        edid2 = make_subrecord('EDID', b'Unique\x00')
        data = make_subrecord('DATA', struct.pack('<I', 1))

        _make_test_plugin('M.esm', [], [
            ('MISC', 0x00000800, edid1 + data),
            ('MISC', 0x00000801, edid2 + data),
        ], tmp_path)
        _make_test_plugin('P.esp', ['M.esm'], [
            ('MISC', 0x00000800, edid1 + data),
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
        from esplib import LoadOrder, PluginSet

        edid = make_subrecord('EDID', b'Test\x00')
        _make_test_plugin('Real.esm', [], [('MISC', 0x800, edid)], tmp_path)

        lo = LoadOrder.from_list(
            ['Real.esm', 'Missing.esp'], data_dir=tmp_path)
        ps = PluginSet(lo)
        loaded = ps.load_all()
        assert loaded == 1


class TestPluginSetSkyrim:


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_load_skyrim_with_dlc(self):
        """Load Skyrim.esm + DLC masters."""
        from esplib import LoadOrder, PluginSet

        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"

        lo = LoadOrder.from_list(
            ['Skyrim.esm', 'Update.esm', 'Dawnguard.esm'],
            data_dir=game.data_dir, game_id='tes5')
        ps = PluginSet(lo)
        loaded = ps.load_all()
        assert loaded >= 2


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_override_in_update_esm(self):
        """Update.esm should override some Skyrim.esm records."""
        from esplib import LoadOrder, PluginSet

        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"

        lo = LoadOrder.from_list(
            ['Skyrim.esm', 'Update.esm'],
            data_dir=game.data_dir, game_id='tes5')
        ps = PluginSet(lo)
        ps.load_all()

        overrides = list(ps.overridden_records())
        assert len(overrides) > 0, "Update.esm should override some Skyrim.esm records"


# ===================================================================
# FormID Remap
# ===================================================================


class TestStructRemapFormID:
    """Plugin.remap_formid() translates FormIDs between master lists."""


    def test_remap_local_to_master(self):
        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm', 'Source.esp'])

        fid = (1 << 24) | 0x000ABC
        remapped = dest.remap_formid(fid, source)

        assert (remapped >> 24) & 0xFF == 1
        assert remapped & 0x00FFFFFF == 0x000ABC


    def test_remap_shared_master(self):
        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm', 'Update.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm', 'Update.esm', 'Source.esp'])

        fid = 0x00013746
        remapped = dest.remap_formid(fid, source)

        assert remapped == 0x00013746


    def test_remap_different_master_order(self):
        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm', 'Dawnguard.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm', 'Update.esm',
                                          'Dawnguard.esm', 'Source.esp'])

        fid = (1 << 24) | 0x000123
        remapped = dest.remap_formid(fid, source)

        assert (remapped >> 24) & 0xFF == 2
        assert remapped & 0x00FFFFFF == 0x000123


    def test_remap_unknown_master_unchanged(self):
        """A FormID referencing an unknown master passes through unchanged."""
        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm', 'Missing.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm'])

        fid = (1 << 24) | 0x000123
        remapped = dest.remap_formid(fid, source)

        assert remapped == fid


class TestRemapFormIDGamefiles:
    """remap_formid with real game data."""


    @pytest.mark.gamefiles
    def test_remap_skyrim_record(self, skyrim_plugin):
        """Remap a Skyrim.esm FormID into a patch with different master order."""
        dest = Plugin.new_plugin(
            Path(tempfile.mkdtemp()) / 'Patch.esp',
            masters=['Update.esm', 'Skyrim.esm'])

        nord_fid = 0x00013746
        remapped = dest.remap_formid(nord_fid, skyrim_plugin)

        assert (remapped >> 24) & 0xFF == 1
        assert remapped & 0x00FFFFFF == 0x013746


# ===================================================================
# Tint Auto-Sort
# ===================================================================


class TestStructNPCTintAutoSort:
    """Tint layers stay interleaved after auto-sort on modified records."""


    def test_tints_interleaved_after_sort(self):
        """Modified NPC record preserves TINI/TINC/TINV/TIAS grouping."""
        from esplib.defs.game import GameRegistry

        npc = Record('NPC_', FormID(0x100), 0)
        npc.add_subrecord('EDID', b'TestNPC\x00')
        npc.add_subrecord('ACBS', b'\x00' * 24)

        npc.add_subrecord('TINI', struct.pack('<H', 643))
        npc.add_subrecord('TINC', bytes([108, 99, 85, 0]))
        npc.add_subrecord('TINV', struct.pack('<i', 89))
        npc.add_subrecord('TIAS', struct.pack('<h', 9336))

        npc.add_subrecord('TINI', struct.pack('<H', 644))
        npc.add_subrecord('TINC', bytes([25, 25, 25, 0]))
        npc.add_subrecord('TINV', struct.pack('<i', 100))
        npc.add_subrecord('TIAS', struct.pack('<h', 9347))

        reg = GameRegistry.get_game('tes5')
        npc.schema = reg.get('NPC_')
        npc.modified = True

        flat = npc._flatten_children()
        tint_sigs = [sr.signature for sr in flat
                     if sr.signature in ('TINI', 'TINC', 'TINV', 'TIAS')]
        expected = ['TINI', 'TINC', 'TINV', 'TIAS',
                    'TINI', 'TINC', 'TINV', 'TIAS']
        assert tint_sigs == expected, \
            f"Tints should be interleaved, got {tint_sigs}"


    def test_tints_after_add_and_remove(self):
        """Adding/removing tint layers preserves interleaved order."""
        from esplib.defs.game import GameRegistry

        npc = Record('NPC_', FormID(0x100), 0)
        npc.add_subrecord('EDID', b'TestNPC\x00')
        npc.add_subrecord('ACBS', b'\x00' * 24)
        npc.add_subrecord('FULL', b'Test\x00')

        npc.add_subrecord('TINI', struct.pack('<H', 1))
        npc.add_subrecord('TINC', bytes([255, 0, 0, 0]))
        npc.add_subrecord('TINV', struct.pack('<i', 50))
        npc.add_subrecord('TIAS', struct.pack('<h', 100))

        reg = GameRegistry.get_game('tes5')
        npc.schema = reg.get('NPC_')

        npc.remove_subrecords('TINI')
        npc.remove_subrecords('TINC')
        npc.remove_subrecords('TINV')
        npc.remove_subrecords('TIAS')
        npc.children = None

        npc.add_subrecord('TINI', struct.pack('<H', 10))
        npc.add_subrecord('TINC', bytes([0, 255, 0, 0]))
        npc.add_subrecord('TINV', struct.pack('<i', 75))
        npc.add_subrecord('TIAS', struct.pack('<h', 200))

        npc.add_subrecord('TINI', struct.pack('<H', 20))
        npc.add_subrecord('TINC', bytes([0, 0, 255, 0]))
        npc.add_subrecord('TINV', struct.pack('<i', 90))
        npc.add_subrecord('TIAS', struct.pack('<h', 300))

        npc.modified = True
        flat = npc._flatten_children()
        tint_sigs = [sr.signature for sr in flat
                     if sr.signature in ('TINI', 'TINC', 'TINV', 'TIAS')]
        expected = ['TINI', 'TINC', 'TINV', 'TIAS',
                    'TINI', 'TINC', 'TINV', 'TIAS']
        assert tint_sigs == expected

        all_sigs = [sr.signature for sr in flat]
        full_idx = all_sigs.index('FULL')
        tini_idx = all_sigs.index('TINI')
        assert full_idx < tini_idx, "FULL should come before tints"
