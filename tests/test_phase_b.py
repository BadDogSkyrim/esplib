"""Tests for Phase B: Record copy and patch file operations."""

import struct
import pytest
from pathlib import Path

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5

from tests.conftest import find_skyrim_esm


class TestRecordCopy:
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
        record = Record('WEAP', FormID(0x800), 0)
        record.schema = tes5.WEAP
        copy = record.copy()
        assert copy.schema is tes5.WEAP

    def test_has_subrecord(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        assert record.has_subrecord('EDID')
        assert not record.has_subrecord('DATA')


class TestNewPlugin:
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


class TestAddMaster:
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


class TestAddRecursiveMasters:
    def test_recursive_masters(self, tmp_path):
        # Source plugin depends on Skyrim.esm + Update.esm
        source = Plugin.new_plugin(tmp_path / 'source.esp',
                                   masters=['Skyrim.esm', 'Update.esm'])
        source.save()

        # Target gets source's masters + source itself
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

        # Skyrim.esm should only appear once
        assert target.header.masters.count('Skyrim.esm') == 1
        assert 'mod.esp' in target.header.masters


class TestCopyRecord:
    def test_copy_record_to_plugin(self, tmp_path):
        # Create source with a weapon
        source = Plugin.new_plugin(tmp_path / 'source.esp',
                                   masters=['Skyrim.esm'])
        weap = Record('WEAP', FormID(0x01000800), 0)
        weap.add_subrecord('EDID', b'TestSword\x00')
        weap.add_subrecord('DATA', struct.pack('<Ifh', 25, 0, 7))
        source.add_record(weap)
        source.save()

        # Copy to target
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

        # Modify original -- copy should be unaffected
        rec.subrecords[0].set_string('Changed')
        assert copied.editor_id == 'Gold'

    def test_save_and_reload_copied_plugin(self, tmp_path):
        source = Plugin.new_plugin(tmp_path / 'src.esp',
                                   masters=['Skyrim.esm'])
        rec = Record('WEAP', FormID(0x00012EB7), 0)  # Override IronSword
        rec.add_subrecord('EDID', b'IronSword\x00')
        source.add_record(rec)
        source.save()

        target = Plugin.new_plugin(tmp_path / 'patch.esp')
        target.copy_record(rec, source)
        target.save()

        # Reload and verify
        reloaded = Plugin(tmp_path / 'patch.esp')
        assert len(reloaded.records) == 1
        assert reloaded.records[0].editor_id == 'IronSword'
        assert 'Skyrim.esm' in reloaded.header.masters


class TestCopyFromSkyrim:
    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_copy_iron_sword(self, tmp_path):
        from tests.conftest import find_skyrim_esm
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")

        skyrim = Plugin(esm_path)
        sword = skyrim.get_record_by_editor_id('IronSword')
        assert sword is not None

        patch = Plugin.new_plugin(tmp_path / 'test_patch.esp')
        copied = patch.copy_record(sword, skyrim)
        patch.save()

        # Reload and verify
        reloaded = Plugin(tmp_path / 'test_patch.esp')
        assert len(reloaded.records) == 1
        assert reloaded.records[0].form_id.value == sword.form_id.value
