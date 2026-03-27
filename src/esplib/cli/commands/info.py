"""esplib info -- show plugin header and statistics."""

import json
from esplib import Plugin


def run(args):
    plugin = Plugin(args.plugin)
    stats = plugin.get_statistics()

    if args.format == 'json':
        print(json.dumps(stats, indent=2))
    else:
        print(f"File:       {stats['file_path']}")
        print(f"Type:       {stats['file_type']}")
        print(f"Version:    {stats['version']}")
        print(f"Records:    {stats['total_records']}")
        print(f"Groups:     {stats['total_groups']}")
        print(f"Localized:  {stats['is_localized']}")
        if stats['author']:
            print(f"Author:     {stats['author']}")
        if stats['description']:
            print(f"Desc:       {stats['description']}")

        masters = stats['masters']
        if masters:
            print(f"\nMasters ({len(masters)}):")
            for m in masters:
                print(f"  {m}")

        record_types = stats['record_types']
        if record_types:
            print(f"\nRecord types ({len(record_types)}):")
            for sig, count in sorted(record_types.items(), key=lambda x: -x[1]):
                print(f"  {sig}: {count:,}")

    return 0
