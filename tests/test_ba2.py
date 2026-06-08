"""Tests for BA2 archive reading and FO4 localized-string resolution.

The real-file tests are marked ``gamefiles`` and skip when Fallout 4 isn't
installed. They validate that:
  - GNRL and DX10 BA2 archives parse and index their files,
  - string tables extract from a GNRL archive,
  - FO4 localized FULL names resolve (via the `_en` language alias) when a
    plugin is loaded from a Data dir whose BA2s hold the strings.
"""

import struct
import pytest

from esplib import Plugin, Ba2Reader
from esplib.strings import _language_aliases
from esplib.game_discovery import find_game_data, find_game_file


def _fo4_data():
    return find_game_data('fo4')


# ---------------------------------------------------------------------------
# Unit: language aliasing (no game files)
# ---------------------------------------------------------------------------


class TestLanguageAliases:


    def test_english_expands_to_en(self):
        # FO4 names English strings <plugin>_en.STRINGS; Skyrim uses _english.
        assert _language_aliases('english') == ['english', 'en']


    def test_en_expands_to_english(self):
        assert _language_aliases('en') == ['en', 'english']


    def test_unknown_language_passes_through(self):
        assert _language_aliases('klingon') == ['klingon']


# ---------------------------------------------------------------------------
# Real-file: BA2 reading (requires Fallout 4)
# ---------------------------------------------------------------------------


@pytest.mark.gamefiles
class TestBa2Reader:


    def test_gnrl_archive_parses(self):
        data = _fo4_data()
        if not data:
            pytest.skip("Fallout 4 not installed")
        path = data / 'Fallout4 - Interface.ba2'
        if not path.exists():
            pytest.skip("Interface BA2 not found")
        with Ba2Reader(path) as ba2:
            assert ba2.archive_type == 'GNRL'
            files = ba2.list_files()
            assert len(files) > 0
            # The English STRINGS table lives here.
            assert ba2.has_file(r'strings\fallout4_en.strings')


    def test_extract_strings_table(self):
        data = _fo4_data()
        if not data:
            pytest.skip("Fallout 4 not installed")
        path = data / 'Fallout4 - Interface.ba2'
        if not path.exists():
            pytest.skip("Interface BA2 not found")
        with Ba2Reader(path) as ba2:
            raw = ba2.read_file(r'strings/fallout4_en.strings')
            assert raw is not None and len(raw) > 8
            count, data_size = struct.unpack('<II', raw[:8])
            assert count > 0
            assert data_size > 0


    def test_dx10_archive_parses(self):
        data = _fo4_data()
        if not data:
            pytest.skip("Fallout 4 not installed")
        path = data / 'Fallout4 - Textures1.ba2'
        if not path.exists():
            pytest.skip("Textures BA2 not found")
        with Ba2Reader(path) as ba2:
            assert ba2.archive_type == 'DX10'
            assert len(ba2.list_files()) > 0


    def test_dx10_extract_reconstructs_dds(self):
        # A DX10 texture must come back as a complete DX10-headered DDS:
        # 'DDS ' magic + 124-byte header + 20-byte DXT10 header, with the
        # dxgiFormat / dimensions matching the indexed metadata and the body
        # length equal to the concatenated mip chunks.
        data = _fo4_data()
        if not data:
            pytest.skip("Fallout 4 not installed")
        path = data / 'Fallout4 - Textures1.ba2'
        if not path.exists():
            pytest.skip("Textures BA2 not found")
        target = r'textures\actors\character\basehumanmale\basemalehead_d.dds'
        with Ba2Reader(path) as ba2:
            assert ba2.has_file(target)
            dds = ba2.read_file(target)
            assert dds[:4] == b'DDS '
            (hdr_size,) = struct.unpack('<I', dds[4:8])
            assert hdr_size == 124
            assert dds[84:88] == b'DX10'  # ddspf.dwFourCC
            height, width = struct.unpack('<II', dds[12:20])
            dxgi_format = struct.unpack('<I', dds[128:132])[0]
            entry = ba2._by_name[target.replace('/', '\\')]
            assert (width, height) == (entry.dx10_width, entry.dx10_height)
            assert dxgi_format == entry.dx10_format
            body = sum(unpacked for _, _, unpacked in entry.chunks)
            assert len(dds) == 148 + body


# ---------------------------------------------------------------------------
# Real-file: end-to-end localized name resolution (requires Fallout 4)
# ---------------------------------------------------------------------------


@pytest.mark.gamefiles
class TestPartialLoad:
    """Plugin.load(only_signatures=...) parses just the named top-level groups
    and seeks past the rest — a fast partial load."""

    def test_only_npc_skips_other_groups(self):
        esm = find_game_file('Fallout4.esm', 'fo4')
        if not esm:
            pytest.skip("Fallout4.esm not found")
        p = Plugin.load(esm, only_signatures={'NPC_'})
        assert p.partial_load is True
        assert len(list(p.get_records_by_signature('NPC_'))) > 1000
        # Groups we didn't ask for must not have been parsed.
        assert not list(p.get_records_by_signature('WEAP'))
        assert not list(p.get_records_by_signature('CELL'))
        # TES4 header is always parsed.
        assert p.header is not None

    def test_empty_set_is_header_only(self):
        esm = find_game_file('Fallout4.esm', 'fo4')
        if not esm:
            pytest.skip("Fallout4.esm not found")
        p = Plugin.load(esm, only_signatures=frozenset())
        assert p.partial_load is True
        assert not list(p.get_records_by_signature('NPC_'))
        assert not list(p.get_records_by_signature('WEAP'))
        assert p.header is not None  # TES4 still parsed


@pytest.mark.gamefiles
@pytest.mark.slow
class TestFo4StringResolution:


    @pytest.fixture(scope='class')
    def fo4(self):
        esm = find_game_file('Fallout4.esm', 'fo4')
        if not esm:
            pytest.skip("Fallout4.esm not found")
        return Plugin.load(esm)


    def test_string_tables_loaded(self, fo4):
        assert fo4.is_localized
        assert fo4.string_tables is not None
        assert fo4.string_tables.strings is not None


    def test_npc_full_names_resolve(self, fo4):
        resolved = 0
        for npc in fo4.get_records_by_signature('NPC_'):
            full = npc.get_subrecord('FULL')
            if full is None or full.size != 4:
                continue
            if npc.full_name:
                resolved += 1
            if resolved >= 5:
                break
        assert resolved >= 5, "expected localized NPC names to resolve from BA2"
