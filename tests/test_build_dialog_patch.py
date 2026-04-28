"""Tests for scripts/build_dialog_patch.py.

The end-to-end test builds a patch ESP from a one-row CSV that
edits DA03BarbasGreeting1A's first response, reloads the patch,
and verifies the INFO override has the new text inline (zstring,
non-localized) and that SNAM has been dropped from the edited
response."""

import csv
import io
import struct
import sys
import tempfile
from pathlib import Path

import pytest

# Make scripts importable as modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import esplib.defs.tes5  # noqa: F401
from esplib import Plugin
from esplib.record import GroupRecord, Record

from build_dialog_patch import (
    build_patch, parse_edits, _apply_info_edits,
)


def make_row(**overrides):
    base = {
        'form_id': '[00] 01BFC2',
        'plugin': 'Skyrim.esm',
        'quest_edid': 'DA03',
        'dial_edid': 'DA03BarbasGreeting1A',
        'dial_full': "I've got things to do.",
        'new_dial_full': '',
        'info_edid': '',
        'response_index': '0',
        'original_text': "I know, I know... Wars to fight, dragons to confront, guild business to conduct.",
        'new_text': '',
        'notes': '',
    }
    base.update(overrides)
    return base


class TestParseEdits:

    def test_blank_new_text_skipped(self):
        edits, _ = parse_edits([make_row(new_text='')])
        assert edits == {}

    def test_new_text_equals_original_skipped(self):
        edits, _ = parse_edits([
            make_row(new_text="I know, I know... Wars to fight, dragons to confront, guild business to conduct."),
        ])
        assert edits == {}

    def test_real_edit_picked_up(self):
        edits, plugin_name = parse_edits([make_row(new_text='Hello.')])
        assert plugin_name == 'Skyrim.esm'
        assert edits == {
            '[00] 01BFC2': {'responses': {0: 'Hello.'}, 'new_dial_full': None}
        }

    def test_multiple_responses_same_info(self):
        rows = [
            make_row(response_index='0', new_text='A'),
            make_row(response_index='1', original_text='other', new_text='B'),
            make_row(response_index='2', original_text='same', new_text='same'),
        ]
        edits, _ = parse_edits(rows)
        assert edits == {
            '[00] 01BFC2': {'responses': {0: 'A', 1: 'B'}, 'new_dial_full': None}
        }

    def test_mixed_plugins_rejected(self):
        rows = [make_row(plugin='Skyrim.esm', new_text='A'),
                make_row(plugin='Other.esp', new_text='B')]
        with pytest.raises(ValueError):
            parse_edits(rows)

    def test_dial_full_edit_picked_up(self):
        edits, _ = parse_edits([
            make_row(new_dial_full='New topic line.'),
        ])
        assert edits == {
            '[00] 01BFC2': {'responses': {}, 'new_dial_full': 'New topic line.'}
        }

    def test_dial_full_unchanged_skipped(self):
        edits, _ = parse_edits([
            make_row(new_dial_full="I've got things to do."),  # same as dial_full
        ])
        assert edits == {}

    def test_dial_full_inconsistent_within_one_info_raises(self):
        rows = [
            make_row(response_index='0', new_dial_full='A'),
            make_row(response_index='1', original_text='x', new_dial_full='B'),
        ]
        with pytest.raises(ValueError, match='Inconsistent new_dial_full'):
            parse_edits(rows)


