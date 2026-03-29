"""Tests for Phase A: Additional Skyrim record definitions (RACE, HDPT, ARMA, NPC_ extensions)."""

import struct
import pytest

from esplib import Plugin, Record, SubRecord, FormID
from esplib.defs import tes5, GameRegistry

from tests.conftest import find_skyrim_esm


# ---------------------------------------------------------------------------
# Synthetic tests
# ---------------------------------------------------------------------------

class TestHDPT:
    def test_headpart_type(self):
        record = Record('HDPT', FormID(0x800), 0)
        record.add_subrecord('EDID', b'TestHair\x00')
        record.add_subrecord('PNAM', struct.pack('<I', 3))  # Hair

        result = tes5.HDPT.from_record(record)
        assert result['Editor ID'] == 'TestHair'
        assert result['Type'] == 3

    def test_headpart_flags(self):
        record = Record('HDPT', FormID(0x801), 0)
        record.add_subrecord('EDID', b'TestHP\x00')
        record.add_subrecord('DATA', bytes([0x03]))  # Playable + Male

        result = tes5.HDPT.from_record(record)
        assert result['Flags'] == 3

    def test_valid_races(self):
        record = Record('HDPT', FormID(0x802), 0)
        record.add_subrecord('EDID', b'TestHP\x00')
        record.add_subrecord('RNAM', struct.pack('<I', 0x12345))

        result = tes5.HDPT.from_record(record)
        assert result['Valid Races'].value == 0x12345


class TestARMA:
    def test_armor_addon_basic(self):
        record = Record('ARMA', FormID(0x900), 0)
        record.add_subrecord('EDID', b'TestAddon\x00')
        record.add_subrecord('RNAM', struct.pack('<I', 0x13746))  # NordRace
        record.add_subrecord('BOD2', struct.pack('<II', 0x04, 0))  # Body, Light

        result = tes5.ARMA.from_record(record)
        assert result['Editor ID'] == 'TestAddon'
        assert result['Race'].value == 0x13746
        assert result['Body Template']['first_person_flags'] == 4

    def test_additional_races(self):
        record = Record('ARMA', FormID(0x901), 0)
        record.add_subrecord('EDID', b'TestAddon\x00')
        record.add_subrecord('MODL', struct.pack('<I', 0x13746))  # Race 1
        record.add_subrecord('MODL', struct.pack('<I', 0x13747))  # Race 2

        result = tes5.ARMA.from_record(record)
        addl = result['Additional Races']
        assert isinstance(addl, list)
        assert len(addl) == 2


class TestRACE:
    def test_race_basic(self):
        record = Record('RACE', FormID(0xA00), 0)
        record.add_subrecord('EDID', b'TestRace\x00')
        record.add_subrecord('WNAM', struct.pack('<I', 0x12345))  # Skin
        record.add_subrecord('RNAM', struct.pack('<I', 0x23456))  # Armor race
        record.add_subrecord('NAM8', struct.pack('<I', 0x34567))  # Morph race

        result = tes5.RACE.from_record(record)
        assert result['Editor ID'] == 'TestRace'
        assert result['Skin'].value == 0x12345
        assert result['Armor Race'].value == 0x23456
        assert result['Morph Race'].value == 0x34567

    def test_race_tint_entries(self):
        record = Record('RACE', FormID(0xA01), 0)
        record.add_subrecord('EDID', b'TestRace\x00')
        record.add_subrecord('TINI', struct.pack('<H', 0))
        record.add_subrecord('TINT', b'tintmask.dds\x00')
        record.add_subrecord('TINP', struct.pack('<H', 1))

        result = tes5.RACE.from_record(record)
        assert result['Tint Index'] == 0
        assert result['Tint File'] == 'tintmask.dds'
        assert result['Tint Mask Type'] == 1


class TestNPCExtensions:
    def test_npc_head_parts(self):
        record = Record('NPC_', FormID(0xB00), 0)
        record.add_subrecord('EDID', b'TestNPC\x00')
        record.add_subrecord('PNAM', struct.pack('<I', 0x100))
        record.add_subrecord('PNAM', struct.pack('<I', 0x200))
        record.add_subrecord('PNAM', struct.pack('<I', 0x300))

        result = tes5.NPC_.from_record(record)
        hp = result['Head Part']
        assert isinstance(hp, list)
        assert len(hp) == 3
        assert hp[0].value == 0x100

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

    def test_npc_default_outfit(self):
        record = Record('NPC_', FormID(0xB02), 0)
        record.add_subrecord('EDID', b'TestNPC\x00')
        record.add_subrecord('DOFT', struct.pack('<I', 0xABCDE))

        result = tes5.NPC_.from_record(record)
        assert result['Default Outfit'].value == 0xABCDE

    def test_npc_qnam(self):
        record = Record('NPC_', FormID(0xB03), 0)
        record.add_subrecord('EDID', b'TestNPC\x00')
        record.add_subrecord('QNAM',
                             struct.pack('<fff', 1.0, 0.8, 0.6))

        result = tes5.NPC_.from_record(record)
        assert abs(result['Texture Lighting']['red'] - 1.0) < 0.001
        assert abs(result['Texture Lighting']['blue'] - 0.6) < 0.001


class TestRegistration:
    def test_new_types_registered(self):
        registry = GameRegistry.get_game('tes5')
        for sig in ['HDPT', 'ARMA', 'RACE']:
            assert registry.get(sig) is not None, f"{sig} not registered"


# ---------------------------------------------------------------------------
# Real game file tests
# ---------------------------------------------------------------------------

class TestSkyrimPhaseA:
    @pytest.fixture(scope='class')
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_resolve_nord_race(self, skyrim):
        nord = skyrim.get_record_by_editor_id('NordRace')
        if not nord:
            pytest.skip("NordRace not found")
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
        hdpts = skyrim.get_records_by_signature('HDPT')
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
        armas = skyrim.get_records_by_signature('ARMA')
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
        races = skyrim.get_records_by_signature('RACE')
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
        npcs = skyrim.get_records_by_signature('NPC_')
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
        npcs = skyrim.get_records_by_signature('NPC_')
        for npc in npcs[:200]:
            tini = npc.get_subrecords('TINI')
            if len(tini) > 0:
                result = tes5.NPC_.from_record(npc)
                assert 'Tint Index' in result
                break
