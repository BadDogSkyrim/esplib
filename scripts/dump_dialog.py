"""Dump dialog from a single plugin into CSV for review or editing.

Walks every DIAL in the plugin, then walks each DIAL's child INFO
group, then walks each INFO's response list. Each response becomes
one CSV row.

Columns:
    form_id          INFO record form id (e.g. "[INFO:0001362f]")
    plugin           source plugin filename
    quest_edid       EditorID of the DIAL's QNAM quest, if resolvable
    dial_edid        EditorID of the parent DIAL
    dial_full        DIAL FULL text (the topic line the player sees)
    info_edid        EditorID of the INFO record (often blank)
    response_index   0-based index of this response within the INFO
    original_text    the response's NAM1 text (resolved if localized)
    new_text         left blank for editing — if filled in by the
                     user and run through build_dialog_patch.py, this
                     replaces original_text in the patch
    notes            blank by default; for user annotation

Pair with build_dialog_patch.py: dump → edit `new_text` in the CSV →
build_dialog_patch reads the edited CSV and emits a patch ESP.

Usage:
    python dump_dialog.py <plugin_path> [-o output.csv] [--masters dir]

If the plugin has masters that contain QNAM targets, point --masters
at the Data directory so quest EditorIDs can resolve. Without it,
quest_edid is left blank for cross-plugin references.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import esplib.defs.tes5  # noqa: F401 -- registers DIAL/INFO schemas
from esplib import Plugin, LoadOrder, PluginSet, find_strings_dir
from esplib.defs import tes5
from esplib.record import Record, GroupRecord


CSV_COLUMNS = [
    'form_id', 'plugin', 'quest_edid', 'dial_edid', 'dial_full',
    'new_dial_full',
    'info_edid', 'response_index', 'original_text', 'new_text', 'notes',
]


def _resolve_string(plugin, value):
    """Return text for either a string-table id (int) or inline text."""
    if isinstance(value, int):
        return plugin.resolve_string(value) or ''
    if isinstance(value, str):
        return value
    return ''


def _iter_dial_with_infos(plugin):
    """Yield (dial_record, [info_records]) pairs in plugin order.

    DIAL top group lays out as: DIAL, child-GRUP(INFOs), DIAL,
    child-GRUP(INFOs), ... The child group's group_type is 7 and its
    label is the parent DIAL's form_id."""
    for group in plugin.groups:
        if not (group.group_type == 0 and group.label == 'DIAL'):
            continue
        last_dial = None
        for item in group.records:
            if isinstance(item, Record) and item.signature == 'DIAL':
                if last_dial is not None:
                    yield last_dial, []
                last_dial = item
            elif isinstance(item, GroupRecord) and item.group_type == 7:
                infos = [r for r in item.records
                         if isinstance(r, Record) and r.signature == 'INFO']
                yield last_dial, infos
                last_dial = None
        if last_dial is not None:
            yield last_dial, []


def _iter_responses(info):
    """Yield (response_index, nam1_value, snam_present) per response.

    Walks subrecords linearly: each TRDT marks a new response, the
    NAM1 that follows (before the next TRDT) is its text. nam1_value
    is whatever NAM1 stores (uint32 string id in localized plugins,
    str in inline plugins). Yields nothing if the INFO has no
    responses."""
    response_index = -1
    nam1 = None
    snam = False
    started = False
    for sub in info.subrecords:
        if sub.signature == 'TRDT':
            if started:
                yield response_index, nam1, snam
            response_index += 1
            nam1 = None
            snam = False
            started = True
        elif sub.signature == 'NAM1' and started and nam1 is None:
            # 4-byte payload = uint32 string-table id (localized
            # plugin); anything else = inline zstring (non-localized).
            if len(sub.data) == 4:
                import struct
                nam1 = struct.unpack('<I', sub.data)[0]
            else:
                nam1 = sub.data.rstrip(b'\x00').decode(
                    'cp1252', errors='replace')
        elif sub.signature == 'SNAM' and started:
            snam = True
    if started:
        yield response_index, nam1, snam


