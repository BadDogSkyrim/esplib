"""Tests for Skyrim SE record definitions against real Skyrim.esm data."""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import EspContext, GameRegistry
from esplib.defs import tes5

from tests.conftest import find_skyrim_esm


# ---------------------------------------------------------------------------
# Synthetic record tests (no game files needed)
# ---------------------------------------------------------------------------

class TestGMST:
    def test_float_gmst(self):
        record = Record('GMST', FormID(0x100), 0)
        record.add_subrecord('EDID', b'fTestValue\x00')
        record.add_subrecord('DATA', struct.pack('<f', 3.14))

        result = tes5.GMST.from_record(record)
        assert result['Editor ID'] == 'fTestValue'
        assert result['Value'] == struct.pack('<f', 3.14)

    def test_int_gmst(self):
        record = Record('GMST', FormID(0x101), 0)
        record.add_subrecord('EDID', b'iTestValue\x00')
        record.add_subrecord('DATA', struct.pack('<i', 42))

        result = tes5.GMST.from_record(record)
        assert result['Editor ID'] == 'iTestValue'


class TestGLOB:
    def test_float_global(self):
        record = Record('GLOB', FormID(0x200), 0)
        record.add_subrecord('EDID', b'TestGlobal\x00')
        record.add_subrecord('FNAM', bytes([ord('f')]))
        record.add_subrecord('FLTV', struct.pack('<f', 1.0))

        result = tes5.GLOB.from_record(record)
        assert result['Editor ID'] == 'TestGlobal'
        assert result['Type'] == ord('f')
        assert result['Value'] == 1.0


class TestKYWD:
    def test_keyword(self):
        record = Record('KYWD', FormID(0x300), 0)
        record.add_subrecord('EDID', b'WeapTypeSword\x00')
        record.add_subrecord('CNAM', bytes([255, 0, 0, 255]))

        result = tes5.KYWD.from_record(record)
        assert result['Editor ID'] == 'WeapTypeSword'
        assert result['Color']['red'] == 255
        assert result['Color']['green'] == 0
        assert result['Color']['alpha'] == 255


class TestWEAP:
    def test_weapon_data(self):
        record = Record('WEAP', FormID(0x800), 0)
        record.add_subrecord('EDID', b'IronSword\x00')
        record.add_subrecord('FULL', struct.pack('<H', 10) + b'Iron Sword')
        record.add_subrecord('DATA',
                             struct.pack('<I', 25) +       # value
                             struct.pack('<f', 9.0) +      # weight
                             struct.pack('<H', 7))         # damage

        result = tes5.WEAP.from_record(record)
        assert result['Editor ID'] == 'IronSword'
        assert result['Name'] == 'Iron Sword'
        assert result['Game Data']['value'] == 25
        assert abs(result['Game Data']['weight'] - 9.0) < 0.001
        assert result['Game Data']['damage'] == 7


class TestARMO:
    def test_armor_data(self):
        record = Record('ARMO', FormID(0x900), 0)
        record.add_subrecord('EDID', b'IronArmor\x00')
        record.add_subrecord('DATA',
                             struct.pack('<i', 125) +      # value
                             struct.pack('<f', 30.0))      # weight
        record.add_subrecord('DNAM', struct.pack('<i', 25))  # armor rating

        result = tes5.ARMO.from_record(record)
        assert result['Editor ID'] == 'IronArmor'
        assert result['Data']['value'] == 125
        assert abs(result['Data']['weight'] - 30.0) < 0.001
        assert result['Armor Rating'] == 25


class TestALCH:
    def test_potion(self):
        record = Record('ALCH', FormID(0xA00), 0)
        record.add_subrecord('EDID', b'PotionOfHealth\x00')
        record.add_subrecord('DATA', struct.pack('<f', 0.5))  # weight

        result = tes5.ALCH.from_record(record)
        assert result['Editor ID'] == 'PotionOfHealth'
        assert abs(result['Weight'] - 0.5) < 0.001


