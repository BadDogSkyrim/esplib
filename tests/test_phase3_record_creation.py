"""Phase 3 converted tests: creating records with schemas, save/reload, field validation.

Schema resolution of synthetic/real records is in test_defs_tes5.py.
These tests cover creating full record plugins from scratch, saving to disk,
reloading, and verifying fields via the schema system.
"""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5

from tests.conftest import find_skyrim_esm


# ---------------------------------------------------------------------------
# Weapon creation and validation
# ---------------------------------------------------------------------------

class TestWeaponCreation:
    """Create weapon plugins from scratch, save, reload, verify."""

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

    def test_weapon_save_reload_raw(self, tmp_path):
        """Weapon record survives save/reload with correct raw subrecords."""
        plugin = self._make_weapon_plugin()
        path = tmp_path / 'weapon_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 1

        rec = loaded.records[0]
        assert rec.signature == 'WEAP'
        assert rec.editor_id == 'esplib_TestSword'

        data_sr = rec.get_subrecord('DATA')
        assert data_sr is not None
        value, weight, damage = struct.unpack('<IfH', data_sr.data)
        assert value == 100
        assert weight == pytest.approx(5.0)
        assert damage == 50

    def test_weapon_save_reload_schema(self, tmp_path):
        """Weapon fields resolve correctly through schema after save/reload."""
        plugin = self._make_weapon_plugin()
        path = tmp_path / 'weapon_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        result = tes5.WEAP.from_record(rec)

        assert result['Editor ID'] == 'esplib_TestSword'
        assert result['Name'] == 'Esplib Test Sword'
        assert result['Game Data']['value'] == 100
        assert result['Game Data']['weight'] == pytest.approx(5.0)
        assert result['Game Data']['damage'] == 50

    def test_weapon_dnam_fields(self, tmp_path):
        """DNAM weapon-specific fields survive save/reload."""
        plugin = self._make_weapon_plugin()
        path = tmp_path / 'weapon_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        result = tes5.WEAP.from_record(rec)

        wdata = result['Weapon Data']
        assert wdata['speed'] == pytest.approx(1.0)
        assert wdata['reach'] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Armor creation and validation
# ---------------------------------------------------------------------------

class TestArmorCreation:
    """Create armor plugins from scratch, save, reload, verify."""

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

    def test_armor_save_reload_raw(self, tmp_path):
        """Armor record survives save/reload with correct raw values."""
        plugin = self._make_armor_plugin()
        path = tmp_path / 'armor_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert rec.editor_id == 'esplib_TestArmor'

        data_sr = rec.get_subrecord('DATA')
        value, weight = struct.unpack('<if', data_sr.data)
        assert value == 200
        assert weight == pytest.approx(35.0)

        dnam_sr = rec.get_subrecord('DNAM')
        rating = struct.unpack('<i', dnam_sr.data)[0]
        assert rating == 3000

    def test_armor_save_reload_schema(self, tmp_path):
        """Armor fields resolve correctly through schema after save/reload."""
        plugin = self._make_armor_plugin()
        path = tmp_path / 'armor_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        result = tes5.ARMO.from_record(rec)

        assert result['Editor ID'] == 'esplib_TestArmor'
        assert result['Data']['value'] == 200
        assert result['Data']['weight'] == pytest.approx(35.0)
        assert result['Armor Rating'] == 3000

    def test_armor_race_reference(self, tmp_path):
        """RNAM race FormID reference survives save/reload."""
        plugin = self._make_armor_plugin()
        path = tmp_path / 'armor_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        rnam = rec.get_subrecord('RNAM')
        fid = struct.unpack('<I', rnam.data)[0]
        assert fid == 0x00013746


# ---------------------------------------------------------------------------
# Potion creation and validation
# ---------------------------------------------------------------------------

class TestPotionCreation:
    """Create potion plugins from scratch, save, reload, verify."""

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
        """Potion record survives save/reload."""
        plugin = self._make_potion_plugin()
        path = tmp_path / 'potion_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert rec.editor_id == 'esplib_TestPotion'

    def test_potion_weight(self, tmp_path):
        """Potion weight field round-trips correctly."""
        plugin = self._make_potion_plugin()
        path = tmp_path / 'potion_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        result = tes5.ALCH.from_record(rec)
        assert result['Weight'] == pytest.approx(0.5)

    def test_potion_effect_subrecords(self, tmp_path):
        """Effect subrecords (EFID, EFIT) survive save/reload."""
        plugin = self._make_potion_plugin()
        path = tmp_path / 'potion_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]

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
# Field validation against real Skyrim.esm
# ---------------------------------------------------------------------------

class TestSkyrimFieldValues:
    """Validate specific field values from Skyrim.esm records."""

    @pytest.fixture(scope='class')
    def skyrim(self):
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")
        return Plugin(esm_path)

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_sword_fields(self, skyrim):
        """IronSword should have known vanilla values."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            pytest.skip("IronSword not found")

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
            pytest.skip("ArmorIronCuirass not found")

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
