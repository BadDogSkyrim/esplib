"""Build a patch ESP from an edited dialog dump CSV.

Reads a CSV produced by dump_dialog.py whose rows the user has
edited (filling in `new_text` for selected lines). For each INFO
that has at least one row where `new_text` is non-empty AND
differs from `original_text`, an override is written into a fresh
patch ESP. Other responses on the same INFO keep their original
text in the override (delocalized to inline strings since the patch
is non-localized).

When a response is edited, its SNAM (response sound) is dropped --
the engine then falls back to silent generic VO for that line, which
is the standard "I changed the dialog so the recorded VO no longer
matches" pattern.

The patch lists the source plugin as its only master (no transitive
masters from the source's own master list). Patches load AFTER the
source plugin in the load order to override its INFOs.

Usage:
    python build_dialog_patch.py edited.csv [--source PATH] [-o PATCH_PATH]

By default the source plugin path is the directory of the CSV's
`plugin` column entry resolved relative to the Skyrim Data dir; pass
--source to point explicitly. Output goes to
`<source_stem>_DialogPatch.esp` next to the source plugin unless -o
is given.
"""

import argparse
import csv
import logging
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import esplib.defs.tes5  # noqa: F401
from esplib import Plugin, find_game_data, find_strings_dir
from esplib.record import GroupRecord, Record, SubRecord
from esplib.utils import FormID

# Reuse dump_dialog's group walker for DIAL <-> INFO mapping.
sys.path.insert(0, str(Path(__file__).parent))
from dump_dialog import _iter_dial_with_infos, CSV_COLUMNS  # noqa: E402


log = logging.getLogger(__name__)


def parse_edits(rows):
    """Reduce CSV rows to {info_form_id: {response_index: new_text}}.

    Only includes rows where new_text is non-empty AND different from
    original_text. Returns the source plugin filename observed across
    all rows, or raises ValueError if rows reference multiple plugins.
    """
    edits = defaultdict(dict)
    plugin_name = None
    for row in rows:
        row_plugin = row['plugin']
        if plugin_name is None:
            plugin_name = row_plugin
        elif plugin_name != row_plugin:
            raise ValueError(
                f"CSV mixes plugins: '{plugin_name}' and '{row_plugin}'. "
                "build_dialog_patch only supports single-plugin CSVs.")

        new_text = row['new_text']
        if not new_text:
            continue
        if new_text == row['original_text']:
            continue
        try:
            idx = int(row['response_index'])
        except (TypeError, ValueError):
            log.warning("skipping row with non-integer response_index: %r",
                        row['response_index'])
            continue
        edits[row['form_id']][idx] = new_text

    return edits, plugin_name


def _override_record(patch, source_record):
    """Return a patch-mastered override of source_record without
    putting it into a top-level group (we'll place it manually).

    Mirrors copy_record minus the add_record call. Caller is
    responsible for adding the override to patch.records and to the
    correct GroupRecord."""
    new_record = source_record.copy()
    source = source_record.plugin
    new_record.form_id = FormID(
        patch.remap_formid(source_record.form_id.value, source))
    patch._remap_subrecord_formids(new_record, source)
    if not patch.is_localized:
        patch._delocalize_strings(new_record, source, None)
    new_record.plugin = patch
    return new_record


def _delocalize_nam1(sub, source_plugin):
    """If NAM1 is a 4-byte string-table id and the source plugin is
    localized, return the resolved text. Else return the inline
    text (zstring) from the subrecord. Empty string if unresolvable."""
    if len(sub.data) == 4 and source_plugin and source_plugin.is_localized:
        sid = struct.unpack('<I', sub.data)[0]
        return source_plugin.resolve_string(sid) or ''
    # Inline zstring (non-localized format on disk)
    return sub.data.rstrip(b'\x00').decode('cp1252', errors='replace')


def _apply_info_edits(new_info, source_info, edit_map):
    """Rewrite NAM1 subrecords inline (delocalized) and drop SNAMs
    on edited responses.

    edit_map: {response_index: new_text} -- only for edited responses.
    """
    source_plugin = source_info.plugin
    new_subs = []
    response_index = -1
    in_response = False

    for sr in new_info.subrecords:
        if sr.signature == 'TRDT':
            response_index += 1
            in_response = True
            new_subs.append(sr)
        elif sr.signature == 'NAM1' and in_response:
            edited = edit_map.get(response_index)
            if edited is not None:
                text = edited
            else:
                text = _delocalize_nam1(sr, source_plugin)
            data = text.encode('cp1252', errors='replace') + b'\x00'
            new_subs.append(SubRecord('NAM1', data))
        elif (sr.signature == 'SNAM' and in_response
              and edit_map.get(response_index) is not None):
            # Drop SNAM on edited responses -- VO no longer matches.
            continue
        else:
            new_subs.append(sr)

    new_info.subrecords = new_subs


