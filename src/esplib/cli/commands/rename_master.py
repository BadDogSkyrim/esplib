"""esplib rename-master -- rename a master dependency in a plugin."""

from esplib import Plugin


def run(args):
    plugin = Plugin(args.plugin)

    old_name = args.old_name
    new_name = args.new_name

    if old_name not in plugin.header.masters:
        print(f"Error: '{old_name}' is not a master of {plugin.file_path.name}")
        print(f"Masters: {plugin.header.masters}")
        return 1

    # Find and rename the MAST subrecord
    header_record = plugin.header._raw_record
    if header_record is None:
        print("Error: no raw TES4 record (plugin was created, not loaded)")
        return 1

    renamed = False
    for sr in header_record.subrecords:
        if sr.signature == 'MAST' and sr.get_string() == old_name:
            sr.set_string(new_name)
            renamed = True
            break

    if not renamed:
        print(f"Error: MAST subrecord for '{old_name}' not found")
        return 1

    # Update the header's master list too
    idx = plugin.header.masters.index(old_name)
    plugin.header.masters[idx] = new_name

    plugin.save()
    print(f"Renamed master: '{old_name}' -> '{new_name}' in {plugin.file_path.name}")
    return 0
