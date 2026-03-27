"""esplib diff -- differences between two plugins."""

import json
from esplib import Plugin
from esplib.defs.game import GameRegistry


def run(args):
    p1 = Plugin(args.plugin1)
    p2 = Plugin(args.plugin2)

    # Build FormID -> record maps
    index1 = {r.form_id.value: r for r in p1.records}
    index2 = {r.form_id.value: r for r in p2.records}

    all_fids = sorted(set(index1.keys()) | set(index2.keys()))

    added = []    # in p2 but not p1
    removed = []  # in p1 but not p2
    changed = []  # in both but different
    identical = 0

    for fid in all_fids:
        r1 = index1.get(fid)
        r2 = index2.get(fid)

        if r1 is None:
            added.append((fid, r2))
        elif r2 is None:
            removed.append((fid, r1))
        else:
            # Compare raw subrecord bytes
            bytes1 = r1._serialize_subrecords()
            bytes2 = r2._serialize_subrecords()
            if bytes1 != bytes2:
                changed.append((fid, r1, r2))
            else:
                identical += 1

    if args.format == 'json':
        output = {
            'plugin1': str(p1.file_path),
            'plugin2': str(p2.file_path),
            'added': len(added),
            'removed': len(removed),
            'changed': len(changed),
            'identical': identical,
            'details': {
                'added': [{'form_id': f'0x{fid:08X}',
                           'signature': r.signature,
                           'editor_id': r.editor_id}
                          for fid, r in added[:100]],
                'removed': [{'form_id': f'0x{fid:08X}',
                             'signature': r.signature,
                             'editor_id': r.editor_id}
                            for fid, r in removed[:100]],
                'changed': [{'form_id': f'0x{fid:08X}',
                             'signature': r1.signature,
                             'editor_id': r1.editor_id or r2.editor_id}
                            for fid, r1, r2 in changed[:100]],
            }
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Comparing: {p1.file_path}")
        print(f"     with: {p2.file_path}")
        print()
        print(f"Added:     {len(added)}")
        print(f"Removed:   {len(removed)}")
        print(f"Changed:   {len(changed)}")
        print(f"Identical: {identical}")

        if added:
            print(f"\n--- Added ({len(added)}) ---")
            for fid, r in added[:20]:
                edid = r.editor_id or ''
                print(f"  + {r.signature} 0x{fid:08X} {edid}")
            if len(added) > 20:
                print(f"  ... and {len(added) - 20} more")

        if removed:
            print(f"\n--- Removed ({len(removed)}) ---")
            for fid, r in removed[:20]:
                edid = r.editor_id or ''
                print(f"  - {r.signature} 0x{fid:08X} {edid}")
            if len(removed) > 20:
                print(f"  ... and {len(removed) - 20} more")

        if changed:
            print(f"\n--- Changed ({len(changed)}) ---")
            for fid, r1, r2 in changed[:20]:
                edid = r1.editor_id or r2.editor_id or ''
                print(f"  ~ {r1.signature} 0x{fid:08X} {edid}")

                if args.field_level and r1.schema:
                    _print_field_diff(r1, r2)

            if len(changed) > 20:
                print(f"  ... and {len(changed) - 20} more")

    return 0


def _print_field_diff(r1, r2):
    """Print field-level differences between two records."""
    try:
        fields1 = r1.schema.from_record(r1)
        fields2 = r2.schema.from_record(r2)
    except Exception:
        return

    for key in set(fields1.keys()) | set(fields2.keys()):
        v1 = fields1.get(key)
        v2 = fields2.get(key)
        if v1 != v2:
            print(f"      {key}: {v1} -> {v2}")
