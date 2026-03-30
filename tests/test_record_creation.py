"""Record creation tests: synthetic plugin workflows and Skyrim.esm validation.

Covers creating plugins from scratch, adding records with schemas,
saving/reloading, and verifying field values against real game data.
"""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5


# ---------------------------------------------------------------------------
# Plugin Creation
# ---------------------------------------------------------------------------

class TestPluginCreation:
    """Test creating new plugins, saving, and reloading."""


    def test_create_empty_plugin(self, tmp_path):
        """An empty plugin should save and reload with correct header."""
        plugin = Plugin()
        plugin.header.version = 1.71
        plugin.header.is_esm = False

        path = tmp_path / "empty.esp"
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.header.version == pytest.approx(1.71, abs=0.01)
        assert not loaded.is_esm
        assert len(loaded.records) == 0


    def test_create_esm_flag(self, tmp_path):
        """ESM flag should survive save/reload."""
        plugin = Plugin()
        plugin.header.is_esm = True
        plugin.header.version = 1.71

        path = tmp_path / "test.esm"
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.is_esm


    def test_create_plugin_with_masters(self, tmp_path):
        """Master list should survive save/reload."""
        plugin = Plugin()
        plugin.header.version = 1.71
        plugin.header.masters = ['Skyrim.esm', 'Update.esm']
        plugin.header.master_sizes = [0, 0]

        path = tmp_path / "with_masters.esp"
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.header.masters == ['Skyrim.esm', 'Update.esm']


    def test_gmst_override_save_reload(self, tmp_path):
        """Create a GMST override, save, reload, verify field values."""
        plugin = Plugin()
        plugin.header.is_esm = False
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        gmst = Record('GMST', FormID(0x00066C5B), 0)
        gmst.timestamp = 0
        gmst.version = 44
        gmst.version_control_info = 0
        gmst.add_subrecord('EDID', b'fJumpHeightMin\x00')
        data_sr = gmst.add_subrecord('DATA')
        data_sr.data = struct.pack('<f', 500.0)

        plugin.add_record(gmst)

        path = tmp_path / 'gmst_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.header.masters == ['Skyrim.esm']
        assert len(loaded.records) == 1

        rec = loaded.records[0]
        assert rec.signature == 'GMST'
        assert rec.form_id.value == 0x00066C5B
        assert rec.editor_id == 'fJumpHeightMin'

        data = rec.get_subrecord('DATA')
        value = struct.unpack('<f', data.data)[0]
        assert value == pytest.approx(500.0)


    def test_multiple_record_types(self, tmp_path):
        """Records of different types get separate groups."""
        plugin = Plugin()
        plugin.header.version = 1.71

        gmst = Record('GMST', FormID(0x100), 0)
        gmst.version = 44
        gmst.add_subrecord('EDID', b'fTest\x00')
        gmst.add_subrecord('DATA', struct.pack('<f', 1.0))
        plugin.add_record(gmst)

        glob = Record('GLOB', FormID(0x200), 0)
        glob.version = 44
        glob.add_subrecord('EDID', b'TestGlobal\x00')
        glob.add_subrecord('FNAM', bytes([ord('f')]))
        glob.add_subrecord('FLTV', struct.pack('<f', 0.0))
        plugin.add_record(glob)

        path = tmp_path / 'multi_type.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 2
        assert len(loaded.groups) == 2
        assert loaded.get_record_by_editor_id('fTest') is not None
        assert loaded.get_record_by_editor_id('TestGlobal') is not None


# ---------------------------------------------------------------------------
# Record Creation with Schema
# ---------------------------------------------------------------------------