def iter_dialog_rows(plugin, plugin_set=None):
    """Yield one CSV row dict per (DIAL, INFO, response) triple."""
    plugin_name = plugin.file_path.name if plugin.file_path else '?'
    for dial, infos in _iter_dial_with_infos(plugin):
        if dial is None:
            continue
        dial.bind_schema(tes5.DIAL)
        dial_edid = dial.editor_id or ''
        dial_full = _resolve_string(plugin, dial['FULL']) if dial.get_subrecord('FULL') else ''
        quest_edid = ''
        qnam_sub = dial.get_subrecord('QNAM')
        if qnam_sub is not None:
            qfid = qnam_sub.get_form_id()
            if plugin_set is not None:
                qrec = plugin_set.resolve_form_id(qfid, dial.plugin)
                if qrec and qrec.editor_id:
                    quest_edid = qrec.editor_id
            else:
                # Single-plugin lookup: only resolves if QNAM points
                # into this plugin's own form-id space.
                qrec = plugin.get_record_by_form_id(qfid)
                if qrec and qrec.editor_id:
                    quest_edid = qrec.editor_id
        for info in infos:
            info.bind_schema(tes5.INFO)
            info_edid = info.editor_id or ''
            for response_index, nam1, _snam in _iter_responses(info):
                original_text = _resolve_string(plugin, nam1)
                yield {
                    'form_id': str(info.form_id),
                    'plugin': plugin_name,
                    'quest_edid': quest_edid,
                    'dial_edid': dial_edid,
                    'dial_full': dial_full,
                    'new_dial_full': '',
                    'info_edid': info_edid,
                    'response_index': response_index,
                    'original_text': original_text,
                    'new_text': '',
                    'notes': '',
                }


def write_csv(rows, out):
    """Write rows (dicts using CSV_COLUMNS keys) to a file-like object."""
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)


def _build_plugin_set(plugin_path, data_dir=None):
    """Load plugin via PluginSet so QNAMs resolve across masters.

    The target plugin can live anywhere on disk (e.g. inside a Vortex
    or MO2 mod folder, outside the deployed Data directory). Masters
    are loaded from data_dir; the target plugin is loaded directly
    from its given path and injected into the set so override
    resolution finds it. If data_dir is None, falls back to the
    plugin's own directory."""
    plugin_path = Path(plugin_path)
    if data_dir is None:
        data_dir = plugin_path.parent
    else:
        data_dir = Path(data_dir)

    strings_dir = find_strings_dir()

    # Load the target plugin directly from its actual path -- it may
    # not be in data_dir (e.g. a Vortex mod folder).
    target = Plugin()
    if strings_dir:
        target.string_search_dirs = [str(strings_dir)]
    target._load(plugin_path)

    masters = list(target.header.masters)
    plugin_name = plugin_path.name

    # Masters that aren't in data_dir won't contribute to QNAM
    # resolution -- quest_edid will be blank for quests defined in
    # those plugins. Warn but don't fail; this is mild for a dump.
    missing = [m for m in masters if not (data_dir / m).exists()]
    if missing:
        print(f"Warning: masters not found under {data_dir}: {missing}\n"
              f"  quest_edid will be blank for quests defined in those "
              f"plugins.\n  Use --no-resolve to skip cross-plugin "
              f"resolution entirely.", file=sys.stderr)
        masters = [m for m in masters if m not in missing]

    lo = LoadOrder.from_list(masters + [plugin_name],
                             data_dir=data_dir, game_id='tes5')
    ps = PluginSet(lo)
    if strings_dir:
        ps.string_search_dirs = [str(strings_dir)]
    ps.load_all()

    # Inject the target plugin so resolution works even when the file
    # lives outside data_dir.
    ps._plugins[plugin_name] = target
    ps._loaded_full[plugin_name] = True
    target.plugin_set = ps
    ps._override_index = None

    return ps, target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n', 1)[0])
    parser.add_argument('plugin', help='path to plugin file (.esp/.esm)')
    parser.add_argument('-o', '--output', help='output CSV path (default: stdout)')
    parser.add_argument('--masters', help='Data directory for resolving masters '
                                          '(default: plugin\'s own directory)')
    parser.add_argument('--no-resolve', action='store_true',
                        help='skip PluginSet load — quest_edid will be blank '
                             'for cross-plugin references but startup is faster')
    args = parser.parse_args(argv)

    plugin_path = Path(args.plugin)
    if not plugin_path.exists():
        print(f"Error: plugin not found: {plugin_path}", file=sys.stderr)
        return 1

    if args.no_resolve:
        plugin_set = None
        plugin = Plugin.load(plugin_path)
    else:
        plugin_set, plugin = _build_plugin_set(plugin_path, args.masters)

    rows = iter_dialog_rows(plugin, plugin_set)

    if args.output:
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            write_csv(rows, f)
        print(f"Wrote dialog dump to {args.output}", file=sys.stderr)
    else:
        write_csv(rows, sys.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main())
