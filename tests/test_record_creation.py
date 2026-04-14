"""Record creation tests: synthetic plugin workflows and Skyrim.esm validation.

Covers creating plugins from scratch, adding records with schemas,
saving/reloading, and verifying field values against real game data.
"""

import pytest

from esplib import Plugin, Record, FormID
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
        plugin = Plugin.new_plugin(tmp_path / "with_masters.esp",
                                   masters=['Skyrim.esm', 'Update.esm'])
        plugin.save()

        loaded = Plugin(tmp_path / "with_masters.esp")
        assert loaded.header.masters == ['Skyrim.esm', 'Update.esm']


    def test_gmst_override_save_reload(self, tmp_path):
        """Create a GMST override, save, reload, verify field values."""
        plugin = Plugin.new_plugin(tmp_path / 'gmst_test.esp',
                                   masters=['Skyrim.esm'])

        gmst = Record('GMST', FormID(0x00066C5B))
        gmst.add_subrecord('EDID', 'fJumpHeightMin')
        plugin.add_record(gmst)
        gmst['DATA'] = 500.0

        plugin.save()

        loaded = Plugin(tmp_path / 'gmst_test.esp')
        assert loaded.header.masters == ['Skyrim.esm']
        assert len(loaded.records) == 1

        rec = loaded.records[0]
        assert rec.signature == 'GMST'
        assert rec.form_id.value == 0x00066C5B
        assert rec.editor_id == 'fJumpHeightMin'
        assert rec['DATA'] == pytest.approx(500.0)


    def test_multiple_record_types(self, tmp_path):
        """Records of different types get separate groups."""
        plugin = Plugin.new_plugin(tmp_path / 'multi_type.esp')

        gmst = Record('GMST', FormID(0x100))
        gmst.add_subrecord('EDID', 'fTest')
        plugin.add_record(gmst)
        gmst['DATA'] = 1.0

        glob = Record('GLOB', FormID(0x200))
        glob.add_subrecord('EDID', 'TestGlobal')
        plugin.add_record(glob)
        glob['FNAM'] = ord('f')
        glob['FLTV'] = 76.0

        plugin.save()

        loaded = Plugin(tmp_path / 'multi_type.esp')
        assert len(loaded.records) == 2
        assert len(loaded.groups) == 2

        gmst_loaded = loaded.get_record_by_editor_id('fTest')
        assert gmst_loaded is not None
        assert gmst_loaded['DATA'] == pytest.approx(1.0)

        glob_loaded = loaded.get_record_by_editor_id('TestGlobal')
        assert glob_loaded is not None
        assert glob_loaded['FLTV'] == pytest.approx(76.0)


# ---------------------------------------------------------------------------
# Record Creation with Schema
# ---------------------------------------------------------------------------

class TestPluginWeaponCreation:
    """Create a weapon plugin, save, reload, verify via schema."""


    def _make_weapon_plugin(self, tmp_path):
        """Build a plugin with a single test weapon."""
        plugin = Plugin.new_plugin(tmp_path / 'weapon_test.esp',
                                   masters=['Skyrim.esm'])

        weap = Record('WEAP', FormID(0x01000800))
        weap.add_subrecord('EDID', 'esplib_TestSword')
        plugin.add_record(weap)

        weap['OBND'] = {'x1': -10, 'y1': -1, 'z1': -10,
                         'x2': 10, 'y2': 30, 'z2': 10}
        weap['FULL'] = 'Esplib Test Sword'
        weap['DESC'] = 'A test weapon created by esplib.'
        weap['DATA'] = {'value': 100, 'weight': 5.0, 'damage': 50}
        weap['DNAM'] = {
            'animation_type': 1,  # OneHandSword
            'speed': 1.0,
            'reach': 0.7,
        }
        weap['CRDT'] = {'crit_damage': 10, 'crit_pct_mult': 1.0}
        weap['VNAM'] = 1  # Normal

        return plugin


    def test_weapon_save_reload(self, tmp_path):
        """Weapon record survives save/reload with correct fields via schema."""
        plugin = self._make_weapon_plugin(tmp_path)
        plugin.save()

        loaded = Plugin(tmp_path / 'weapon_test.esp')
        assert len(loaded.records) == 1

        rec = loaded.records[0]
        assert rec.signature == 'WEAP'
        assert rec.editor_id == 'esplib_TestSword'
        assert rec['FULL'] == 'Esplib Test Sword'
        assert rec['DATA']['value'] == 100
        assert rec['DATA']['weight'] == pytest.approx(5.0)
        assert rec['DATA']['damage'] == 50
        assert rec['DNAM']['speed'] == pytest.approx(1.0)
        assert rec['DNAM']['reach'] == pytest.approx(0.7)