class TestPluginWeaponCreation:
    """Create a weapon plugin, save, reload, verify via schema."""


    def _make_weapon_plugin(self):
        """Build a plugin with a single test weapon."""
        plugin = Plugin()
        plugin.header.is_esm = False
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        weap = Record('WEAP', FormID(0x01000800), 0)
        weap.version = 44
        weap.add_subrecord('EDID', b'esplib_TestSword\x00')
        weap.add_subrecord('OBND', struct.pack('<6h', -10, -1, -10, 10, 30, 10))
        name = b'Esplib Test Sword'
        weap.add_subrecord('FULL', struct.pack('<H', len(name)) + name)
        desc = b'A test weapon created by esplib.'
        weap.add_subrecord('DESC', struct.pack('<H', len(desc)) + desc)

        # DATA: value=100, weight=5.0, damage=50
        weap.add_subrecord('DATA',
                           struct.pack('<I', 100) +
                           struct.pack('<f', 5.0) +
                           struct.pack('<H', 50))

        # DNAM: 100 bytes for SSE
        dnam = bytearray(100)
        struct.pack_into('<B', dnam, 0, 1)     # animation_type = OneHandSword
        struct.pack_into('<f', dnam, 4, 1.0)   # speed
        struct.pack_into('<f', dnam, 8, 0.7)   # reach
        weap.add_subrecord('DNAM', bytes(dnam))

        # CRDT: 24 bytes
        crdt = bytearray(24)
        struct.pack_into('<H', crdt, 0, 10)    # crit damage
        struct.pack_into('<f', crdt, 4, 1.0)   # crit % mult
        weap.add_subrecord('CRDT', bytes(crdt))

        # VNAM: detection sound level
        weap.add_subrecord('VNAM', struct.pack('<I', 1))

        plugin.add_record(weap)
        return plugin


    def test_weapon_save_reload(self, tmp_path):
        """Weapon record survives save/reload with correct fields via schema."""
        plugin = self._make_weapon_plugin()
        path = tmp_path / 'weapon_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 1

        rec = loaded.records[0]
        assert rec.signature == 'WEAP'
        assert rec.editor_id == 'esplib_TestSword'

        result = tes5.WEAP.from_record(rec)
        assert result['Editor ID'] == 'esplib_TestSword'
        assert result['Name'] == 'Esplib Test Sword'
        assert result['Game Data']['value'] == 100
        assert result['Game Data']['weight'] == pytest.approx(5.0)
        assert result['Game Data']['damage'] == 50
        assert result['Weapon Data']['speed'] == pytest.approx(1.0)
        assert result['Weapon Data']['reach'] == pytest.approx(0.7)


class TestPluginArmorCreation:
    """Create an armor plugin, save, reload, verify via schema."""


    def _make_armor_plugin(self):
        plugin = Plugin()
        plugin.header.is_esm = False
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        armo = Record('ARMO', FormID(0x01000800), 0)
        armo.version = 44
        armo.add_subrecord('EDID', b'esplib_TestArmor\x00')
        armo.add_subrecord('OBND', struct.pack('<6h', -15, -5, -15, 15, 30, 15))
        name = b'Esplib Test Armor'
        armo.add_subrecord('FULL', struct.pack('<H', len(name)) + name)
        armo.add_subrecord('BOD2', struct.pack('<II', 0x00000004, 1))
        armo.add_subrecord('RNAM', struct.pack('<I', 0x00013746))  # Nord race
        desc = b'Test armor created by esplib.'
        armo.add_subrecord('DESC', struct.pack('<H', len(desc)) + desc)
        armo.add_subrecord('DATA', struct.pack('<if', 200, 35.0))
        # Armor rating stored x100: 3000 = 30.0 in-game
        armo.add_subrecord('DNAM', struct.pack('<i', 3000))

        plugin.add_record(armo)
        return plugin


    def test_armor_save_reload(self, tmp_path):
        """Armor record survives save/reload with correct fields via schema."""
        plugin = self._make_armor_plugin()
        path = tmp_path / 'armor_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert rec.editor_id == 'esplib_TestArmor'

        result = tes5.ARMO.from_record(rec)
        assert result['Editor ID'] == 'esplib_TestArmor'
        assert result['Data']['value'] == 200
        assert result['Data']['weight'] == pytest.approx(35.0)
        assert result['Armor Rating'] == 3000

        # RNAM race FormID
        rnam = rec.get_subrecord('RNAM')
        fid = struct.unpack('<I', rnam.data)[0]
        assert fid == 0x00013746


class TestPluginPotionCreation:
    """Create a potion plugin, save, reload, verify via schema."""


    def _make_potion_plugin(self):
        plugin = Plugin()
        plugin.header.is_esm = False
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        alch = Record('ALCH', FormID(0x01000800), 0)
        alch.version = 44
        alch.add_subrecord('EDID', b'esplib_TestPotion\x00')
        alch.add_subrecord('OBND', struct.pack('<6h', -3, -3, -7, 3, 3, 7))
        name = b'Esplib Test Potion'
        alch.add_subrecord('FULL', struct.pack('<H', len(name)) + name)
        desc = b'A test potion from esplib.'
        alch.add_subrecord('DESC', struct.pack('<H', len(desc)) + desc)

        # DATA: weight=0.5
        alch.add_subrecord('DATA', struct.pack('<f', 0.5))

        # ENIT: value=50, flags=0, no addiction, no sound
        enit = struct.pack('<i', 50)       # value
        enit += struct.pack('<I', 0)       # flags
        enit += struct.pack('<I', 0)       # addiction
        enit += struct.pack('<f', 0.0)     # addiction chance
        enit += struct.pack('<I', 0)       # sound consume
        alch.add_subrecord('ENIT', enit)

        # Effect: Restore Health (0x0003EB15)
        alch.add_subrecord('EFID', struct.pack('<I', 0x0003EB15))
        # EFIT: magnitude=50, area=0, duration=0
        alch.add_subrecord('EFIT', struct.pack('<fII', 50.0, 0, 0))

        plugin.add_record(alch)
        return plugin


    def test_potion_save_reload(self, tmp_path):
        """Potion record survives save/reload with correct fields."""
        plugin = self._make_potion_plugin()
        path = tmp_path / 'potion_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert rec.editor_id == 'esplib_TestPotion'

        result = tes5.ALCH.from_record(rec)
        assert result['Weight'] == pytest.approx(0.5)

        efid = rec.get_subrecord('EFID')
        assert efid is not None
        effect_id = struct.unpack('<I', efid.data)[0]
        assert effect_id == 0x0003EB15

        efit = rec.get_subrecord('EFIT')
        assert efit is not None
        magnitude, area, duration = struct.unpack('<fII', efit.data)
        assert magnitude == pytest.approx(50.0)
        assert area == 0
        assert duration == 0