@pytest.mark.gamefiles
@pytest.mark.slow
class TestBuildPatch:

    def test_patch_overrides_info_with_new_text(self, skyrim_plugin, tmp_path):
        """Build a patch from a one-row edit, reload it, and confirm
        the INFO override has the new NAM1 (inline) and SNAM is
        stripped from the edited response."""
        new_text = "I have errands to run, dog."
        rows = [make_row(new_text=new_text)]

        patch_path = tmp_path / 'BarbasPatch.esp'
        stats = build_patch(rows, skyrim_plugin, patch_path)
        assert stats == {'infos_overridden': 1, 'dials_overridden': 1}
        assert patch_path.exists()

        patch = Plugin.load(patch_path)
        assert not patch.is_localized
        assert patch.header.masters == ['Skyrim.esm']

        # Find the INFO override by form_id
        info_overrides = [r for r in patch.records if r.signature == 'INFO']
        assert len(info_overrides) == 1
        info = info_overrides[0]

        # NAM1 should be inline zstring of the new text
        nam1 = info.get_subrecord('NAM1')
        assert nam1 is not None
        assert len(nam1.data) != 4  # not a localized string id
        assert nam1.data.rstrip(b'\x00').decode('cp1252') == new_text

        # SNAM dropped on edited response (Barbas's first response had
        # one in vanilla -- verify it's gone)
        # We can't easily count which TRDT lost its SNAM without
        # walking the response list, but we can confirm at minimum
        # that the dropped count matches expectations: the source
        # info had one SNAM at response 0 and we edited response 0,
        # so the patch should have zero SNAMs.
        source_info = skyrim_plugin.get_record_by_form_id(info.form_id.value)
        source_snams = sum(1 for s in source_info.subrecords if s.signature == 'SNAM')
        patch_snams = sum(1 for s in info.subrecords if s.signature == 'SNAM')
        assert patch_snams == max(0, source_snams - 1)

        # Parent DIAL must also be present and form a valid topic group
        dials = [r for r in patch.records if r.signature == 'DIAL']
        assert len(dials) == 1
        assert dials[0].editor_id == 'DA03BarbasGreeting1A'

        # The DIAL group structure: top "DIAL" GRUP with a type=7
        # subgroup labeled with the parent DIAL form id.
        top_dial_groups = [g for g in patch.groups
                           if g.group_type == 0 and g.label == 'DIAL']
        assert len(top_dial_groups) == 1
        top = top_dial_groups[0]
        # Records should be: DIAL, child-GRUP(7), and child-GRUP holds the INFO
        children = list(top.records)
        assert any(isinstance(c, Record) and c.signature == 'DIAL' for c in children)
        type7 = [c for c in children
                 if isinstance(c, GroupRecord) and c.group_type == 7]
        assert len(type7) == 1
        assert type7[0].label == dials[0].form_id.value
        infos_in_group = [r for r in type7[0].records
                          if isinstance(r, Record) and r.signature == 'INFO']
        assert len(infos_in_group) == 1

    def test_no_edits_produces_no_patch(self, skyrim_plugin, tmp_path):
        rows = [make_row(new_text='')]
        patch_path = tmp_path / 'NoEdits.esp'
        stats = build_patch(rows, skyrim_plugin, patch_path)
        assert stats == {'infos_overridden': 0, 'dials_overridden': 0}
        assert not patch_path.exists()

    def test_multi_response_only_edits_targeted(self, skyrim_plugin, tmp_path):
        """For a 3-response INFO, edit only response 1; responses 0
        and 2 should round-trip with their original text inlined."""
        target_form_id = '[00] 01362F'
        # Original texts of the three responses (from dump_dialog test)
        originals = [
            "I can't believe you did that. You people are monsters!",
            "You demand payment for protection and you can't even protect yourselves.",
            "Here, take your coin and tell Brynjolf to leave us alone.",
        ]
        new_resp1 = "PATCHED LINE."
        rows = [
            {'form_id': target_form_id, 'plugin': 'Skyrim.esm',
             'quest_edid': 'TG01',
             'dial_edid': 'TG01BersiQuestPreBrokenBranchTopic',
             'dial_full': 'That was from Brynjolf. Get the message?',
             'info_edid': '',
             'response_index': str(i),
             'original_text': originals[i],
             'new_text': new_resp1 if i == 1 else '',
             'notes': ''}
            for i in range(3)
        ]

        patch_path = tmp_path / 'Bersi.esp'
        stats = build_patch(rows, skyrim_plugin, patch_path)
        assert stats == {'infos_overridden': 1, 'dials_overridden': 1}

        patch = Plugin.load(patch_path)
        info = next(r for r in patch.records if r.signature == 'INFO')
        nam1s = [s for s in info.subrecords if s.signature == 'NAM1']
        # All three NAM1s must be inline zstrings now
        texts = [s.data.rstrip(b'\x00').decode('cp1252') for s in nam1s]
        assert texts == [originals[0], new_resp1, originals[2]]

    def test_dial_full_only_edit_produces_dial_only_override(
            self, skyrim_plugin, tmp_path):
        """A row that only edits new_dial_full (no new_text) should
        override the parent DIAL with a new FULL but write zero INFO
        overrides. The patch's topic-children group is empty for that
        DIAL."""
        new_full = "I'm in a hurry."
        rows = [make_row(new_dial_full=new_full)]

        patch_path = tmp_path / 'DialOnly.esp'
        stats = build_patch(rows, skyrim_plugin, patch_path)
        assert stats == {'infos_overridden': 0, 'dials_overridden': 1}

        patch = Plugin.load(patch_path)
        dials = [r for r in patch.records if r.signature == 'DIAL']
        assert len(dials) == 1
        assert dials[0].editor_id == 'DA03BarbasGreeting1A'
        full = dials[0].get_subrecord('FULL')
        assert full is not None
        assert full.data.rstrip(b'\x00').decode('cp1252') == new_full
        # No INFO records in the patch
        assert [r for r in patch.records if r.signature == 'INFO'] == []
        # Topic-children group is present but empty
        top = next(g for g in patch.groups
                   if g.group_type == 0 and g.label == 'DIAL')
        type7 = [c for c in top.records
                 if isinstance(c, GroupRecord) and c.group_type == 7]
        assert len(type7) == 1
        assert [r for r in type7[0].records
                if isinstance(r, Record) and r.signature == 'INFO'] == []

    def test_dial_full_and_response_edits_combined(
            self, skyrim_plugin, tmp_path):
        """Editing both the topic line and a response on the same
        INFO produces a single DIAL override with the new FULL plus
        an INFO override with the new NAM1."""
        new_full = "Hey dog."
        new_resp = "Go fetch a stick."
        rows = [make_row(new_dial_full=new_full, new_text=new_resp)]

        patch_path = tmp_path / 'BarbasBoth.esp'
        stats = build_patch(rows, skyrim_plugin, patch_path)
        assert stats == {'infos_overridden': 1, 'dials_overridden': 1}

        patch = Plugin.load(patch_path)
        dial = next(r for r in patch.records if r.signature == 'DIAL')
        info = next(r for r in patch.records if r.signature == 'INFO')

        assert (dial.get_subrecord('FULL').data.rstrip(b'\x00')
                .decode('cp1252') == new_full)
        assert (info.get_subrecord('NAM1').data.rstrip(b'\x00')
                .decode('cp1252') == new_resp)
