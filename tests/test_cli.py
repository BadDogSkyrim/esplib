"""Tests for CLI commands."""

import json
import struct
import pytest
from pathlib import Path
from unittest.mock import patch

from esplib.cli.commands import info, dump, diff, validate, rename_master
from esplib import Plugin, Record, SubRecord, FormID

from tests.conftest import find_skyrim_esm


class FakeArgs:
    """Minimal args object for testing commands."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestFileNotFound:
    def test_info_missing_file(self, capsys):
        from esplib.cli.main import main
        with patch('sys.argv', ['esplib', 'info', 'nonexistent_plugin.esp']):
            ret = main()
        assert ret == 1
        err = capsys.readouterr().err
        assert 'file not found' in err.lower()

    def test_diff_missing_file(self, tmp_path, capsys):
        # Create one valid file, reference one missing
        from esplib.cli.main import main
        plugin = Plugin()
        path = tmp_path / 'exists.esp'
        plugin.save(path)
        with patch('sys.argv', ['esplib', 'diff', str(path), 'missing.esp']):
            ret = main()
        assert ret == 1
        err = capsys.readouterr().err
        assert 'file not found' in err.lower()


class TestInfoCommand:
    def test_info_text(self, tmp_path, capsys):
        plugin = Plugin()
        plugin.header.is_esm = True
        plugin.header.author = 'TestAuthor'
        plugin.header.version = 1.71
        rec = Record('GMST', FormID(0x800), 0)
        rec.add_subrecord('EDID', b'fTest\x00')
        plugin.add_record(rec)
        path = tmp_path / 'test.esm'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), format='text')
        info.run(args)
        out = capsys.readouterr().out
        assert 'ESM' in out
        assert 'TestAuthor' in out

    def test_info_json(self, tmp_path, capsys):
        plugin = Plugin()
        plugin.header.is_esm = True
        path = tmp_path / 'test.esm'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), format='json')
        info.run(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['file_type'] == 'ESM'


class TestDumpCommand:
    def test_dump_text(self, tmp_path, capsys):
        plugin = Plugin()
        rec = Record('GMST', FormID(0x800), 0)
        rec.add_subrecord('EDID', b'fTestVal\x00')
        rec.add_subrecord('DATA', struct.pack('<f', 3.14))
        plugin.add_record(rec)
        path = tmp_path / 'test.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), record_type=None, form_id=None,
                        editor_id=None, game=None, format='text', limit=0)
        dump.run(args)
        out = capsys.readouterr().out
        assert 'fTestVal' in out

    def test_dump_json(self, tmp_path, capsys):
        plugin = Plugin()
        rec = Record('GMST', FormID(0x800), 0)
        rec.add_subrecord('EDID', b'iTest\x00')
        plugin.add_record(rec)
        path = tmp_path / 'test.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), record_type=None, form_id=None,
                        editor_id=None, game=None, format='json', limit=0)
        dump.run(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_dump_csv(self, tmp_path, capsys):
        plugin = Plugin()
        rec = Record('GMST', FormID(0x800), 0)
        rec.add_subrecord('EDID', b'fVal\x00')
        plugin.add_record(rec)
        path = tmp_path / 'test.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), record_type=None, form_id=None,
                        editor_id=None, game=None, format='csv', limit=0)
        dump.run(args)
        out = capsys.readouterr().out
        assert '_signature' in out  # CSV header
        assert 'GMST' in out

    def test_dump_filter_by_type(self, tmp_path, capsys):
        plugin = Plugin()
        rec1 = Record('GMST', FormID(0x800), 0)
        rec1.add_subrecord('EDID', b'fVal\x00')
        rec2 = Record('GLOB', FormID(0x801), 0)
        rec2.add_subrecord('EDID', b'gVal\x00')
        plugin.add_record(rec1)
        plugin.add_record(rec2)
        path = tmp_path / 'test.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), record_type='GMST', form_id=None,
                        editor_id=None, game=None, format='text', limit=0)
        dump.run(args)
        out = capsys.readouterr().out
        assert 'fVal' in out
        assert 'gVal' not in out


class TestDiffCommand:
    def test_diff_text(self, tmp_path, capsys):
        p1 = Plugin()
        rec1 = Record('GMST', FormID(0x800), 0)
        rec1.add_subrecord('EDID', b'fTest\x00')
        rec1.add_subrecord('DATA', struct.pack('<f', 1.0))
        p1.add_record(rec1)
        path1 = tmp_path / 'a.esp'
        p1.save(path1)

        p2 = Plugin()
        rec2 = Record('GMST', FormID(0x800), 0)
        rec2.add_subrecord('EDID', b'fTest\x00')
        rec2.add_subrecord('DATA', struct.pack('<f', 2.0))
        p2.add_record(rec2)
        path2 = tmp_path / 'b.esp'
        p2.save(path2)

        args = FakeArgs(plugin1=str(path1), plugin2=str(path2),
                        field_level=False, game=None, format='text')
        diff.run(args)
        out = capsys.readouterr().out
        assert 'Changed:   1' in out

    def test_diff_json(self, tmp_path, capsys):
        p1 = Plugin()
        path1 = tmp_path / 'a.esp'
        p1.save(path1)

        p2 = Plugin()
        rec = Record('GMST', FormID(0x800), 0)
        p2.add_record(rec)
        path2 = tmp_path / 'b.esp'
        p2.save(path2)

        args = FakeArgs(plugin1=str(path1), plugin2=str(path2),
                        field_level=False, game=None, format='json')
        diff.run(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['added'] == 1


class TestValidateCommand:
    def test_valid_plugin(self, tmp_path, capsys):
        plugin = Plugin()
        rec = Record('GMST', FormID(0x800), 0)
        plugin.add_record(rec)
        path = tmp_path / 'good.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), game=None, format='text')
        ret = validate.run(args)
        assert ret == 0
        assert 'no issues' in capsys.readouterr().out

    def test_duplicate_formid(self, tmp_path, capsys):
        plugin = Plugin()
        plugin.add_record(Record('GMST', FormID(0x800), 0))
        plugin.add_record(Record('GLOB', FormID(0x800), 0))
        path = tmp_path / 'bad.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), game=None, format='text')
        ret = validate.run(args)
        assert ret == 1
        assert 'Duplicate' in capsys.readouterr().out


class TestRenameMasterCommand:
    def test_rename(self, tmp_path, capsys):
        plugin = Plugin()
        plugin.header.masters = ['OldMaster.esm']
        plugin.header.master_sizes = [0]
        rec = Record('GMST', FormID(0x00000800), 0)
        rec.add_subrecord('EDID', b'fTest\x00')
        plugin.add_record(rec)
        path = tmp_path / 'test.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), old_name='OldMaster.esm',
                        new_name='NewMaster.esm')
        ret = rename_master.run(args)
        assert ret == 0

        # Verify
        reloaded = Plugin(path)
        assert reloaded.header.masters == ['NewMaster.esm']

    def test_rename_nonexistent_master(self, tmp_path, capsys):
        plugin = Plugin()
        plugin.header.masters = ['Real.esm']
        plugin.header.master_sizes = [0]
        path = tmp_path / 'test.esp'
        plugin.save(path)

        args = FakeArgs(plugin=str(path), old_name='Fake.esm',
                        new_name='New.esm')
        ret = rename_master.run(args)
        assert ret == 1
