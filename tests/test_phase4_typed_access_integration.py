"""Phase 4 converted tests: typed access integration with save/reload.

In-memory typed access tests are in test_access.py. These tests cover
the full workflow: create plugin with typed access, save, reload, verify
fields via typed access on the reloaded plugin.
"""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5

from tests.conftest import find_skyrim_esm


# ---------------------------------------------------------------------------
# Typed access with save/reload
# ---------------------------------------------------------------------------

class TestTypedAccessSaveReload:
    """Create records using typed access, save, reload, verify."""

    def test_write_weapon_data_via_typed_access(self, tmp_path):
        """record['DATA'] = dict should produce correct bytes on disk."""
        plugin = Plugin()
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        weap = Record('WEAP', FormID(0x00012EB7), 0)
        weap.version = 44
        weap.schema = tes5.WEAP
        weap.add_subrecord('EDID', b'IronSword\x00')
        weap['DATA'] = {'value': 9999, 'weight': 5.0, 'damage': 100}

        plugin.add_record(weap)

        path = tmp_path / 'typed_weapon.esp'
        plugin.save(path)

        loaded = Plugin(path)
        loaded.set_game('tes5')
        rec = loaded.get_record_by_editor_id('IronSword')
        assert rec is not None

        data = rec['DATA']
        assert data['value'] == 9999
        assert data['weight'] == pytest.approx(5.0)
        assert data['damage'] == 100

    def test_auto_detect_game_on_reload(self, tmp_path):
        """Loading a v1.71 plugin auto-detects tes5 and binds schemas."""
        plugin = Plugin()
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        weap = Record('WEAP', FormID(0x800), 0)
        weap.version = 44
        weap.add_subrecord('EDID', b'TestSword\x00')
        weap.add_subrecord('DATA',
                           struct.pack('<I', 50) +
                           struct.pack('<f', 3.0) +
                           struct.pack('<H', 20))
        plugin.add_record(weap)

        path = tmp_path / 'set_game_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        # auto_detect_game() is called during load, so schema is bound
        assert rec.schema is not None
        assert rec.schema.signature == 'WEAP'

        data = rec['DATA']
        assert data['value'] == 50
        assert data['damage'] == 20

    def test_modify_and_save_preserves_edid(self, tmp_path):
        """Modifying a field via typed access shouldn't affect EDID."""
        plugin = Plugin()
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        weap = Record('WEAP', FormID(0x800), 0)
        weap.version = 44
        weap.schema = tes5.WEAP
        weap.add_subrecord('EDID', b'MyWeapon\x00')
        weap.add_subrecord('DATA',
                           struct.pack('<I', 10) +
                           struct.pack('<f', 1.0) +
                           struct.pack('<H', 5))
        plugin.add_record(weap)

        # Modify damage
        data = weap['DATA']
        data['damage'] = 99
        weap['DATA'] = data

        path = tmp_path / 'modify_edid.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        assert rec.editor_id == 'MyWeapon'

    def test_write_edid_via_typed_access(self, tmp_path):
        """record['EDID'] = string should round-trip through save/reload."""
        plugin = Plugin()
        plugin.header.version = 1.71

        weap = Record('WEAP', FormID(0x800), 0)
        weap.version = 44
        weap.schema = tes5.WEAP
        weap['EDID'] = 'NewWeaponName'
        plugin.add_record(weap)

        path = tmp_path / 'edid_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.records[0].editor_id == 'NewWeaponName'


