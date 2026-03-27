# esplib API Reference

Python library for reading and modifying Bethesda plugin files (.esp, .esm, .esl).

## Quick Start

```python
from esplib import Plugin

# Load a plugin and inspect records
plugin = Plugin("MyMod.esp")
plugin.set_game('tes5') # optional, read from plugin otherwise

for record in plugin.get_records_by_signature('WEAP'):
    print(record.editor_id, record['DATA']['damage'])

# Create a patch plugin
patch = Plugin.new_plugin("Patch.esp", masters=["Skyrim.esm", "MyMod.esp"])
sword = plugin.get_record_by_editor_id("IronSword")
copy = patch.copy_record(sword, plugin)
copy['DATA'] = {'value': 50, 'weight': 10.0, 'damage': 20}
patch.save()
```

---

## Plugin

Main entry point for loading, creating, and saving plugin files.

### Loading

```python
plugin = Plugin("Skyrim.esm")           # Load from file
plugin.set_game('tes5')                  # Bind schemas for typed field access
plugin.auto_detect_game()               # Or auto-detect from header version
```

### Creating

```python
patch = Plugin.new_plugin(
    "MyPatch.esp",
    masters=["Skyrim.esm"],
    version=1.71,
    is_esm=False
)
```

### Record Access

```python
plugin.get_record_by_form_id(0x00012EB7)        # By FormID
plugin.get_record_by_editor_id("IronSword")      # By Editor ID
plugin.get_records_by_signature("WEAP")           # All of a type
len(plugin)                                       # Record count
for record in plugin:                             # Iterate all records
    ...
```

### Record Manipulation

```python
plugin.add_record(record)                         # Add a record
plugin.remove_record(record)                      # Remove a record
copy = plugin.copy_record(record, source_plugin)  # Deep copy (auto-adds masters)
fid = plugin.get_next_form_id()                   # Next available FormID
```

### Master Management

```python
plugin.add_master("Dawnguard.esm")                # Add master dependency
plugin.add_recursive_masters(source_plugin)       # Add plugin + its masters
plugin.header.masters                             # List of master filenames
```

### Saving

```python
plugin.save()                            # Save to original path (creates .bak)
plugin.save_as("NewFile.esp")            # Save to different path
data = plugin.to_bytes()                 # Serialize to bytes without writing
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `header` | `PluginHeader` | Header metadata |
| `records` | `list[Record]` | All records |
| `is_esm` | `bool` | ESM flag |
| `is_esl` | `bool` | ESL flag |
| `is_localized` | `bool` | Uses string tables |
| `modified` | `bool` | Has unsaved changes |

### Validation

```python
issues = plugin.validate()     # Returns list of issue strings (empty = valid)
stats = plugin.get_statistics()  # Dict with header info, record counts, types
```

---

## Record

A main record (WEAP, NPC_, ARMO, etc.) containing subrecords.

### Typed Field Access

With a schema bound (via `plugin.set_game()`), fields are parsed automatically:

```python
weapon = plugin.get_record_by_editor_id("IronSword")

# Read struct fields
data = weapon['DATA']                # {'value': 25, 'weight': 12.0, 'damage': 7}
damage = weapon['DATA']['damage']    # 7

# Write
weapon['DATA'] = {'value': 50, 'weight': 10.0, 'damage': 20}
```

Without a schema, `record[sig]` returns the raw `SubRecord` object.

### Group Access

Records with repeating subrecord groups expose them via `get_group()`:

```python
# HDPT record -- NAM0/NAM1 pairs form "Part" groups
parts = headpart.get_group('Part')     # Live list[GroupInstance]
for part in parts:
    part_type = part.get_subrecord('NAM0')
    filename = part.get_subrecord('NAM1')

# RACE record -- disambiguates duplicate signatures
male_skel = race.get_group('Male Skeletal Model')[0]
male_skel.get_subrecord('ANAM')    # Male skeleton path

female_skel = race.get_group('Female Skeletal Model')[0]
female_skel.get_subrecord('ANAM')  # Female skeleton path

# Manipulate the list directly
parts.append(GroupInstance.new(hdpt_schema_group_def))
del parts[2]
parts[0], parts[1] = parts[1], parts[0]
```

### Subrecord Access

Low-level access to raw subrecords:

```python
record.get_subrecord('EDID')             # First matching SubRecord or None
record.get_subrecords('KWDA')            # All matching SubRecords
record.add_subrecord('DATA', raw_bytes)  # Append new subrecord
record.has_subrecord('VMAD')             # Check existence
'VMAD' in record                         # Same thing
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `signature` | `str` | 4-char type (WEAP, NPC_, etc.) |
| `form_id` | `FormID` | Unique identifier |
| `flags` | `int` | Record flags |
| `editor_id` | `str` | EDID value (get/set) |
| `full_name` | `str` | FULL value (get/set) |
| `is_compressed` | `bool` | Uses zlib compression |
| `modified` | `bool` | Changed since load |

### Copying

`record.copy()` clones the record data without attaching it to any plugin.
The caller decides where the copy goes:

```python
copy = record.copy()              # Free-floating deep copy
copy.form_id = FormID(0x900)      # Change identity if needed
some_plugin.add_record(copy)      # Add it to a plugin
```