class TestLVLI:
    def test_leveled_item(self):
        record = Record('LVLI', FormID(0xB00), 0)
        record.add_subrecord('EDID', b'LItemWeapon\x00')
        record.add_subrecord('LVLD', bytes([10]))  # 10% chance none
        record.add_subrecord('LVLF', bytes([0x01]))  # calc all levels
        record.add_subrecord('LLCT', bytes([2]))  # 2 entries
        record.add_subrecord('LVLO',
                             struct.pack('<H', 1) +        # level
                             struct.pack('<H', 0) +        # padding
                             struct.pack('<I', 0x12EB7) +  # formid
                             struct.pack('<H', 1) +        # count
                             struct.pack('<H', 0))         # padding

        result = tes5.LVLI.from_record(record)
        assert result['Editor ID'] == 'LItemWeapon'
        assert result['Chance None'] == 10
        assert result['Flags'] == 1
        assert result['Entry Count'] == 2
        entry = result['Leveled List Entry']
        assert entry['level'] == 1
        assert entry['reference'].value == 0x12EB7


class TestCOBJ:
    def test_recipe(self):
        record = Record('COBJ', FormID(0xC00), 0)
        record.add_subrecord('EDID', b'RecipeIronSword\x00')
        record.add_subrecord('COCT', struct.pack('<I', 2))
        record.add_subrecord('CNTO',
                             struct.pack('<I', 0x5ACE4) +  # iron ingot
                             struct.pack('<i', 1))
        record.add_subrecord('CNTO',
                             struct.pack('<I', 0x5ACE5) +  # leather strips
                             struct.pack('<i', 2))
        record.add_subrecord('CNAM', struct.pack('<I', 0x12EB7))  # iron sword
        record.add_subrecord('BNAM', struct.pack('<I', 0x88105))  # forge keyword
        record.add_subrecord('NAM1', struct.pack('<H', 1))

        result = tes5.COBJ.from_record(record)
        assert result['Editor ID'] == 'RecipeIronSword'
        assert result['Ingredient Count'] == 2
        # Multiple CNTO subrecords should produce a list
        ingredients = result['Ingredient']
        assert isinstance(ingredients, list)
        assert len(ingredients) == 2
        assert ingredients[0]['count'] == 1
        assert ingredients[1]['count'] == 2
        assert result['Created Object'].value == 0x12EB7
        assert result['Created Object Count'] == 1


class TestFACT:
    def test_faction(self):
        record = Record('FACT', FormID(0xD00), 0)
        record.add_subrecord('EDID', b'CompanionsFaction\x00')
        record.add_subrecord('FULL', struct.pack('<H', 10) + b'Companions')
        record.add_subrecord('DATA', struct.pack('<I', 0x4000))  # Vendor flag

        result = tes5.FACT.from_record(record)
        assert result['Editor ID'] == 'CompanionsFaction'
        assert result['Name'] == 'Companions'
        assert result['Flags'] == 0x4000


class TestNPC:
    def test_npc_acbs(self):
        record = Record('NPC_', FormID(0xE00), 0)
        record.add_subrecord('EDID', b'TestNPC\x00')

        # ACBS: 24 bytes
        acbs = struct.pack('<I', 0x30)   # flags: auto-calc + unique
        acbs += struct.pack('<h', 0)     # magicka offset
        acbs += struct.pack('<h', 0)     # stamina offset
        acbs += struct.pack('<H', 25)    # level
        acbs += struct.pack('<H', 1)     # calc min
        acbs += struct.pack('<H', 100)   # calc max
        acbs += struct.pack('<H', 100)   # speed mult
        acbs += struct.pack('<h', 0)     # disposition
        acbs += struct.pack('<H', 0)     # template flags
        acbs += struct.pack('<h', 0)     # health offset
        acbs += struct.pack('<H', 0)     # bleedout
        record.add_subrecord('ACBS', acbs)

        record.add_subrecord('RNAM', struct.pack('<I', 0x13746))  # Nord race

        result = tes5.NPC_.from_record(record)
        assert result['Editor ID'] == 'TestNPC'
        assert result['Configuration']['level'] == 25
        assert result['Configuration']['calc_max_level'] == 100
        assert result['Race'].value == 0x13746


class TestGameRegistry:
    def test_tes5_registered(self):
        registry = GameRegistry.get_game('tes5')
        assert registry is not None
        assert registry.name == 'Skyrim Special Edition'

    def test_tes5_has_weap(self):
        registry = GameRegistry.get_game('tes5')
        weap = registry.get('WEAP')
        assert weap is not None
        assert weap.name == 'Weapon'

    def test_detect_skyrim(self):
        registry = GameRegistry.detect_game(1.71)
        assert registry is not None
        assert registry.game_id == 'tes5'

    def test_all_tier0_registered(self):
        registry = GameRegistry.get_game('tes5')
        for sig in ['GMST', 'GLOB', 'KYWD', 'FLST']:
            assert registry.get(sig) is not None, f"{sig} not registered"

    def test_all_tier1_registered(self):
        registry = GameRegistry.get_game('tes5')
        for sig in ['WEAP', 'ARMO', 'ALCH', 'AMMO', 'BOOK', 'MISC',
                     'LVLI', 'COBJ', 'FACT', 'NPC_']:
            assert registry.get(sig) is not None, f"{sig} not registered"


