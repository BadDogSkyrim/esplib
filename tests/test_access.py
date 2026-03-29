"""Tests for typed record access via Record.__getitem__/__setitem__."""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5, GameRegistry, EspContext

from tests.conftest import find_skyrim_esm, make_simple_plugin


class TestRecordGetItem:
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


class TestRecordSetItem:
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

    def test_write_wrong_type_without_schema_raises(self):
        record = Record('WEAP', FormID(0x800), 0)
        with pytest.raises(TypeError):
            record['DATA'] = 42


class TestRecordRoundTrip:
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


class TestPluginSetGame:
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
            pytest.skip("IronSword not found")

        data = weapon['DATA']
        assert isinstance(data, dict)
        assert data['damage'] == 7
        assert data['value'] == 25

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_modify_and_read_back(self, skyrim):
        """Modify a weapon's damage in memory and read it back."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            pytest.skip("IronSword not found")

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
