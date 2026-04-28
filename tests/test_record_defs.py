"""Tests for Skyrim SE record definitions — synthetic and real game file."""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import EspContext, GameRegistry
from esplib.defs import tes5

from tests.conftest import find_skyrim_esm


# ---------------------------------------------------------------------------
# Synthetic record tests (no game files needed)
# ---------------------------------------------------------------------------


class TestStructGLOB:


    def test_float_global(self):
        record = Record('GLOB', FormID(0x200), 0)
        record.add_subrecord('EDID', b'TestGlobal\x00')
        record.add_subrecord('FNAM', bytes([ord('f')]))
        record.add_subrecord('FLTV', struct.pack('<f', 1.0))

        result = tes5.GLOB.from_record(record)
        assert result['Editor ID'] == 'TestGlobal'
        assert result['Type'] == 'Float'
        assert result['Value'] == 1.0


class TestStructKYWD:


    def test_keyword(self):
        record = Record('KYWD', FormID(0x300), 0)
        record.add_subrecord('EDID', b'WeapTypeSword\x00')
        record.add_subrecord('CNAM', bytes([255, 0, 0, 255]))

        result = tes5.KYWD.from_record(record)
        assert result['Editor ID'] == 'WeapTypeSword'
        assert result['Color']['red'] == 255
        assert result['Color']['green'] == 0
        assert result['Color']['alpha'] == 255


class TestStructCOBJ:


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


class TestStructNPCTintLayers:


    def test_npc_tint_layers(self):
        record = Record('NPC_', FormID(0xB01), 0)
        record.add_subrecord('EDID', b'TestNPC\x00')
        record.add_subrecord('TINI', struct.pack('<H', 5))
        record.add_subrecord('TINC', bytes([255, 128, 0, 200]))
        record.add_subrecord('TINV', struct.pack('<i', 75))
        record.add_subrecord('TIAS', struct.pack('<h', -1))

        result = tes5.NPC_.from_record(record)
        assert result['Tint Index'] == 5
        assert result['Tint Color']['red'] == 255
        assert result['Tint Color']['green'] == 128
        assert result['Tint Interpolation Value'] == 75
        assert result['Tint Preset'] == -1


class TestStructGameRegistry:


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


    def test_phase_a_types_registered(self):
        registry = GameRegistry.get_game('tes5')
        for sig in ['HDPT', 'ARMA', 'RACE']:
            assert registry.get(sig) is not None, f"{sig} not registered"


    def test_txst_registered(self):
        """TXST (texture set) carries the eight TX00..TX07 texture
        path slots that mods reference everywhere; surfaced as the
        single biggest unscanned record type in find_missing_assets,
        added 2026-04-24."""
        registry = GameRegistry.get_game('tes5')
        txst = registry.get('TXST')
        assert txst is not None, "TXST not registered"
        # Each TX0n slot is present and exposes a zstring value
        # named 'texture' so consumers can detect path subrecords by
        # the value_def name without per-slot special cases.
        sigs = {m.signature for m in txst.members
                if hasattr(m, 'signature')}
        for slot in ('TX00', 'TX01', 'TX02', 'TX03',
                     'TX04', 'TX05', 'TX06', 'TX07'):
            assert slot in sigs, f"TXST missing slot {slot}"


    def test_dial_registered(self):
        """DIAL (dialog topic) — needed for dialog-dump tooling so
        each INFO's parent topic + quest can be reported alongside
        the response text."""
        registry = GameRegistry.get_game('tes5')
        dial = registry.get('DIAL')
        assert dial is not None, "DIAL not registered"
        sigs = {m.signature for m in dial.members
                if hasattr(m, 'signature')}
        for sig in ('EDID', 'FULL', 'PNAM', 'QNAM', 'DATA',
                    'SNAM', 'TIFC'):
            assert sig in sigs, f"DIAL missing {sig}"


    def test_info_registered(self):
        """INFO (dialog response) — the actual lines of dialog. NAM1
        carries the response text; SNAM the voice-file FormID. Both
        are inside a repeating Response group (one per response
        variant on the INFO)."""
        registry = GameRegistry.get_game('tes5')
        info = registry.get('INFO')
        assert info is not None, "INFO not registered"
        # Top-level subrecords + at least one Response group with
        # NAM1 and SNAM.
        flat_sigs = set()
        def _collect(members):
            for m in members:
                if hasattr(m, 'members'):
                    _collect(m.members)
                elif hasattr(m, 'signature'):
                    flat_sigs.add(m.signature)
        _collect(info.members)
        for sig in ('ENAM', 'CNAM', 'TRDT', 'NAM1', 'NAM2', 'SNAM'):
            assert sig in flat_sigs, f"INFO missing {sig}"


# ---------------------------------------------------------------------------
# Real game file tests (requires Skyrim.esm)
# ---------------------------------------------------------------------------