# ---------------------------------------------------------------------------
# Real game file tests (requires Skyrim.esm)
# ---------------------------------------------------------------------------

class TestSkyrimRecords:
    """Validate definitions against real Skyrim.esm records."""

    @pytest.fixture(scope='class')
    def skyrim(self):
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")
        return Plugin(esm_path)

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_iron_sword(self, skyrim):
        """Resolve the Iron Sword WEAP record."""
        iron_sword = skyrim.get_record_by_editor_id('IronSword')
        if not iron_sword:
            pytest.skip("IronSword not found (localized EDID?)")

        result = tes5.WEAP.from_record(iron_sword)
        assert 'Game Data' in result
        assert 'damage' in result['Game Data']
        assert isinstance(result['Game Data']['damage'], int)
        assert result['Game Data']['damage'] > 0

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_iron_armor(self, skyrim):
        """Resolve the Iron Armor ARMO record."""
        iron_armor = skyrim.get_record_by_editor_id('ArmorIronCuirass')
        if not iron_armor:
            pytest.skip("ArmorIronCuirass not found")

        result = tes5.ARMO.from_record(iron_armor)
        assert 'Data' in result
        assert 'value' in result['Data']
        assert result['Data']['value'] > 0

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_gmst(self, skyrim):
        """Resolve a GMST record."""
        gmsts = skyrim.get_records_by_signature('GMST')
        assert len(gmsts) > 0

        # Find a float GMST
        for gmst in gmsts[:50]:
            edid = gmst.editor_id
            if edid and edid.startswith('f'):
                result = tes5.GMST.from_record(gmst)
                assert 'Editor ID' in result
                assert 'Value' in result
                break

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_npc(self, skyrim):
        """Resolve an NPC_ record with ACBS."""
        npcs = skyrim.get_records_by_signature('NPC_')
        assert len(npcs) > 0

        # Find an NPC with ACBS
        for npc in npcs[:100]:
            if npc.get_subrecord('ACBS'):
                result = tes5.NPC_.from_record(npc)
                if 'Configuration' in result:
                    config = result['Configuration']
                    assert 'level' in config
                    assert 'flags' in config
                    break

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_lvli(self, skyrim):
        """Resolve a LVLI record."""
        lvlis = skyrim.get_records_by_signature('LVLI')
        assert len(lvlis) > 0

        for lvli in lvlis[:20]:
            result = tes5.LVLI.from_record(lvli)
            if 'Leveled List Entry' in result:
                break

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_weap_dnam_size_matches_schema(self, skyrim):
        """DNAM subrecord size should match our schema's expected size."""
        weapons = skyrim.get_records_by_signature('WEAP')
        for weapon in weapons[:50]:
            dnam = weapon.get_subrecord('DNAM')
            if dnam:
                # Our schema should consume all bytes without error
                result = tes5.WEAP.from_record(weapon)
                assert 'Weapon Data' in result
                wdata = result['Weapon Data']
                assert 'stagger' in wdata, "stagger field missing -- DNAM size mismatch"
                break

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_all_weap_resolve_without_crash(self, skyrim):
        """All WEAP records should resolve without exceptions."""
        weapons = skyrim.get_records_by_signature('WEAP')
        errors = []
        for weapon in weapons[:200]:  # Test first 200
            try:
                tes5.WEAP.from_record(weapon)
            except Exception as e:
                errors.append(f"{weapon.editor_id or weapon.form_id}: {e}")

        assert len(errors) == 0, f"Errors resolving weapons:\n" + "\n".join(errors[:10])

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_all_armo_resolve_without_crash(self, skyrim):
        """All ARMO records should resolve without exceptions."""
        armors = skyrim.get_records_by_signature('ARMO')
        errors = []
        for armor in armors[:200]:
            try:
                tes5.ARMO.from_record(armor)
            except Exception as e:
                errors.append(f"{armor.editor_id or armor.form_id}: {e}")

        assert len(errors) == 0, f"Errors resolving armors:\n" + "\n".join(errors[:10])