class TestPluginArmorCreation:
    """Create an armor plugin, save, reload, verify via schema."""


    def _make_armor_plugin(self, tmp_path):
        plugin = Plugin.new_plugin(tmp_path / 'armor_test.esp',
                                   masters=['Skyrim.esm'])

        armo = Record('ARMO', FormID(0x01000800))
        armo.add_subrecord('EDID', 'esplib_TestArmor')
        plugin.add_record(armo)

        armo['OBND'] = {'x1': -15, 'y1': -5, 'z1': -15,
                         'x2': 15, 'y2': 30, 'z2': 15}
        armo['FULL'] = 'Esplib Test Armor'
        armo['BOD2'] = {'first_person_flags': 0x00000004, 'armor_type': 1}
        armo['RNAM'] = FormID(0x00013746)  # NordRace
        armo['DESC'] = 'Test armor created by esplib.'
        armo['DATA'] = {'value': 200, 'weight': 35.0}
        # Armor rating stored x100: 3000 = 30.0 in-game
        armo['DNAM'] = 3000

        return plugin


    def test_armor_save_reload(self, tmp_path):
        """Armor record survives save/reload with correct fields via schema."""
        plugin = self._make_armor_plugin(tmp_path)
        plugin.save()

        loaded = Plugin(tmp_path / 'armor_test.esp')
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert rec.editor_id == 'esplib_TestArmor'
        assert rec['DATA']['value'] == 200
        assert rec['DATA']['weight'] == pytest.approx(35.0)
        assert rec['DNAM'] == 3000
        assert rec['RNAM'] == FormID(0x00013746)


class TestPluginPotionCreation:
    """Create a potion plugin, save, reload, verify via schema."""


    def _make_potion_plugin(self, tmp_path):
        plugin = Plugin.new_plugin(tmp_path / 'potion_test.esp',
                                   masters=['Skyrim.esm'])

        alch = Record('ALCH', FormID(0x01000800))
        alch.add_subrecord('EDID', 'esplib_TestPotion')
        plugin.add_record(alch)

        alch['OBND'] = {'x1': -3, 'y1': -3, 'z1': -7,
                         'x2': 3, 'y2': 3, 'z2': 7}
        alch['FULL'] = 'Esplib Test Potion'
        alch['DESC'] = 'A test potion from esplib.'
        alch['DATA'] = 0.5  # weight
        alch['ENIT'] = {'value': 50, 'flags': 0, 'addiction': 0,
                         'addiction_chance': 0.0, 'sound_consume': 0}
        alch['EFID'] = FormID(0x0003EB15)  # Restore Health
        alch['EFIT'] = {'magnitude': 50.0, 'area': 0, 'duration': 0}

        return plugin


    def test_potion_save_reload(self, tmp_path):
        """Potion record survives save/reload with correct fields."""
        plugin = self._make_potion_plugin(tmp_path)
        plugin.save()

        loaded = Plugin(tmp_path / 'potion_test.esp')
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert rec.editor_id == 'esplib_TestPotion'
        assert rec['FULL'] == 'Esplib Test Potion'
        assert rec['DATA'] == pytest.approx(0.5)
        assert rec['EFID'] == FormID(0x0003EB15)
        assert rec['EFIT']['magnitude'] == pytest.approx(50.0)
        assert rec['EFIT']['area'] == 0
        assert rec['EFIT']['duration'] == 0


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
        assert weapon is not None, "IronSword not found in Skyrim.esm"

        assert weapon['DATA']['damage'] == 7
        assert weapon['DATA']['value'] == 25
        assert weapon['DATA']['weight'] == pytest.approx(9.0)


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_armor_fields(self, skyrim):
        """ArmorIronCuirass should have known vanilla values."""
        armor = skyrim.get_record_by_editor_id('ArmorIronCuirass')
        assert armor is not None, "ArmorIronCuirass not found in Skyrim.esm"

        assert armor['DATA']['value'] == 125
        assert armor['DATA']['weight'] == pytest.approx(30.0)


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_all_weap_resolve(self, skyrim):
        """All WEAP records in Skyrim.esm resolve without errors."""
        weapons = list(skyrim.get_records_by_signature('WEAP'))
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
        armors = list(skyrim.get_records_by_signature('ARMO'))
        assert len(armors) > 0

        errors = []
        for a in armors:
            try:
                tes5.ARMO.from_record(a)
            except Exception as e:
                errors.append(f"{a.editor_id or a.form_id}: {e}")

        assert len(errors) == 0, f"{len(errors)} errors:\n" + "\n".join(errors[:10])
