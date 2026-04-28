"""Build a patch ESP from an edited dialog dump CSV.

Reads a CSV produced by dump_dialog.py whose rows the user has
edited. Two columns are user-editable:

  new_text       -- replaces a single response line within an INFO.
  new_dial_full  -- replaces the topic line shown to the player
                    (DIAL FULL). All rows belonging to the same
                    DIAL must agree on this value.

For each INFO that has at least one row where `new_text` is non-
empty AND differs from `original_text`, an override is written into
a fresh patch ESP. Other responses on the same INFO keep their
original text in the override (delocalized to inline strings since
the patch is non-localized). For each parent DIAL, an override is
written; if any of its rows set `new_dial_full`, the override gets
the new topic line. A DIAL with only `new_dial_full` set (no INFO
edits) still produces a DIAL-only override with an empty topic-
children group, mirroring xEdit's pattern.

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
    """Reduce CSV rows to per-INFO edit dicts.

    Returns ({info_form_id: {'responses': {idx: text},
                             'new_dial_full': str_or_None}},
             plugin_name).

    Response edits: rows where new_text is non-empty AND different
    from original_text.

    Dial-full edits: rows where new_dial_full is non-empty AND
    different from dial_full. Multiple rows for the same INFO must
    agree on new_dial_full or this raises ValueError.

    Empty entries (no responses + no dial-full edit) are dropped, so
    the returned dict has only INFOs with at least one real edit.
    """
    edits = defaultdict(lambda: {'responses': {}, 'new_dial_full': None})
    plugin_name = None
    for row in rows:
        row_plugin = row['plugin']
        if plugin_name is None:
            plugin_name = row_plugin
        elif plugin_name != row_plugin:
            raise ValueError(
                f"CSV mixes plugins: '{plugin_name}' and '{row_plugin}'. "
                "build_dialog_patch only supports single-plugin CSVs.")

        info_fid = row['form_id']
        entry = edits[info_fid]

        new_text = row['new_text']
        if new_text and new_text != row['original_text']:
            try:
                idx = int(row['response_index'])
                entry['responses'][idx] = new_text
            except (TypeError, ValueError):
                log.warning("skipping row with non-integer response_index: %r",
                            row['response_index'])

        new_dial_full = row.get('new_dial_full', '')
        if new_dial_full and new_dial_full != row['dial_full']:
            existing = entry['new_dial_full']
            if existing is None:
                entry['new_dial_full'] = new_dial_full
            elif existing != new_dial_full:
                raise ValueError(
                    f"Inconsistent new_dial_full for INFO {info_fid}: "
                    f"{existing!r} vs {new_dial_full!r}")

    # Drop INFOs that ended up with neither response edits nor a dial-full edit
    edits = {fid: v for fid, v in edits.items()
             if v['responses'] or v['new_dial_full']}
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


def _set_full_inline(record, text):
    """Replace (or add) the FULL subrecord with an inline zstring."""
    data = text.encode('cp1252', errors='replace') + b'\x00'
    full_sub = record.get_subrecord('FULL')
    if full_sub is not None:
        full_sub.data = data
    else:
        record.add_subrecord('FULL', data)


def build_patch(rows, source_plugin, patch_path):
    """Build a dialog patch ESP at patch_path from the edited rows.

    rows: iterable of dicts using CSV_COLUMNS keys.
    source_plugin: Plugin loaded from disk (the mod we're patching).
    patch_path: Path to write the patch ESP to.

    Returns {'infos_overridden': int, 'dials_overridden': int}.
    No patch file is written if both counts would be zero."""
    rows = list(rows)
    edits, csv_plugin = parse_edits(rows)
    empty = {'infos_overridden': 0, 'dials_overridden': 0}
    if not edits:
        log.info("no edits found in CSV; no patch written")
        return empty

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

    # Group edits by parent DIAL. Each DIAL gets a list of INFOs to
    # override (only those with response edits) plus an optional new
    # FULL that all rows for that DIAL must agree on.
    by_dial = {}  # dial_form_id_value -> {'dial', 'infos', 'new_full'}
    for info_fid_str, edit_data in edits.items():
        if info_fid_str not in info_to_dial:
            log.warning("INFO %s not found in source plugin %s",
                        info_fid_str, source_plugin.file_path.name)
            continue
        dial, info = info_to_dial[info_fid_str]
        key = dial.form_id.value
        if key not in by_dial:
            by_dial[key] = {'dial': dial, 'infos': [], 'new_full': None}
        if edit_data['responses']:
            by_dial[key]['infos'].append((info, edit_data['responses']))

        nd = edit_data['new_dial_full']
        if nd is not None:
            if by_dial[key]['new_full'] is None:
                by_dial[key]['new_full'] = nd
            elif by_dial[key]['new_full'] != nd:
                raise ValueError(
                    f"Inconsistent new_dial_full across INFOs of DIAL "
                    f"{dial.editor_id or hex(key)}: "
                    f"{by_dial[key]['new_full']!r} vs {nd!r}")

    if not by_dial:
        log.info("no source INFOs matched the edits; no patch written")
        return empty

    plugin_name = source_plugin.file_path.name
    patch = Plugin.new_plugin(patch_path, masters=[plugin_name], game='tes5')

    top_dial_grup = GroupRecord(0, 'DIAL')
    patch.groups.append(top_dial_grup)

    info_count = 0
    dial_count = 0
    for dial_fid_value, group in by_dial.items():
        dial_source = group['dial']
        new_dial = _override_record(patch, dial_source)
        if group['new_full'] is not None:
            _set_full_inline(new_dial, group['new_full'])

        top_dial_grup.records.append(new_dial)
        patch.records.append(new_dial)
        patch._form_id_index[new_dial.form_id.value] = new_dial
        if new_dial.editor_id:
            patch._editor_id_index[new_dial.editor_id.lower()] = new_dial
        dial_count += 1

        # Always emit the type=7 child group, even when empty -- xEdit-
        # style patches keep the topic-children container present even
        # for DIAL-only overrides.
        child_grup = GroupRecord(7, new_dial.form_id.value)
        top_dial_grup.records.append(child_grup)

        for info_source, responses in group['infos']:
            new_info = _override_record(patch, info_source)
            _apply_info_edits(new_info, info_source, responses)
            child_grup.records.append(new_info)
            patch.records.append(new_info)
            patch._form_id_index[new_info.form_id.value] = new_info
            info_count += 1

    patch.save()
    log.info("wrote patch with %d INFO + %d DIAL override(s) -> %s",
             info_count, dial_count, patch_path)
    return {'infos_overridden': info_count, 'dials_overridden': dial_count}


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

    stats = build_patch(rows, source, patch_path)
    infos = stats['infos_overridden']
    dials = stats['dials_overridden']
    if infos or dials:
        print(f"Wrote {patch_path} ({infos} INFO override(s), "
              f"{dials} DIAL override(s))")
        return 0
    else:
        print("No edits found in CSV; no patch written.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