class TestSkyrimRecords:
    """Validate definitions against real Skyrim.esm records."""


    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_iron_sword(self, skyrim):
        """Resolve the Iron Sword WEAP record."""
        iron_sword = skyrim.get_record_by_editor_id('IronSword')
        if not iron_sword:
            assert False, "IronSword not found in Skyrim.esm"

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
            assert False, "ArmorIronCuirass not found in Skyrim.esm"

        result = tes5.ARMO.from_record(iron_armor)
        assert 'Data' in result
        assert 'value' in result['Data']
        assert result['Data']['value'] > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_gmst(self, skyrim):
        """Resolve a GMST record."""
        gmsts = list(skyrim.get_records_by_signature('GMST'))
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
        npcs = list(skyrim.get_records_by_signature('NPC_'))
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
    def test_resolve_dial(self, skyrim):
        """Resolve a DIAL record by EDID and read parsed values.
        DA03BarbasGreeting1A is a known stable dialog topic in
        vanilla; QNAM points at its parent quest."""
        dial = skyrim.get_record_by_editor_id('DA03BarbasGreeting1A')
        if not dial:
            pytest.skip("DA03BarbasGreeting1A not in Skyrim.esm")
        dial.bind_schema(tes5.DIAL)
        # PNAM is a float (dialog priority).
        assert isinstance(dial['PNAM'], float)
        # QNAM is a quest FormID — should resolve to a real QUST.
        qnam = dial['QNAM']
        assert qnam is not None
        # TIFC is the count of INFOs under this DIAL; at least 1.
        tifc = dial['TIFC']
        assert isinstance(tifc, int) and tifc >= 1


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_info(self, skyrim):
        """Resolve an INFO record. INFOs rarely have an EDID, so
        find the first one whose first response has a NAM1 and
        verify the response group parses."""
        for info in skyrim.get_records_by_signature('INFO'):
            if info.get_subrecord('NAM1') is None:
                continue
            info.bind_schema(tes5.INFO)
            # NAM1 in a localized plugin (Skyrim.esm is localized) is
            # a uint32 string-table ID; we don't resolve the string
            # here — just confirm the field type round-trips.
            nam1 = info['NAM1']
            assert nam1 is not None
            return
        pytest.skip("No INFO with NAM1 found")


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_txst(self, skyrim):
        """Resolve a TXST record and read back its texture slot
        paths. Skyrim.esm has thousands of TXSTs; the first one
        with a non-empty TX00 is enough to confirm parsing works."""
        for txst in skyrim.get_records_by_signature('TXST'):
            tx00 = txst.get_subrecord('TX00')
            if tx00 is None:
                continue
            result = tes5.TXST.from_record(txst)
            # Slot subrecord descriptions are the dict keys.
            color_path = result.get('Color Map')
            assert isinstance(color_path, str), color_path
            assert color_path, "Color Map should be a non-empty path"
            assert color_path.lower().endswith('.dds'), color_path
            return
        pytest.skip("No TXST with TX00 found")


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_lvli(self, skyrim):
        """Resolve a LVLI record."""
        lvlis = list(skyrim.get_records_by_signature('LVLI'))
        assert len(lvlis) > 0

        for lvli in lvlis[:20]:
            result = tes5.LVLI.from_record(lvli)
            if 'Leveled List Entry' in result:
                break


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_weap_dnam_size_matches_schema(self, skyrim):
        """DNAM subrecord size should match our schema's expected size."""
        weapons = list(skyrim.get_records_by_signature('WEAP'))
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
        weapons = list(skyrim.get_records_by_signature('WEAP'))
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
        armors = list(skyrim.get_records_by_signature('ARMO'))
        errors = []
        for armor in armors[:200]:
            try:
                tes5.ARMO.from_record(armor)
            except Exception as e:
                errors.append(f"{armor.editor_id or armor.form_id}: {e}")

        assert len(errors) == 0, f"Errors resolving armors:\n" + "\n".join(errors[:10])


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_nord_race(self, skyrim):
        nord = skyrim.get_record_by_editor_id('NordRace')
        if not nord:
            assert False, "NordRace not found in Skyrim.esm"
        result = tes5.RACE.from_record(nord)
        assert 'Editor ID' in result
        assert result['Editor ID'] == 'NordRace'
        # Should have skin, armor race
        if 'Skin' in result:
            assert result['Skin'].value > 0
        if 'Armor Race' in result:
            assert result['Armor Race'].value > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_bulk_resolve_hdpt(self, skyrim):
        hdpts = list(skyrim.get_records_by_signature('HDPT'))
        assert len(hdpts) > 0
        errors = []
        for hp in hdpts[:200]:
            try:
                tes5.HDPT.from_record(hp)
            except Exception as e:
                errors.append(f"{hp.editor_id or hp.form_id}: {e}")
        assert len(errors) == 0, f"Errors:\n" + "\n".join(errors[:10])


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_bulk_resolve_arma(self, skyrim):
        armas = list(skyrim.get_records_by_signature('ARMA'))
        assert len(armas) > 0
        errors = []
        for arma in armas[:200]:
            try:
                tes5.ARMA.from_record(arma)
            except Exception as e:
                errors.append(f"{arma.editor_id or arma.form_id}: {e}")
        assert len(errors) == 0, f"Errors:\n" + "\n".join(errors[:10])


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_bulk_resolve_race(self, skyrim):
        races = list(skyrim.get_records_by_signature('RACE'))
        assert len(races) > 0
        errors = []
        for race in races:
            try:
                tes5.RACE.from_record(race)
            except Exception as e:
                errors.append(f"{race.editor_id or race.form_id}: {e}")
        assert len(errors) == 0, f"Errors:\n" + "\n".join(errors[:10])


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_npc_with_head_parts(self, skyrim):
        """Find an NPC with head parts and verify they resolve."""
        npcs = list(skyrim.get_records_by_signature('NPC_'))
        for npc in npcs[:100]:
            pnam = npc.get_subrecords('PNAM')
            if len(pnam) > 0:
                result = tes5.NPC_.from_record(npc)
                hp = result.get('Head Part')
                if hp:
                    if isinstance(hp, list):
                        assert len(hp) > 0
                    else:
                        assert hp.value > 0
                    break


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_npc_with_tint_layers(self, skyrim):
        """Find an NPC with tint layers."""
        npcs = list(skyrim.get_records_by_signature('NPC_'))
        for npc in npcs[:200]:
            tini = npc.get_subrecords('TINI')
            if len(tini) > 0:
                result = tes5.NPC_.from_record(npc)
                assert 'Tint Index' in result
                break
