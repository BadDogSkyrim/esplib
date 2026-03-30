"""Tests for Plugin features: FormID remapping, string delocalization, copy_record.

Includes both synthetic tests and gamefiles tests that use Skyrim.esm.
"""

import struct
import tempfile
import pytest
from pathlib import Path

from esplib import Plugin, Record, FormID
from esplib.record import SubRecord

from tests.conftest import (
    find_skyrim_esm, find_skyrim_data, find_strings_dir,
    make_simple_plugin, make_subrecord,
)


# ===================================================================
# Synthetic tests (no game files needed)
# ===================================================================


class TestRemapFormID:
    """Plugin.remap_formid() translates FormIDs between master lists."""


    def test_remap_local_to_master(self):
        """A local record in source becomes a master reference in dest."""
        import esplib.defs.tes5

        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm', 'Source.esp'])

        # FormID 0x01000ABC in source = local record (master[1] = self)
        # Source has 1 master, so local index = 1
        fid = (1 << 24) | 0x000ABC
        remapped = dest.remap_formid(fid, source)

        # In dest, Source.esp is master[1]
        assert (remapped >> 24) & 0xFF == 1
        assert remapped & 0x00FFFFFF == 0x000ABC


    def test_remap_shared_master(self):
        """A reference to a shared master keeps the same object ID."""
        import esplib.defs.tes5

        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm', 'Update.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm', 'Update.esm', 'Source.esp'])

        # FormID 0x00013746 in source = Skyrim.esm record (master[0])
        fid = 0x00013746
        remapped = dest.remap_formid(fid, source)

        # Skyrim.esm is master[0] in both
        assert remapped == 0x00013746


    def test_remap_different_master_order(self):
        """Masters at different indices get remapped correctly."""
        import esplib.defs.tes5

        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm', 'Dawnguard.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm', 'Update.esm',
                                          'Dawnguard.esm', 'Source.esp'])

        # FormID 0x01000123 in source = Dawnguard.esm record (master[1])
        fid = (1 << 24) | 0x000123
        remapped = dest.remap_formid(fid, source)

        # In dest, Dawnguard.esm is master[2]
        assert (remapped >> 24) & 0xFF == 2
        assert remapped & 0x00FFFFFF == 0x000123


    def test_remap_unknown_master_unchanged(self):
        """A FormID referencing an unknown master passes through unchanged."""
        import esplib.defs.tes5

        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm', 'Missing.esm'])
        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Dest.esp',
                                 masters=['Skyrim.esm'])

        # master[1] = Missing.esm, not in dest
        fid = (1 << 24) | 0x000123
        remapped = dest.remap_formid(fid, source)

        # Can't remap — returned unchanged
        assert remapped == fid


class TestCopyRecordDelocalization:
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
        import esplib.defs.tes5

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
        import esplib.defs.tes5

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
        import esplib.defs.tes5

        source = self._make_localized_plugin({42: 'Iron Sword'})

        rec = Record('WEAP', FormID(0x100), 0)
        rec.add_subrecord('FULL', struct.pack('<I', 42))
        rec._plugin = source

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esm')
        dest.header.is_localized = True

        copied = dest.copy_record(rec)
        full = copied.get_subrecord('FULL')
        # Should still be 4 bytes (string ID), not delocalized
        assert full.size == 4
        assert struct.unpack('<I', full.data)[0] == 42


    def test_no_delocalize_nonlocalized_source(self):
        """Non-localized source records are copied as-is."""
        import esplib.defs.tes5

        rec = Record('WEAP', FormID(0x100), 0)
        rec.add_subrecord('FULL', b'Iron Sword\x00')
        # No _plugin set, or _plugin.is_localized = False

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esp')

        copied = dest.copy_record(rec)
        full = copied.get_subrecord('FULL')
        assert full.get_string() == 'Iron Sword'


class TestCopyRecordMasters:
    """copy_record uses record._plugin for master resolution."""


    def test_copy_adds_masters_from_plugin_ref(self):
        """copy_record adds source plugin's masters via _plugin back-ref."""
        import esplib.defs.tes5

        source = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Source.esp',
                                   masters=['Skyrim.esm'])
        source.file_path = Path('Source.esp')

        rec = Record('WEAP', FormID(0x100), 0)
        rec._plugin = source

        dest = Plugin.new_plugin(Path(tempfile.mkdtemp()) / 'Patch.esp')
        assert len(dest.header.masters) == 0

        dest.copy_record(rec)

        assert 'Skyrim.esm' in dest.header.masters
        assert 'Source.esp' in dest.header.masters


# ===================================================================
# Gamefiles tests (require Skyrim.esm + string tables)
# ===================================================================


class TestNPCTintAutoSort:
    """Tint layers stay interleaved after auto-sort on modified records."""


    def test_tints_interleaved_after_sort(self):
        """Modified NPC record preserves TINI/TINC/TINV/TIAS grouping."""
        import esplib.defs.tes5
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
        import esplib.defs.tes5
        from esplib.defs.game import GameRegistry

        npc = Record('NPC_', FormID(0x100), 0)
        npc.add_subrecord('EDID', b'TestNPC\x00')
        npc.add_subrecord('ACBS', b'\x00' * 24)
        npc.add_subrecord('FULL', b'Test\x00')

        # Start with one tint
        npc.add_subrecord('TINI', struct.pack('<H', 1))
        npc.add_subrecord('TINC', bytes([255, 0, 0, 0]))
        npc.add_subrecord('TINV', struct.pack('<i', 50))
        npc.add_subrecord('TIAS', struct.pack('<h', 100))

        reg = GameRegistry.get_game('tes5')
        npc.schema = reg.get('NPC_')

        # Remove tints and add new ones
        npc.remove_subrecords('TINI')
        npc.remove_subrecords('TINC')
        npc.remove_subrecords('TINV')
        npc.remove_subrecords('TIAS')
        npc.children = None  # force re-restructure

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

        # Verify FULL is before tints (schema ordering)
        all_sigs = [sr.signature for sr in flat]
        full_idx = all_sigs.index('FULL')
        tini_idx = all_sigs.index('TINI')
        assert full_idx < tini_idx, "FULL should come before tints"


class TestRemapFormIDGamefiles:
    """remap_formid with real game data."""


    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin


    @pytest.mark.gamefiles
    def test_remap_skyrim_record(self, skyrim):
        """Remap a Skyrim.esm FormID into a patch with different master order."""
        import esplib.defs.tes5

        dest = Plugin.new_plugin(
            Path(tempfile.mkdtemp()) / 'Patch.esp',
            masters=['Update.esm', 'Skyrim.esm'])

        # NordRace is 0x00013746 in Skyrim.esm (master[0] in Skyrim's own list)
        # Skyrim.esm has no masters, so local index = 0
        nord_fid = 0x00013746
        remapped = dest.remap_formid(nord_fid, skyrim)

        # In dest, Skyrim.esm is master[1]
        assert (remapped >> 24) & 0xFF == 1
        assert remapped & 0x00FFFFFF == 0x013746


class TestDelocalizeGamefiles:
    """String delocalization with real Skyrim.esm."""


    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin


    @pytest.mark.gamefiles
    def test_copy_race_delocalizes_full(self, skyrim):
        """Copying NordRace from Skyrim.esm delocalizes FULL to 'Nord'."""
        import esplib.defs.tes5

        if not skyrim.string_tables:
            pytest.skip("String tables not loaded")

        nord = None
        for r in skyrim.get_records_by_signature('RACE'):
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