class TestMultipleRecordTypedAccess:
    """Test typed access across multiple records in one plugin."""

    def test_two_weapons_independent_data(self, tmp_path):
        """Two weapons in one plugin, each with different typed data."""
        plugin = Plugin()
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        sword = Record('WEAP', FormID(0x00012EB7), 0)
        sword.version = 44
        sword.schema = tes5.WEAP
        sword.add_subrecord('EDID', b'TestSword\x00')
        sword['DATA'] = {'value': 100, 'weight': 5.0, 'damage': 50}
        plugin.add_record(sword)

        axe = Record('WEAP', FormID(0x000139A3), 0)
        axe.version = 44
        axe.schema = tes5.WEAP
        axe.add_subrecord('EDID', b'TestAxe\x00')
        axe['DATA'] = {'value': 200, 'weight': 8.0, 'damage': 75}
        plugin.add_record(axe)

        path = tmp_path / 'two_weapons.esp'
        plugin.save(path)

        loaded = Plugin(path)
        loaded.set_game('tes5')

        s = loaded.get_record_by_editor_id('TestSword')
        a = loaded.get_record_by_editor_id('TestAxe')

        assert s['DATA']['damage'] == 50
        assert s['DATA']['value'] == 100
        assert a['DATA']['damage'] == 75
        assert a['DATA']['value'] == 200

    def test_weapon_with_template_cnam(self, tmp_path):
        """CNAM (template FormID) should round-trip via typed access."""
        plugin = Plugin()
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        axe = Record('WEAP', FormID(0x000139A3), 0)
        axe.version = 44
        axe.schema = tes5.WEAP
        axe.add_subrecord('EDID', b'TemplatedAxe\x00')
        axe['DATA'] = {'value': 5555, 'weight': 8.0, 'damage': 75}
        axe.add_subrecord('CNAM', struct.pack('<I', 0x00013983))
        plugin.add_record(axe)

        path = tmp_path / 'template_test.esp'
        plugin.save(path)

        loaded = Plugin(path)
        loaded.set_game('tes5')
        rec = loaded.get_record_by_editor_id('TemplatedAxe')

        cnam = rec['CNAM']
        assert cnam is not None
        assert cnam.value == 0x00013983


# ---------------------------------------------------------------------------
# Real game file typed access
# ---------------------------------------------------------------------------

class TestSkyrimTypedAccess:
    """Test typed access against real Skyrim.esm with set_game()."""

    @pytest.fixture(scope='class')
    def skyrim(self):
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")
        plugin = Plugin(esm_path)
        plugin.set_game('tes5')
        return plugin

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_sword_typed_access(self, skyrim):
        """IronSword fields readable via typed access."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            pytest.skip("IronSword not found")

        data = weapon['DATA']
        assert isinstance(data, dict)
        assert data['damage'] == 7
        assert data['value'] == 25
        assert data['weight'] == pytest.approx(9.0)

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_iron_sword_dnam(self, skyrim):
        """IronSword DNAM fields accessible via typed access."""
        weapon = skyrim.get_record_by_editor_id('IronSword')
        if not weapon:
            pytest.skip("IronSword not found")

        dnam = weapon['DNAM']
        if dnam is None:
            pytest.skip("DNAM not present")

        assert 'speed' in dnam
        assert 'reach' in dnam
        assert dnam['speed'] > 0
        assert dnam['reach'] > 0

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_npc_acbs_typed_access(self, skyrim):
        """NPC_ ACBS config accessible via typed access."""
        npcs = skyrim.get_records_by_signature('NPC_')
        for npc in npcs[:100]:
            if npc.get_subrecord('ACBS') and npc.editor_id:
                acbs = npc['ACBS']
                if acbs:
                    assert 'level' in acbs
                    assert 'flags' in acbs
                    return
        pytest.skip("No NPC with ACBS found in first 100")

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_enchanted_weapon_with_template(self, skyrim):
        """Enchanted weapon should have CNAM template reference."""
        weapon = skyrim.get_record_by_editor_id('EnchSteelWarAxeStamina2')
        if not weapon:
            pytest.skip("EnchSteelWarAxeStamina2 not found")

        cnam = weapon['CNAM']
        assert cnam is not None
        # CNAM should be a FormID
        assert hasattr(cnam, 'value')
        assert cnam.value > 0
