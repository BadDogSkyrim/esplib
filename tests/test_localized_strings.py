"""Integration tests for localized string resolution.

Requires Skyrim.esm and its string tables (extracted from BSA).
"""

import pytest
from pathlib import Path


SKYRIM_DATA_PATHS = [
    Path(r"C:\Steam\steamapps\common\Skyrim Special Edition\Data"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data"),
    Path(r"C:\Program Files\Steam\steamapps\common\Skyrim Special Edition\Data"),
    Path(r"D:\Steam\steamapps\common\Skyrim Special Edition\Data"),
    Path(r"D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data"),
]

STRING_TABLE_PATHS = [
    Path(r"C:\Modding\SkyrimSEAssets\00 Vanilla Assets\strings"),
]


def _find_skyrim_data():
    for p in SKYRIM_DATA_PATHS:
        if p.exists():
            return p
    return None


def _find_strings_dir():
    """Find directory containing Skyrim_english.STRINGS."""
    data = _find_skyrim_data()
    if data:
        d = data / "Strings"
        if (d / "Skyrim_english.STRINGS").exists():
            return d
    for p in STRING_TABLE_PATHS:
        if p.exists():
            for f in p.iterdir():
                if f.name.lower() == "skyrim_english.strings":
                    return p
    return None


def _strings_available():
    return _find_strings_dir() is not None


requires_strings = pytest.mark.skipif(
    not _strings_available(),
    reason="Skyrim string tables not found",
)


@requires_strings
class TestLocalizedFullName:
    """full_name resolves correctly for localized plugins."""

    @pytest.fixture(scope="class")
    def skyrim(self, skyrim_plugin):
        return skyrim_plugin

    def test_plugin_is_localized(self, skyrim):
        assert skyrim.is_localized

    def test_string_tables_loaded(self, skyrim):
        assert skyrim.string_tables is not None
        assert skyrim.string_tables.strings is not None

    def test_nord_race_name(self, skyrim):
        for r in skyrim.get_records_by_signature('RACE'):
            if r.editor_id == 'NordRace':
                assert r.full_name == 'Nord'
                return
        pytest.fail("NordRace not found")

    def test_breton_race_name(self, skyrim):
        for r in skyrim.get_records_by_signature('RACE'):
            if r.editor_id == 'BretonRace':
                assert r.full_name == 'Breton'
                return
        pytest.fail("BretonRace not found")

    def test_dark_elf_race_name(self, skyrim):
        for r in skyrim.get_records_by_signature('RACE'):
            if r.editor_id == 'DarkElfRace':
                assert r.full_name == 'Dark Elf'
                return
        pytest.fail("DarkElfRace not found")

    def test_iron_sword_name(self, skyrim):
        for r in skyrim.get_records_by_signature('WEAP'):
            if r.editor_id == 'IronSword':
                assert r.full_name == 'Iron Sword'
                return
        pytest.fail("IronSword not found")


class TestNonLocalizedFullName:
    """Non-localized plugins still work with inline strings."""

    def test_inline_null_terminated(self):
        from esplib import Record, FormID
        rec = Record('WEAP', FormID(0x100), 0)
        rec.add_subrecord('FULL', b'Test Sword\x00')
        assert rec.full_name == 'Test Sword'

    def test_no_full_subrecord(self):
        from esplib import Record, FormID
        rec = Record('WEAP', FormID(0x100), 0)
        assert rec.full_name is None
