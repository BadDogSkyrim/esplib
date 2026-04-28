"""Tests for scripts/dump_dialog.py.

The dialog-dump pipeline is mostly mechanical iteration. The
interesting bits are: (1) walking DIAL → child INFO group → per-
response NAM1 correctly, (2) resolving localized string-table ids
back to text, (3) collecting QNAM quest EditorIDs.

We exercise these against Skyrim.esm because synthetically building
a localized DIAL/INFO group with string tables is much heavier than
using a real plugin we already load for other tests."""

import csv
import io
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so we can import dump_dialog.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import esplib.defs.tes5  # noqa: F401
from dump_dialog import (
    CSV_COLUMNS, iter_dialog_rows, write_csv,
)


@pytest.mark.gamefiles
@pytest.mark.slow
class TestDumpDialog:

    def test_columns_match_schema(self):
        """Lock the public CSV column set so build_dialog_patch.py
        and the editing workflow can rely on it."""
        assert CSV_COLUMNS == [
            'form_id', 'plugin', 'quest_edid', 'dial_edid', 'dial_full',
            'info_edid', 'response_index', 'original_text', 'new_text',
            'notes',
        ]

    def test_da03_barbas_greeting_row(self, skyrim_plugin):
        """DA03BarbasGreeting1A is a known stable DIAL whose FULL
        resolves to a fixed line. The first INFO under it has one
        response with a known text and a resolved quest EDID."""
        rows = []
        for row in iter_dialog_rows(skyrim_plugin):
            if row['dial_edid'] == 'DA03BarbasGreeting1A':
                rows.append(row)
            elif rows:
                break  # past the target DIAL

        assert rows, "no rows for DA03BarbasGreeting1A"
        first = rows[0]
        assert first['plugin'] == 'Skyrim.esm'
        assert first['dial_full'] == "I've got things to do."
        assert first['quest_edid'] == 'DA03'
        assert first['response_index'] == 0
        assert first['original_text'] == (
            "I know, I know... Wars to fight, dragons to confront, "
            "guild business to conduct."
        )
        assert first['new_text'] == ''
        assert first['notes'] == ''

    def test_multi_response_indexes(self, skyrim_plugin):
        """Walk the responses of a known three-response INFO and
        verify response_index goes 0, 1, 2 with distinct text. Locks
        the linear-walk logic in _iter_responses."""
        target_form_id = '[00] 01362F'
        rows = [r for r in iter_dialog_rows(skyrim_plugin)
                if r['form_id'] == target_form_id]
        if not rows:
            pytest.skip(f"INFO {target_form_id} not in Skyrim.esm")

        assert [r['response_index'] for r in rows] == [0, 1, 2]
        texts = [r['original_text'] for r in rows]
        assert len(set(texts)) == 3
        assert all(t for t in texts)

    def test_csv_round_trip(self, skyrim_plugin):
        """write_csv → csv.DictReader must round-trip a small slice
        of rows with all columns intact."""
        rows = []
        for row in iter_dialog_rows(skyrim_plugin):
            rows.append(row)
            if len(rows) >= 3:
                break

        buf = io.StringIO()
        write_csv(rows, buf)
        buf.seek(0)
        reader = csv.DictReader(buf)
        assert reader.fieldnames == CSV_COLUMNS
        round_tripped = list(reader)
        assert len(round_tripped) == len(rows)
        for orig, rt in zip(rows, round_tripped):
            assert rt['form_id'] == orig['form_id']
            assert rt['dial_edid'] == orig['dial_edid']
            assert rt['original_text'] == orig['original_text']
            # response_index becomes a string after CSV round-trip
            assert int(rt['response_index']) == orig['response_index']
