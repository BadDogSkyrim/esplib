"""Tests for the LocalFormID / AbsoluteFormID type split."""

import struct
import pytest
from esplib import (
    Plugin, Record, FormID, LocalFormID, AbsoluteFormID, BaseFormID,
)


class TestTypeHierarchy:

    def test_formid_is_local(self):
        assert FormID is LocalFormID


    def test_isinstance_base(self):
        local = LocalFormID(0x01000800)
        absolute = AbsoluteFormID(0x01000800)
        assert isinstance(local, BaseFormID)
        assert isinstance(absolute, BaseFormID)


    def test_isinstance_specific(self):
        local = LocalFormID(0x01000800)
        absolute = AbsoluteFormID(0x01000800)
        assert isinstance(local, LocalFormID)
        assert not isinstance(local, AbsoluteFormID)
        assert isinstance(absolute, AbsoluteFormID)
        assert not isinstance(absolute, LocalFormID)


    def test_local_has_file_index(self):
        fid = LocalFormID(0x03000800)
        assert fid.file_index == 3
        assert fid.object_index == 0x800


    def test_absolute_has_load_index(self):
        fid = AbsoluteFormID(0x03000800)
        assert fid.load_index == 3
        assert fid.object_index == 0x800


    def test_absolute_no_file_index(self):
        fid = AbsoluteFormID(0x03000800)
        with pytest.raises(AttributeError):
            _ = fid.file_index


    def test_local_no_load_index(self):
        fid = LocalFormID(0x03000800)
        with pytest.raises(AttributeError):
            _ = fid.load_index


class TestEquality:

    def test_same_type_equal(self):
        assert LocalFormID(0x800) == LocalFormID(0x800)
        assert AbsoluteFormID(0x800) == AbsoluteFormID(0x800)


    def test_cross_type_not_equal(self):
        assert LocalFormID(0x800) != AbsoluteFormID(0x800)


    def test_int_comparison(self):
        assert LocalFormID(0x800) == 0x800
        assert AbsoluteFormID(0x800) == 0x800


    def test_hash_same_value(self):
        """Same raw value hashes the same (benign collision)."""
        assert hash(LocalFormID(0x800)) == hash(AbsoluteFormID(0x800))


    def test_hash_stable_within_type(self):
        assert hash(LocalFormID(0x800)) == hash(LocalFormID(0x800))


class TestStringRepresentation:

    def test_local_repr(self):
        assert repr(LocalFormID(0x01000800)) == 'LocalFormID(0x01000800)'


    def test_absolute_repr(self):
        assert repr(AbsoluteFormID(0x01000800)) == 'AbsoluteFormID(0x01000800)'


    def test_str_same_format(self):
        """Both types produce the same string display."""
        assert str(LocalFormID(0x01000800)) == str(AbsoluteFormID(0x01000800))


class TestFromString:

    def test_from_string_returns_local(self):
        fid = FormID.from_string('[01] 000800')
        assert isinstance(fid, LocalFormID)
        assert fid.value == 0x01000800


class TestNormalizeDenormalize:

    def test_normalize_returns_absolute(self, tmp_path):
        from esplib import PluginSet, LoadOrder

        p_path = tmp_path / 'Test.esp'
        p = Plugin.new_plugin(p_path, masters=['Skyrim.esm'])
        p.save()

        lo = LoadOrder.from_list(['Skyrim.esm', 'Test.esp'],
                                 data_dir=tmp_path)
        ps = PluginSet(lo)
        ps.load_all()
        plugin = ps.get_plugin('Test.esp')

        local_fid = FormID(0x00000800)  # file_index=0 -> Skyrim.esm
        result = plugin.normalize_form_id(local_fid)
        assert isinstance(result, AbsoluteFormID)


    def test_resolve_form_id_with_absolute(self, tmp_path):
        """AbsoluteFormID can be passed to resolve_form_id without a plugin."""
        from esplib import PluginSet

        p_path = tmp_path / 'Test.esp'
        p = Plugin.new_plugin(p_path)
        rec = Record('WEAP', FormID(0x800), 0)
        rec.add_subrecord('EDID', b'TestSword\x00')
        p.add_record(rec)
        p.save()

        ps = PluginSet.from_plugin(p_path)
        plugin = ps.get_plugin('Test.esp')
        norm = plugin.normalize_form_id(FormID(0x800))

        # Can resolve with just the AbsoluteFormID, no plugin needed
        result = ps.resolve_form_id(norm)
        assert result is not None
        assert result.editor_id == 'TestSword'


    def test_resolve_form_id_local_requires_plugin(self):
        """Passing a LocalFormID without source_plugin raises TypeError."""
        from esplib import PluginSet, LoadOrder

        lo = LoadOrder.from_list([], data_dir='.')
        ps = PluginSet(lo)

        with pytest.raises(TypeError, match='source_plugin is required'):
            ps.resolve_form_id(FormID(0x800))


    def test_schema_access_returns_absolute_in_pluginset(self, tmp_path):
        """record['FIELD'] returns AbsoluteFormID when PluginSet is present."""
        from esplib import PluginSet

        p_path = tmp_path / 'Test.esp'
        p = Plugin.new_plugin(p_path, masters=['Skyrim.esm'])

        npc = Record('NPC_', FormID(0x800), 0)
        npc.add_subrecord('EDID', b'TestNPC\x00')
        # TPLT references file_index=0 (Skyrim.esm), object 0x123
        npc.add_subrecord('TPLT', struct.pack('<I', 0x00000123))
        p.add_record(npc)
        p.save()

        ps = PluginSet.from_plugin(p_path)
        plugin = ps.get_plugin('Test.esp')
        npc_loaded = plugin.get_record_by_editor_id('TestNPC')

        tplt = npc_loaded['TPLT']
        assert isinstance(tplt, AbsoluteFormID), \
            f"Expected AbsoluteFormID, got {type(tplt).__name__}"