For the common case of copying a record into a patch plugin (with automatic
master handling), use `Plugin.copy_record()` instead:

```python
copy = patch.copy_record(sword, skyrim) # Creates an override
# copies to patch, Skyrim.esm added as master automatically
```

---

## SubRecord

A field within a record, identified by a 4-character signature.

```python
sr = record.get_subrecord('DATA')
sr.signature   # 'DATA'
sr.size        # Length in bytes
sr.data        # Raw bytes

# Typed getters
sr.get_uint32()
sr.get_float()
sr.get_string()
sr.get_form_id()

# Typed setters
sr.set_uint32(0, 100)
sr.set_float(0, 3.14)
sr.set_string("NewName")
```

---

## GroupInstance

One instance of a repeating subrecord group (e.g. one Part in an HDPT record).

```python
from esplib import GroupInstance

# Create a new empty instance
inst = GroupInstance.new(group_def)

# Add subrecords
inst.add_subrecord('NAM0', struct.pack('<I', 0))
inst.add_subrecord('NAM1', b'meshes\\path.tri\x00')

# Query
sr = inst.get_subrecord('NAM0')
all_srs = inst.get_subrecords('NAM0')
```

---

## FormID

32-bit record identifier.

```python
from esplib import FormID

fid = FormID(0x00012EB7)
fid.file_index    # 0x00 (top 8 bits -- index into master list)
fid.object_index  # 0x12EB7 (lower 24 bits)
str(fid)          # "[00] 012EB7"

# Parse from string
fid = FormID.from_string("00012EB7")
fid = FormID.from_string("[FE:001] 800")   # ESL format
```

---

## FormList Helpers

Convenience functions for FLST records:

```python
from esplib import flst_forms, flst_contains, flst_add, flst_remove

flst = plugin.get_record_by_editor_id("MyFormList")

forms = flst_forms(flst)              # list[FormID]
flst_contains(flst, 0x00012EB7)       # bool
flst_add(flst, 0x00012EB7)            # Append
flst_remove(flst, 0x00012EB7)         # Remove first match, returns bool
```

---

## Global Variable Helpers

Convenience functions for GLOB records:

```python
from esplib import glob_value, glob_set_value, glob_copy_as

glob = plugin.get_record_by_editor_id("GameHour")

val = glob_value(glob)                # float
glob_set_value(glob, 12.0)            # Set value

# Copy with new identity
new_glob = glob_copy_as(glob, "MyGameHour", 0x800)
```

---

## Multi-Plugin Operations

### LoadOrder

```python
from esplib import LoadOrder

lo = LoadOrder.from_list(["Skyrim.esm", "Update.esm", "MyMod.esp"])
lo.index_of("MyMod.esp")   # 2
```

### PluginSet

Load multiple plugins with override resolution:

```python
from esplib import PluginSet

ps = PluginSet(load_order)
ps.load_all()

# Find which plugin wins for a FormID
chain = ps.get_override_chain(0x00012EB7)
winning_record = chain[-1]

# Iterate all overridden records
for form_id, chain in ps.overridden_records():
    if len(chain) > 1:
        print(f"{form_id:#010x} overridden {len(chain)} times")
```

---

## Game Discovery

```python
from esplib import discover_games, find_game

games = discover_games()         # List[GameInstall]
skyrim = find_game('tes5')       # GameInstall or None
skyrim.data_dir                  # Path to Data/
skyrim.plugins_txt()             # Path to plugins.txt
```

---

## Game IDs

Game IDs are used with `Plugin.new_plugin(game=...)` and `plugin.set_game(...)`.
When loading a plugin with `Plugin(path)`, the game is auto-detected from the
header version.

| Game ID | Game | Header Version | Schemas |
|---------|------|---------------|---------|
| `tes5` | Skyrim (LE and SE) | 0.94 (LE), 1.71 (SE) | Yes |
| `tes5le` | Skyrim LE (alias) | 0.94 | Same as `tes5` |
| `fo4` | Fallout 4 | 0.95 | Not yet |
| `sf1` | Starfield | 0.96 | Not yet |

`tes5le` is an alias for `tes5` — same record definitions, different header
version. Use it with `new_plugin()` to create LE-compatible plugins.

---

## Schema Definitions

Record schemas define the structure of each record type. Currently available
for Skyrim LE/SE (`tes5`):

**Tier 0:** TES4, GMST, GLOB, KYWD, FLST

**Tier 1:** WEAP, ARMO, ALCH, AMMO, BOOK, MISC, LVLI, COBJ, FACT, NPC_, HDPT, ARMA, RACE

Schemas are bound automatically when loading a plugin or creating one with
`new_plugin()`. Use `set_game()` to override if auto-detection fails.

### EspGroup

Schema groups define repeating subrecord structures. Used in RACE (skeletal models, body data, head data, attacks), HDPT (parts), ARMO (male/female models), ARMA (biped/1st person models), ALCH (effects), and others.

---

## Exceptions

| Exception | Base | When |
|-----------|------|------|
| `PluginError` | `Exception` | General plugin error |
| `ParseError` | `PluginError` | Binary parsing failure |
| `ValidationError` | `PluginError` | Invalid data |
| `FormIDError` | `PluginError` | FormID operation error |
