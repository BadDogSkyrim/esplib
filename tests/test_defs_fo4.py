"""Tests for Fallout 4 record definitions — synthetic and real game file.

The real-file tests are marked ``gamefiles`` and skip automatically when
Fallout4.esm isn't installed. They validate the FO4 schemas against the
vanilla master: every record of each defined type must resolve, and
unmodified records must round-trip byte-for-byte.
"""

import struct
import pytest

from esplib import Plugin, Record, FormID
from esplib.utils import BinaryReader
from esplib.defs import GameRegistry, fo4
from esplib.game_discovery import find_game_file


def find_fallout4_esm():
    """Locate Fallout4.esm if Fallout 4 is installed, else None."""
    return find_game_file('Fallout4.esm', 'fo4')


@pytest.fixture(scope="module")
def fo4_plugin():
    """Fallout4.esm loaded once per module (skips if not installed)."""
    esm = find_fallout4_esm()
    if not esm:
        pytest.skip("Fallout4.esm not found")
    return Plugin.load(esm)


# ---------------------------------------------------------------------------
# Registration & game detection (no game files needed)
# ---------------------------------------------------------------------------


class TestRegistration:


    def test_fo4_registered(self):
        reg = GameRegistry.get_game('fo4')
        assert reg is not None
        for sig in ('GMST', 'GLOB', 'KYWD', 'FLST', 'TXST', 'CLFM',
                    'HDPT', 'ARMA', 'ARMO', 'RACE', 'NPC_'):
            assert reg.get(sig) is not None, f"{sig} not registered for fo4"


    def test_detect_fo4_versions(self):
        assert GameRegistry.detect_game(0.95) is GameRegistry.get_game('fo4')
        assert GameRegistry.detect_game(1.0) is GameRegistry.get_game('fo4')


    def test_detect_does_not_collide_with_skyrim(self):
        # Skyrim LE (0.94) and SE (1.71) must stay 'tes5', not 'fo4'.
        assert GameRegistry.detect_game(0.94) is GameRegistry.get_game('tes5')
        assert GameRegistry.detect_game(1.71) is GameRegistry.get_game('tes5')


# ---------------------------------------------------------------------------
# Synthetic record tests (no game files needed)
# ---------------------------------------------------------------------------


class TestSyntheticGLOB:


    def test_boolean_type(self):
        # FO4 adds the Boolean ('b') global type Skyrim lacks.
        rec = Record('GLOB', FormID(0x200), 0)
        rec.add_subrecord('EDID', b'TestBool\x00')
        rec.add_subrecord('FNAM', bytes([ord('b')]))
        rec.add_subrecord('FLTV', struct.pack('<f', 1.0))
        result = fo4.GLOB.from_record(rec)
        assert result['Type'] == 'Boolean'


class TestSyntheticCLFM:


    def test_color_and_flags(self):
        rec = Record('CLFM', FormID(0x300), 0)
        rec.add_subrecord('EDID', b'HairColorTest\x00')
        rec.add_subrecord('CNAM', struct.pack('<I', 0x10204080))
        rec.add_subrecord('FNAM', struct.pack('<I', 0x1))  # Playable
        result = fo4.CLFM.from_record(rec)
        assert result['Editor ID'] == 'HairColorTest'
        assert result['Color/Index'] == 0x10204080
        assert 'Playable' in result['Flags']


class TestSyntheticNPCWeight:


    def test_mwgt_struct(self):
        rec = Record('NPC_', FormID(0x400), 0)
        rec.add_subrecord('EDID', b'TestNPC\x00')
        rec.add_subrecord('MWGT', struct.pack('<fff', 0.25, 0.5, 0.75))
        result = fo4.NPC_.from_record(rec)
        assert result['Weight']['thin'] == pytest.approx(0.25)
        assert result['Weight']['muscular'] == pytest.approx(0.5)
        assert result['Weight']['fat'] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Real-file validation (requires Fallout4.esm)
# ---------------------------------------------------------------------------

_TARGETS = ['GMST', 'GLOB', 'KYWD', 'FLST', 'TXST', 'CLFM',
            'HDPT', 'ARMA', 'ARMO', 'RACE', 'NPC_']


@pytest.mark.gamefiles
class TestFallout4Esm:


    def test_autodetects_fo4(self, fo4_plugin):
        assert fo4_plugin._game_registry is GameRegistry.get_game('fo4')
        assert 0.945 <= fo4_plugin.header.version < 1.01


    @pytest.mark.parametrize('sig', _TARGETS)
    def test_all_records_resolve(self, fo4_plugin, sig):
        """Every record of this type must resolve without error."""
        n = 0
        for rec in fo4_plugin.get_records_by_signature(sig):
            rec.schema.from_record(rec)  # raises on failure
            n += 1
        assert n > 0, f"no {sig} records found"


    @pytest.mark.parametrize('sig', ['NPC_', 'ARMA', 'ARMO', 'RACE', 'HDPT'])
    def test_reparse_stable(self, fo4_plugin, sig):
        """Unmodified records serialize -> reparse -> serialize identically."""
        for i, rec in enumerate(fo4_plugin.get_records_by_signature(sig)):
            if i >= 100:
                break
            raw = rec.to_bytes()
            rt = Record.from_bytes(BinaryReader(raw))
            assert rt.to_bytes() == raw, f"{sig} #{i} not reparse-stable"


    def test_modify_preserves_subrecord_order(self, fo4_plugin):
        """Marking an NPC modified (triggering auto-sort) must preserve the
        subrecord order of structurally-grouped blocks — Object Template
        (OBTE/Combination[OBTF/FULL/OBTS]/STOP), Destructible (DEST/DSTD/DSTF),
        Actor Sounds (CS2H/Sound[CS2K/CS2D]/CS2E/CS2F), and APPR. These reuse
        signatures (FULL inside a combination) or repeat (CS2K/CS2D pairs), so
        a naive schema sort would corrupt them. Every vanilla NPC carrying one
        of these blocks must round-trip its full signature order unchanged.
        """
        watch = {'APPR', 'OBTE', 'OBTF', 'OBTS', 'STOP',
                 'DSTD', 'DSTF', 'CS2K', 'CS2D'}
        checked = 0
        for npc in fo4_plugin.get_records_by_signature('NPC_'):
            before = [s.signature for s in npc.subrecords]
            if not (watch & set(before)):
                continue
            checked += 1
            npc.modified = True
            for sr in npc.subrecords:
                sr.modified = True
            rt = Record.from_bytes(BinaryReader(npc.to_bytes()))
            after = [s.signature for s in rt.subrecords]
            assert after == before, (
                f"{npc.editor_id}: subrecord order changed on modify+save\n"
                f"  before: {before}\n  after:  {after}")
        assert checked > 100, f"expected many grouped NPCs, only saw {checked}"
