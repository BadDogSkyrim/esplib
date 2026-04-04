"""Dump record fields from a plugin into CSV.

Form ID and Editor ID are always included. Specify additional subrecord
signatures to dump as positional arguments.

Usage:
    python dump_records.py <plugin_path> <record_type> <SIG> [SIG ...] [-o output.csv]

Examples:
    python dump_records.py Skyrim.esm RACE WNAM RNAM
    python dump_records.py Skyrim.esm ARMO FULL DNAM -o armors.csv
    python dump_records.py Dawnguard.esm NPC_ FULL WNAM -o npcs.csv
"""

import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from esplib import Plugin
from esplib.utils import FormID


def format_parsed(value):
    """Format a schema-parsed value as a string."""
    if isinstance(value, FormID):
        return str(value)
    if isinstance(value, float):
        return f'{value:g}'
    if isinstance(value, dict):
        return '; '.join(f'{k}={format_parsed(v)}' for k, v in value.items())
    if isinstance(value, list):
        return '; '.join(format_parsed(v) for v in value)
    return str(value)


def format_raw(subrecord):
    """Format a subrecord's raw bytes using heuristics."""
    data = subrecord.data
    if data is None or len(data) == 0:
        return ''

    # 2 bytes: uint16
    if len(data) == 2:
        return str(struct.unpack('<H', data)[0])

    # 4 bytes: FormID (most common case in record references)
    if len(data) == 4:
        return str(subrecord.get_form_id())

    # Null-terminated string: printable ASCII/CP1252 ending with \x00
    if data[-1:] == b'\x00' and len(data) > 1:
        try:
            text = data[:-1].decode('cp1252')
            if all(c.isprintable() or c in '\r\n\t' for c in text):
                return text
        except (UnicodeDecodeError, ValueError):
            pass

    # Anything else: hex dump
    return data.hex(' ')


def format_value(subrecord, member_def=None):
    """Format a subrecord for display, using schema if available."""
    if member_def is not None:
        try:
            return format_parsed(member_def.from_subrecord(subrecord))
        except Exception:
            pass
    return format_raw(subrecord)


def dump_records(plugin_path, record_type, signatures, out=None):
    if out is None:
        out = sys.stdout

    p = Plugin()
    p.load(plugin_path)

    records = p.get_records_by_signature(record_type)
    if not records:
        print(f"No {record_type} records found in {plugin_path}", file=sys.stderr)
        return

    # Look up schema definitions for requested signatures
    schema = records[0].schema
    member_defs = {}
    if schema:
        for sig in signatures:
            member_defs[sig] = schema.get_member(sig)

    header = ['FormID', 'EditorID'] + signatures
    writer = csv.writer(out)
    writer.writerow(header)

    for record in records:
        row = [str(record.form_id), record.editor_id or '']

        for sig in signatures:
            member_def = member_defs.get(sig)
            subs = record.get_subrecords(sig)
            if not subs:
                row.append('')
            elif len(subs) == 1:
                row.append(format_value(subs[0], member_def))
            else:
                row.append('; '.join(
                    format_value(s, member_def) for s in subs))

        writer.writerow(row)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__.strip())
        sys.exit(1)

    args = sys.argv[1:]
    plugin_path = args[0]

    output_file = None
    if '-o' in args:
        idx = args.index('-o')
        if idx + 1 < len(args):
            output_file = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("Error: -o requires a filename", file=sys.stderr)
            sys.exit(1)

    record_type = args[1].upper()
    signatures = [s.upper() for s in args[2:]]
    if not signatures:
        print("Error: specify at least one subrecord signature", file=sys.stderr)
        sys.exit(1)

    if not Path(plugin_path).exists():
        print(f"Error: file not found: {plugin_path}", file=sys.stderr)
        sys.exit(1)

    try:
        if output_file:
            with open(output_file, 'w', newline='') as f:
                dump_records(plugin_path, record_type, signatures, out=f)
            print(f"Written to {output_file}")
        else:
            dump_records(plugin_path, record_type, signatures)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
