"""Tests for typed record access via Record.__getitem__/__setitem__."""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5, GameRegistry, EspContext


class TestStructGetItem:
    """Test reading fields via record[sig]."""


    def test_read_with_schema(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'TestSword\x00')
        record.add_subrecord('DATA',
                             struct.pack('<I', 25) +
                             struct.pack('<f', 9.0) +
                             struct.pack('<H', 7))
        record.schema = tes5.WEAP

        assert record['EDID'] == 'TestSword'
        data = record['DATA']
        assert data['value'] == 25
        assert data['damage'] == 7
        assert abs(data['weight'] - 9.0) < 0.001


    def test_read_without_schema_returns_subrecord(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')

        sr = record['EDID']
        assert isinstance(sr, SubRecord)
        assert sr.get_string() == 'Test'


    def test_read_missing_subrecord_with_schema(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        record.schema = tes5.WEAP

        # Known signature but not present
        assert record['DATA'] is None


    def test_read_missing_subrecord_without_schema_raises(self):
        record = Record('WEAP', FormID(0x800), 0)
        with pytest.raises(KeyError):
            record['DATA']


    def test_caching(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        record.schema = tes5.WEAP

        val1 = record['EDID']
        val2 = record['EDID']
        assert val1 == val2
        assert 'EDID' in record._resolved_cache


    def test_contains(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')

        assert 'EDID' in record
        assert 'DATA' not in record


class TestStructSetItem:
    """Test writing fields via record[sig] = value."""


    def test_write_struct_with_schema(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('DATA',
                             struct.pack('<I', 25) +
                             struct.pack('<f', 9.0) +
                             struct.pack('<H', 7))
        record.schema = tes5.WEAP

        # Read, modify, write back
        data = record['DATA']
        assert data['damage'] == 7
        data['damage'] = 50
        record['DATA'] = data

        # Re-read to verify
        record._resolved_cache.clear()
        data2 = record['DATA']
        assert data2['damage'] == 50
        assert data2['value'] == 25  # unchanged


    def test_write_clears_cache(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        record.schema = tes5.WEAP

        _ = record['EDID']  # populate cache
        assert 'EDID' in record._resolved_cache

        record['EDID'] = 'NewName'
        assert 'EDID' not in record._resolved_cache


    def test_write_marks_modified(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        record.schema = tes5.WEAP
        record.modified = False

        record['EDID'] = 'Changed'
        assert record.modified


    def test_write_creates_subrecord_if_missing(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.schema = tes5.WEAP

        record['EDID'] = 'NewWeapon'
        assert record.get_subrecord('EDID') is not None
        record._resolved_cache.clear()
        assert record['EDID'] == 'NewWeapon'


    def test_write_raw_bytes_without_schema(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('DATA', b'\x00' * 10)

        new_data = struct.pack('<I', 50) + struct.pack('<f', 3.0) + struct.pack('<H', 20)
        record['DATA'] = new_data
        assert record.get_subrecord('DATA').data == new_data


    def test_write_int_without_schema_stores_bytes(self):
        record = Record('WEAP', FormID(0x800), 0)
        record['DATA'] = 42
        assert record.get_subrecord('DATA').data == bytearray(b'\x2a')


    def test_write_unsupported_type_without_schema_raises(self):
        record = Record('WEAP', FormID(0x800), 0)
        with pytest.raises(TypeError):
            record['DATA'] = [1, 2, 3]


class TestStructRoundTrip:
    """Test read-modify-write round trips."""


    def test_modify_weapon_damage(self):
        """Modify damage, verify raw bytes change correctly."""
        record = Record('WEAP', FormID(0x800), 0)
        original_data = (struct.pack('<I', 100) +
                         struct.pack('<f', 5.0) +
                         struct.pack('<H', 15))
        record.add_subrecord('DATA', original_data)
        record.schema = tes5.WEAP

        # Modify damage
        data = record['DATA']
        assert data['damage'] == 15
        data['damage'] = 99
        record['DATA'] = data

        # Check raw bytes
        sr = record.get_subrecord('DATA')
        expected = (struct.pack('<I', 100) +
                    struct.pack('<f', 5.0) +
                    struct.pack('<H', 99))
        assert sr.data == expected


    def test_modify_preserves_other_fields(self):
        """Modifying one field in a struct preserves all others."""
        record = Record('ARMO', FormID(0x900), 0)
        record.add_subrecord('DATA',
                             struct.pack('<i', 500) +
                             struct.pack('<f', 15.0))
        record.schema = tes5.ARMO

        data = record['DATA']
        data['value'] = 999
        record['DATA'] = data

        record._resolved_cache.clear()
        data2 = record['DATA']
        assert data2['value'] == 999
        assert abs(data2['weight'] - 15.0) < 0.001


class TestStructSetGame:
    """Test Plugin.set_game() and auto_detect_game()."""


    def test_set_game_binds_schemas(self):
        plugin = Plugin()
        plugin.header.version = 1.71
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'Test\x00')
        plugin.records.append(record)

        # Ensure tes5 is imported (triggers registration)
        import esplib.defs.tes5

        plugin.set_game('tes5')
        assert record.schema is not None
        assert record.schema.signature == 'WEAP'


    def test_set_game_unknown_raises(self):
        plugin = Plugin()
        with pytest.raises(Exception):
            plugin.set_game('unknown_game')


    def test_auto_detect_game(self):
        plugin = Plugin()
        plugin.header.version = 1.71

        record = Record('WEAP', FormID(0x800), 0)
        plugin.records.append(record)

        import esplib.defs.tes5
        plugin.auto_detect_game()
        assert record.schema is not None


    def test_records_without_definition_get_no_schema(self):
        plugin = Plugin()
        record = Record('ZZZZ', FormID(0x800), 0)  # unknown type
        plugin.records.append(record)

        import esplib.defs.tes5
        plugin.set_game('tes5')
        assert record.schema is None


class TestSkyrimAccess:
    """Test typed access against real Skyrim.esm records."""


    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_sword_access(self, skyrim):
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            assert False, "IronSword not found in Skyrim.esm"

        data = weapon['DATA']
        assert isinstance(data, dict)
        assert data['damage'] == 7
        assert data['value'] == 25
        assert data['weight'] == pytest.approx(9.0)

        dnam = weapon['DNAM']
        if dnam is None:
            assert False, "DNAM not present on IronSword"

        assert 'speed' in dnam
        assert 'reach' in dnam
        assert dnam['speed'] > 0
        assert dnam['reach'] > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_npc_acbs_typed_access(self, skyrim):
        """NPC_ ACBS config accessible via typed access."""
        npc = skyrim.get_record_by_editor_id('Bryling')
        acbs = npc['ACBS']
        assert acbs
        assert 'level' in acbs
        assert 'flags' in acbs
        assert acbs['level'] == 9
        assert acbs['flags'].Female, "Bryling should be female"
        assert 'Female' in acbs['flags']
        assert not acbs['flags'].Is_CharGen_Face_Preset


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_enchanted_weapon_with_template(self, skyrim):
        """Enchanted weapon should have CNAM template reference."""
        weapon = skyrim.get_record_by_editor_id('EnchSteelWarAxeStamina2')
        if not weapon:
            assert False, "EnchSteelWarAxeStamina2 not found in Skyrim.esm"

        cnam = weapon['CNAM']
        assert cnam is not None
        assert hasattr(cnam, 'value')
        assert cnam.value != 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_modify_and_read_back(self, skyrim):
        """Modify a weapon's damage in memory and read it back."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            assert False, "IronSword not found in Skyrim.esm"

        data = weapon['DATA']
        original_damage = data['damage']

        data['damage'] = 999
        weapon['DATA'] = data

        weapon._resolved_cache.clear()
        data2 = weapon['DATA']
        assert data2['damage'] == 999

        # Restore original
        data2['damage'] = original_damage
        weapon['DATA'] = data2


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_modify_skyrim_record_save_reload(self, skyrim, tmp_path):
        """Copy a Skyrim record, modify it, save to file, reload, verify."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        assert weapon is not None

        patch = Plugin.new_plugin(tmp_path / 'patch.esp',
                                  masters=['Skyrim.esm'])
        copied = patch.copy_record(weapon)

        data = copied['DATA']
        data['damage'] = 999
        copied['DATA'] = data

        patch.save()

        reloaded = Plugin(tmp_path / 'patch.esp')
        rec = reloaded.records[0]
        assert rec.editor_id == 'IronSword'
        reloaded_data = rec['DATA']
        assert reloaded_data['damage'] == 999


class TestPluginTypedAccess:
    """Create records using typed access, save, reload, verify."""


    def test_write_weapon_data_via_typed_access(self, tmp_path):
        """record['DATA'] = dict should produce correct bytes on disk."""
        path = tmp_path / 'typed_weapon.esp'
        plugin = Plugin.new_plugin(path, masters=['Skyrim.esm'])

        weap = Record('WEAP')
        weap.schema = tes5.WEAP
        weap['EDID'] = 'TestSword'
        weap['DATA'] = {'value': 9999, 'weight': 5.0, 'damage': 100}

        plugin.add_record(weap)
        assert weap.form_id.value != 0, "FormID should be auto-assigned"
        plugin.save()

        loaded = Plugin(path)
        assert loaded.header.version == pytest.approx(1.71, abs=0.01)
        assert loaded.header.masters == ['Skyrim.esm']
        assert len(loaded.header.master_sizes) == 1

        # Schema should be auto-detected from v1.71 header
        rec = loaded.get_record_by_editor_id('TestSword')
        assert rec is not None
        assert rec.schema is not None, "Schema should be auto-detected"
        assert rec.editor_id == 'TestSword'

        data = rec['DATA']
        assert data['value'] == 9999
        assert data['weight'] == pytest.approx(5.0)
        assert data['damage'] == 100


class TestPluginMultipleRecordAccess:
    """Test typed access across multiple records in one plugin."""


    def test_two_weapons_independent_data(self, tmp_path):
        """Two weapons in one plugin, each with different typed data."""
        path = tmp_path / 'two_weapons.esp'
        plugin = Plugin.new_plugin(path, masters=['Skyrim.esm'])

        sword = Record('WEAP')
        sword.schema = tes5.WEAP
        sword['EDID'] = 'TestSword'
        sword['DATA'] = {'value': 100, 'weight': 5.0, 'damage': 50}
        plugin.add_record(sword)

        axe = Record('WEAP')
        axe.schema = tes5.WEAP
        axe['EDID'] = 'TestAxe'
        axe['DATA'] = {'value': 200, 'weight': 8.0, 'damage': 75}
        plugin.add_record(axe)

        plugin.save()

        loaded = Plugin(path)
        s = loaded.get_record_by_editor_id('TestSword')
        a = loaded.get_record_by_editor_id('TestAxe')

        assert s.version == 44, "Record version should be 44 for tes5"
        assert a.version == 44

        assert s['DATA']['damage'] == 50
        assert s['DATA']['value'] == 100
        assert a['DATA']['damage'] == 75
        assert a['DATA']['value'] == 200


    def test_weapon_with_template_cnam(self, tmp_path):
        """CNAM (template FormID) should round-trip via typed access."""
        path = tmp_path / 'template_test.esp'
        plugin = Plugin.new_plugin(path, masters=['Skyrim.esm'])

        axe = Record('WEAP')
        axe.schema = tes5.WEAP
        axe['EDID'] = 'TemplatedAxe'
        axe['DATA'] = {'value': 5555, 'weight': 8.0, 'damage': 75}
        axe.add_subrecord('CNAM', struct.pack('<I', 0x00013983))
        plugin.add_record(axe)

        plugin.save()

        loaded = Plugin(path)
        rec = loaded.get_record_by_editor_id('TemplatedAxe')
        assert rec.version == 44

        cnam = rec['CNAM']
        assert cnam is not None
        assert cnam.value == 0x00013983
