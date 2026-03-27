"""esplib dump -- dump records with typed fields."""

import csv
import json
import sys
from esplib import Plugin, FormID
from esplib.defs.game import GameRegistry


def _detect_or_set_game(plugin, game_arg):
    """Bind schemas from explicit game arg or auto-detect."""
    if game_arg:
        plugin.set_game(game_arg)
    else:
        plugin.auto_detect_game()


def _resolve_record(record):
    """Resolve a record's subrecords into a dict, handling errors gracefully."""
    if record.schema is None:
        # No schema -- return raw subrecord info
        result = {}
        for sr in record.subrecords:
            if sr.signature == 'EDID':
                result['EDID'] = sr.get_string()
            else:
                result[sr.signature] = f"<{sr.size} bytes>"
        return result

    try:
        return record.schema.from_record(record)
    except Exception as e:
        return {'_error': str(e)}


def _flatten_value(value, prefix=''):
    """Flatten nested dicts/lists for CSV output."""
    rows = {}
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
            if isinstance(v, (dict, list)):
                rows.update(_flatten_value(v, key))
            else:
                rows[key] = _format_value(v)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            key = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                rows.update(_flatten_value(v, key))
            else:
                rows[key] = _format_value(v)
    else:
        rows[prefix] = _format_value(value)
    return rows


def _format_value(v):
    """Format a value for display."""
    if isinstance(v, FormID):
        return str(v)
    if isinstance(v, bytes):
        if len(v) <= 16:
            return v.hex()
        return f"<{len(v)} bytes>"
    return v


def _make_serializable(obj):
    """Convert an object to JSON-serializable form."""
    if isinstance(obj, FormID):
        return str(obj)
    if isinstance(obj, bytes):
        if len(obj) <= 64:
            return obj.hex()
        return f"<{len(obj)} bytes>"
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    return obj


def run(args):
    plugin = Plugin(args.plugin)

    # Import game defs
    try:
        import esplib.defs.tes5
    except ImportError:
        pass

    _detect_or_set_game(plugin, args.game)

    # Filter records
    records = list(plugin.records)
    if args.record_type:
        records = [r for r in records if r.signature == args.record_type]
    if args.form_id:
        fid = int(args.form_id, 16)
        records = [r for r in records if r.form_id.value == fid]
    if args.editor_id:
        target = args.editor_id.lower()
        records = [r for r in records if r.editor_id and r.editor_id.lower() == target]
    if args.limit > 0:
        records = records[:args.limit]

    if args.format == 'json':
        output = []
        for record in records:
            entry = {
                'signature': record.signature,
                'form_id': str(record.form_id),
                'editor_id': record.editor_id,
                'fields': _make_serializable(_resolve_record(record)),
            }
            output.append(entry)
        print(json.dumps(output, indent=2))

    elif args.format == 'csv':
        if not records:
            return 0

        # Resolve all records and collect field names
        rows = []
        all_keys = set()
        for record in records:
            resolved = _resolve_record(record)
            flat = _flatten_value(resolved)
            flat['_signature'] = record.signature
            flat['_form_id'] = str(record.form_id)
            flat['_editor_id'] = record.editor_id or ''
            all_keys.update(flat.keys())
            rows.append(flat)

        # Sort columns: meta fields first, then alphabetical
        meta = ['_signature', '_form_id', '_editor_id']
        other = sorted(k for k in all_keys if k not in meta)
        fieldnames = meta + other

        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames,
                                extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v is not None else '' for k, v in row.items()})

    else:  # text
        for record in records:
            edid = record.editor_id or '<no EDID>'
            print(f"--- {record.signature} {record.form_id} {edid} ---")
            resolved = _resolve_record(record)
            _print_dict(resolved, indent=2)
            print()

    return 0


def _print_dict(d, indent=0):
    """Pretty-print a resolved record dict."""
    prefix = ' ' * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                print(f"{prefix}{k}:")
                _print_dict(v, indent + 2)
            elif isinstance(v, list):
                print(f"{prefix}{k}: [{len(v)} items]")
                for i, item in enumerate(v[:5]):
                    if isinstance(item, dict):
                        print(f"{prefix}  [{i}]:")
                        _print_dict(item, indent + 4)
                    else:
                        print(f"{prefix}  [{i}] {_format_value(item)}")
                if len(v) > 5:
                    print(f"{prefix}  ... and {len(v) - 5} more")
            else:
                print(f"{prefix}{k}: {_format_value(v)}")
    else:
        print(f"{prefix}{_format_value(d)}")
