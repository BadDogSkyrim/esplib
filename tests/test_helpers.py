"""Tests for Phase E: FormList and Global Variable helpers."""

import struct
import pytest
from pathlib import Path

from esplib import (
    Plugin, Record, SubRecord, FormID,
    flst_forms, flst_contains, flst_add, flst_remove,
    glob_value, glob_set_value, glob_copy_as,
    race_height,
)
from tests.conftest import make_subrecord, make_simple_plugin


class TestPluginFormListHelpers:


    def _make_flst(self, form_ids):
        """Create a FLST record with given FormIDs."""
        record = Record('FLST', FormID(0x100), 0)
        record.add_subrecord('EDID', b'TestList\x00')
        for fid in form_ids:
            record.add_subrecord('LNAM', struct.pack('<I', fid))
        return record


    def test_forms_empty(self):
        record = self._make_flst([])
        assert flst_forms(record) == []


    def test_forms_multiple(self):
        record = self._make_flst([0x100, 0x200, 0x300])
        forms = flst_forms(record)
        assert len(forms) == 3
        assert forms[0].value == 0x100
        assert forms[1].value == 0x200
        assert forms[2].value == 0x300


    def test_contains_true(self):
        record = self._make_flst([0x100, 0x200])
        assert flst_contains(record, 0x200)
        assert flst_contains(record, FormID(0x100))


    def test_contains_false(self):
        record = self._make_flst([0x100])
        assert not flst_contains(record, 0x999)


    def test_add(self):
        record = self._make_flst([0x100])
        flst_add(record, 0x200)
        forms = flst_forms(record)
        assert len(forms) == 2
        assert forms[1].value == 0x200


    def test_add_formid(self):
        record = self._make_flst([])
        flst_add(record, FormID(0x42))
        assert flst_contains(record, 0x42)


    def test_remove_existing(self):
        record = self._make_flst([0x100, 0x200, 0x300])
        assert flst_remove(record, 0x200)
        forms = flst_forms(record)
        assert len(forms) == 2
        assert forms[0].value == 0x100
        assert forms[1].value == 0x300


    def test_remove_nonexistent(self):
        record = self._make_flst([0x100])
        assert not flst_remove(record, 0x999)
        assert len(flst_forms(record)) == 1


    def test_roundtrip(self, tmp_path):
        """Create a FLST plugin, save, reload, verify forms intact."""
        plugin = Plugin.new_plugin(tmp_path / 'test_flst.esp')

        # Create a FLST record
        flst = Record('FLST', FormID(0x800), 0)
        flst.add_subrecord('EDID', b'TestFormList\x00')
        flst_add(flst, 0x01000100)
        flst_add(flst, 0x01000200)
        flst_add(flst, 0x01000300)
        plugin.add_record(flst)
        plugin.save()

        # Reload
        loaded = Plugin(tmp_path / 'test_flst.esp')
        loaded_flst = loaded.get_record_by_editor_id('TestFormList')
        assert loaded_flst is not None
        forms = flst_forms(loaded_flst)
        assert len(forms) == 3
        assert forms[0].value == 0x01000100
        assert forms[1].value == 0x01000200
        assert forms[2].value == 0x01000300


class TestPluginGlobalVariableHelpers:


    def _make_glob(self, value=0.0, glob_type=ord('f')):
        """Create a GLOB record."""
        record = Record('GLOB', FormID(0x100), 0)
        record.add_subrecord('EDID', b'TestGlobal\x00')
        record.add_subrecord('FNAM', struct.pack('<B', glob_type))
        record.add_subrecord('FLTV', struct.pack('<f', value))
        return record


    def test_read_value(self):
        record = self._make_glob(42.5)
        assert glob_value(record) == pytest.approx(42.5)


    def test_read_zero(self):
        record = self._make_glob(0.0)
        assert glob_value(record) == 0.0


    def test_set_value(self):
        record = self._make_glob(1.0)
        glob_set_value(record, 99.5)
        assert glob_value(record) == pytest.approx(99.5)
        assert record.modified


    def test_set_value_creates_fltv(self):
        record = Record('GLOB', FormID(0x100), 0)
        record.add_subrecord('EDID', b'TestGlobal\x00')
        glob_set_value(record, 7.0)
        assert glob_value(record) == pytest.approx(7.0)


    def test_copy_as(self):
        original = self._make_glob(10.0)
        copy = glob_copy_as(original, 'CopiedGlobal', 0x900)
        assert copy.form_id.value == 0x900
        assert copy.editor_id == 'CopiedGlobal'
        assert glob_value(copy) == pytest.approx(10.0)
        # Original unchanged
        assert original.editor_id == 'TestGlobal'
        assert original.form_id.value == 0x100


    def test_copy_as_independent(self):
        original = self._make_glob(5.0)
        copy = glob_copy_as(original, 'Copy', 0x900)
        glob_set_value(copy, 99.0)
        assert glob_value(original) == pytest.approx(5.0)


    def test_roundtrip(self, tmp_path):
        """Create a GLOB plugin, save, reload, verify value."""
        plugin = Plugin.new_plugin(tmp_path / 'test_glob.esp')

        glob = self._make_glob(123.456)
        glob.form_id = FormID(0x800)
        plugin.add_record(glob)
        plugin.save()

        loaded = Plugin(tmp_path / 'test_glob.esp')
        loaded_glob = loaded.get_record_by_editor_id('TestGlobal')
        assert loaded_glob is not None
        assert glob_value(loaded_glob) == pytest.approx(123.456, rel=1e-5)


class TestRaceHeight:
    """FO4 RACE height accessor (DATA floats at offset 0 male / 4 female)."""


    def _make_race(self, male=1.0, female=1.0, trailing=40):
        record = Record('RACE', FormID(0x100), 0)
        record.add_subrecord('EDID', b'TestRace\x00')
        # DATA: two leading f32 heights then the opaque version-dependent rest.
        record.add_subrecord('DATA',
                             struct.pack('<ff', male, female) + b'\x00' * trailing)
        return record


    def test_reads_male_and_female(self):
        race = self._make_race(male=1.0, female=0.98)
        assert race_height(race, female=False) == pytest.approx(1.0)
        assert race_height(race, female=True) == pytest.approx(0.98)


    def test_missing_data_defaults_to_one(self):
        race = Record('RACE', FormID(0x100), 0)
        race.add_subrecord('EDID', b'NoData\x00')
        assert race_height(race) == 1.0


    def test_short_data_defaults_to_one(self):
        race = self._make_race(trailing=0)  # 8 bytes is enough...
        assert race_height(race, female=True) == pytest.approx(1.0)
        short = Record('RACE', FormID(0x100), 0)
        short.add_subrecord('DATA', struct.pack('<f', 1.0))  # only 4 bytes
        assert race_height(short, female=True) == 1.0


    def test_none_record_defaults_to_one(self):
        assert race_height(None) == 1.0