def build_patch(rows, source_plugin, patch_path):
    """Build a dialog patch ESP at patch_path from the edited rows.

    rows: iterable of dicts using CSV_COLUMNS keys.
    source_plugin: Plugin loaded from disk (the mod we're patching).
    patch_path: Path to write the patch ESP to.

    Returns the number of overridden INFO records, or 0 if no edits
    were found in the CSV (no patch is written in that case)."""
    rows = list(rows)
    edits, csv_plugin = parse_edits(rows)
    if not edits:
        log.info("no edits found in CSV; no patch written")
        return 0

    if csv_plugin and source_plugin.file_path \
            and csv_plugin != source_plugin.file_path.name:
        log.warning("CSV says plugin=%s but source loaded is %s",
                    csv_plugin, source_plugin.file_path.name)

    # Build INFO -> (parent DIAL, INFO record) map for the source.
    info_to_dial = {}
    for dial, infos in _iter_dial_with_infos(source_plugin):
        if dial is None:
            continue
        for info in infos:
            info_to_dial[str(info.form_id)] = (dial, info)

    by_dial = defaultdict(list)  # dial.form_id.value -> [(info_record, edit_map)]
    for info_fid_str, edit_map in edits.items():
        if info_fid_str not in info_to_dial:
            log.warning("INFO %s not found in source plugin %s",
                        info_fid_str, source_plugin.file_path.name)
            continue
        dial, info = info_to_dial[info_fid_str]
        by_dial[dial.form_id.value].append((info, edit_map))

    if not by_dial:
        log.info("no source INFOs matched the edits; no patch written")
        return 0

    plugin_name = source_plugin.file_path.name
    patch = Plugin.new_plugin(patch_path, masters=[plugin_name], game='tes5')

    top_dial_grup = GroupRecord(0, 'DIAL')
    patch.groups.append(top_dial_grup)

    overridden = 0
    for dial_fid_value, info_entries in by_dial.items():
        # Override the parent DIAL
        dial_source, _ = info_to_dial[str(info_entries[0][0].form_id)]
        new_dial = _override_record(patch, dial_source)
        top_dial_grup.records.append(new_dial)
        patch.records.append(new_dial)
        patch._form_id_index[new_dial.form_id.value] = new_dial
        if new_dial.editor_id:
            patch._editor_id_index[new_dial.editor_id.lower()] = new_dial

        # Topic Children group (group_type=7, label=parent DIAL form_id)
        child_grup = GroupRecord(7, new_dial.form_id.value)
        top_dial_grup.records.append(child_grup)

        for info_source, edit_map in info_entries:
            new_info = _override_record(patch, info_source)
            _apply_info_edits(new_info, info_source, edit_map)
            child_grup.records.append(new_info)
            patch.records.append(new_info)
            patch._form_id_index[new_info.form_id.value] = new_info
            overridden += 1

    patch.save()
    log.info("wrote patch with %d INFO override(s) -> %s",
             overridden, patch_path)
    return overridden


def _resolve_source_path(csv_path, csv_plugin, explicit):
    if explicit:
        return Path(explicit)
    # Default: <data_dir>/<csv_plugin>
    data_dir = find_game_data('tes5')
    if data_dir is None:
        raise FileNotFoundError(
            "could not locate Skyrim Data directory; pass --source")
    return data_dir / csv_plugin


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n', 1)[0])
    parser.add_argument('csv', help='edited dialog CSV (from dump_dialog.py)')
    parser.add_argument('--source', help='path to the source plugin '
                                         '(default: lookup by CSV plugin column '
                                         'in the Skyrim Data dir)')
    parser.add_argument('-o', '--output', help='output patch path '
                                               '(default: <source>_DialogPatch.esp)')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(levelname)s %(message)s')

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or set(CSV_COLUMNS) - set(reader.fieldnames):
            print(f"Error: CSV missing expected columns. Got "
                  f"{reader.fieldnames}, need {CSV_COLUMNS}", file=sys.stderr)
            return 1
        rows = list(reader)

    if not rows:
        print("Error: CSV is empty", file=sys.stderr)
        return 1

    csv_plugin = rows[0]['plugin']
    source_path = _resolve_source_path(csv_path, csv_plugin, args.source)
    if not source_path.exists():
        print(f"Error: source plugin not found: {source_path}", file=sys.stderr)
        return 1

    source = Plugin()
    strings_dir = find_strings_dir()
    if strings_dir:
        source.string_search_dirs = [str(strings_dir)]
    source._load(source_path)

    if args.output:
        patch_path = Path(args.output)
    else:
        patch_path = source_path.parent / f"{source_path.stem}_DialogPatch.esp"

    overridden = build_patch(rows, source, patch_path)
    if overridden:
        print(f"Wrote {patch_path} ({overridden} INFO overrides)")
        return 0
    else:
        print("No edits found in CSV; no patch written.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
