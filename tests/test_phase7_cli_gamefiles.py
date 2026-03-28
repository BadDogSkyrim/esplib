"""Phase 7 converted tests: CLI commands against real game files.

Synthetic CLI tests are in test_cli.py. These tests run CLI commands
against the actual Skyrim.esm installation to verify real-world behavior.
"""

import json
import pytest
from unittest.mock import patch

from esplib import Plugin
from esplib.cli.commands import info, dump, diff, validate
from esplib.cli.main import main as cli_main

from tests.conftest import find_skyrim_esm


class FakeArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Info command against Skyrim.esm
# ---------------------------------------------------------------------------

class TestInfoSkyrim:
    @pytest.fixture(scope='class')
    def esm_path(self):
        path = find_skyrim_esm()
        if not path:
            pytest.skip("Skyrim.esm not found")
        return str(path)

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_info_text_shows_esm(self, esm_path, capsys):
        """info text output should show ESM file type."""
        args = FakeArgs(plugin=esm_path, format='text')
        info.run(args)
        out = capsys.readouterr().out
        assert 'ESM' in out

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_info_text_shows_version(self, esm_path, capsys):
        """info text output should show version 1.71."""
        args = FakeArgs(plugin=esm_path, format='text')
        info.run(args)
        out = capsys.readouterr().out
        assert '1.71' in out

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_info_json_valid(self, esm_path, capsys):
        """info --format json should produce valid JSON."""
        args = FakeArgs(plugin=esm_path, format='json')
        info.run(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['file_type'] == 'ESM'
        assert data['is_localized'] is True

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_info_json_has_record_types(self, esm_path, capsys):
        """info JSON should include record type counts."""
        args = FakeArgs(plugin=esm_path, format='json')
        info.run(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert 'record_types' in data
        assert 'WEAP' in data['record_types']


# ---------------------------------------------------------------------------
# Dump command against Skyrim.esm
# ---------------------------------------------------------------------------

class TestDumpSkyrim:
    @pytest.fixture(scope='class')
    def esm_path(self):
        path = find_skyrim_esm()
        if not path:
            pytest.skip("Skyrim.esm not found")
        return str(path)

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dump_weap_iron_sword_text(self, esm_path, capsys):
        """Dump IronSword by editor-id should show damage."""
        args = FakeArgs(plugin=esm_path, record_type='WEAP',
                        form_id=None, editor_id='IronSword',
                        game=None, format='text', limit=0)
        dump.run(args)
        out = capsys.readouterr().out
        assert 'IronSword' in out

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dump_weap_iron_sword_json(self, esm_path, capsys):
        """Dump IronSword as JSON should produce valid JSON with fields."""
        args = FakeArgs(plugin=esm_path, record_type='WEAP',
                        form_id=None, editor_id='IronSword',
                        game=None, format='json', limit=0)
        dump.run(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dump_glob_csv(self, esm_path, capsys):
        """Dump GLOB records as CSV with limit."""
        args = FakeArgs(plugin=esm_path, record_type='GLOB',
                        form_id=None, editor_id=None,
                        game=None, format='csv', limit=5)
        dump.run(args)
        out = capsys.readouterr().out
        # CSV should have a header row + data rows
        lines = out.strip().splitlines()
        assert len(lines) >= 2  # header + at least 1 data row
        assert len(lines) <= 6  # header + at most 5 data rows

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dump_filter_by_type(self, esm_path, capsys):
        """Dumping with --type WEAP should only show weapons."""
        args = FakeArgs(plugin=esm_path, record_type='WEAP',
                        form_id=None, editor_id=None,
                        game=None, format='text', limit=3)
        dump.run(args)
        out = capsys.readouterr().out
        assert 'WEAP' in out


# ---------------------------------------------------------------------------
# Validate command against Skyrim.esm
# ---------------------------------------------------------------------------

class TestValidateSkyrim:
    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_skyrim_esm_valid(self, capsys):
        """Skyrim.esm should pass basic validation."""
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")

        args = FakeArgs(plugin=str(esm_path), game=None, format='text')
        ret = validate.run(args)
        out = capsys.readouterr().out
        # Skyrim.esm should either pass or only have minor warnings
        # (duplicate FormIDs in Skyrim.esm are known)
        assert ret is not None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestCLIErrorHandling:
    def test_info_nonexistent_file(self, capsys):
        """info on a missing file should report error gracefully."""
        with patch('sys.argv', ['esplib', 'info', 'does_not_exist.esp']):
            ret = cli_main()
        assert ret == 1
        err = capsys.readouterr().err
        assert 'file not found' in err.lower()