# ---------------------------------------------------------------------------
# Gamefiles Validation
# ---------------------------------------------------------------------------

class TestSkyrimStats:
    """Validate structural properties of Skyrim.esm."""


    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_has_many_records(self, skyrim):
        """Skyrim.esm has tens of thousands of records."""
        assert len(skyrim.records) > 50000


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_has_multiple_groups(self, skyrim):
        """Skyrim.esm has many top-level groups."""
        assert len(skyrim.groups) > 20


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_is_localized(self, skyrim):
        """Skyrim.esm is a localized plugin."""
        assert skyrim.is_localized


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_is_esm(self, skyrim):
        """Skyrim.esm has ESM flag set."""
        assert skyrim.is_esm


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_has_compressed_records(self, skyrim):
        """Skyrim.esm contains compressed records (e.g. NAVM)."""
        compressed = [r for r in skyrim.records if r.is_compressed]
        assert len(compressed) > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_statistics_returns_expected_keys(self, skyrim):
        """get_statistics() returns all expected fields."""
        stats = skyrim.get_statistics()
        assert 'total_records' in stats
        assert 'record_types' in stats
        assert 'masters' in stats
        assert 'version' in stats
        assert stats['is_localized'] is True


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_common_record_types_present(self, skyrim):
        """Skyrim.esm contains expected record types."""
        stats = skyrim.get_statistics()
        types = stats['record_types']
        for sig in ['WEAP', 'ARMO', 'NPC_', 'GMST', 'KYWD', 'ALCH']:
            assert sig in types, f"{sig} not found in Skyrim.esm"
            assert types[sig] > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_header_version(self, skyrim):
        """Skyrim SE version is 1.71."""
        assert skyrim.header.version == pytest.approx(1.71, abs=0.01)


class TestSkyrimFieldValues:
    """Validate specific field values from Skyrim.esm records."""


    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_sword_fields(self, skyrim):
        """IronSword should have known vanilla values."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            assert False, "IronSword not found in Skyrim.esm"

        result = tes5.WEAP.from_record(weapon)
        data = result['Game Data']
        assert data['damage'] == 7
        assert data['value'] == 25
        assert data['weight'] == pytest.approx(9.0)


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_armor_fields(self, skyrim):
        """ArmorIronCuirass should have known vanilla values."""
        armor = skyrim.get_record_by_editor_id('ArmorIronCuirass')
        if not armor:
            assert False, "ArmorIronCuirass not found in Skyrim.esm"

        result = tes5.ARMO.from_record(armor)
        assert result['Data']['value'] == 125
        assert result['Data']['weight'] == pytest.approx(30.0)


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_all_weap_resolve(self, skyrim):
        """All WEAP records in Skyrim.esm resolve without errors."""
        weapons = skyrim.get_records_by_signature('WEAP')
        assert len(weapons) > 0

        errors = []
        for w in weapons:
            try:
                tes5.WEAP.from_record(w)
            except Exception as e:
                errors.append(f"{w.editor_id or w.form_id}: {e}")

        assert len(errors) == 0, f"{len(errors)} errors:\n" + "\n".join(errors[:10])


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_all_armo_resolve(self, skyrim):
        """All ARMO records in Skyrim.esm resolve without errors."""
        armors = skyrim.get_records_by_signature('ARMO')
        assert len(armors) > 0

        errors = []
        for a in armors:
            try:
                tes5.ARMO.from_record(a)
            except Exception as e:
                errors.append(f"{a.editor_id or a.form_id}: {e}")

        assert len(errors) == 0, f"{len(errors)} errors:\n" + "\n".join(errors[:10])
