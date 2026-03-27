# esplib

Python library for reading and modifying Bethesda plugin files (.esp, .esm, .esl).

Built as a Python alternative to xEdit scripting for automating plugin operations
like the [Furrifier](https://www.nexusmods.com/skyrimspecialedition/mods/35138)
mod conversion suite.

## Features

- Load, inspect, modify, and save Bethesda plugin files
- Byte-perfect round-trip (including compressed records)
- Schema-aware typed field access for Skyrim LE/SE record types
- Repeating subrecord groups as first-class data structures
- Record copy and patch file creation with automatic master management
- Multi-plugin load order with override resolution
- FormList and Global Variable helpers
- CLI tools for plugin inspection and comparison
- Game auto-detection from header version

## Quick Start

```python
from esplib import Plugin

# Load and inspect
plugin = Plugin("MyMod.esp")
for weapon in plugin.get_records_by_signature('WEAP'):
    print(weapon.editor_id, weapon['DATA']['damage'])

# Create a patch
patch = Plugin.new_plugin("Patch.esp", masters=["Skyrim.esm"])
sword = plugin.get_record_by_editor_id("IronSword")
override = patch.copy_record(sword, plugin)
override['DATA'] = {'value': 50, 'weight': 10.0, 'damage': 99}
patch.save()
```

## Installation

```bash
pip install -e .
```

Requires Python 3.10+. No external dependencies.

## CLI

```bash
esplib info Skyrim.esm                          # Plugin header and statistics
esplib dump MyMod.esp --type WEAP --limit 10    # Dump weapon records
esplib diff Original.esp Modified.esp           # Compare two plugins
esplib validate MyMod.esp                       # Check for structural issues
esplib rename-master MyMod.esp Old.esm New.esm  # Rename a master dependency
```

## Supported Games

| Game ID | Game | Schemas |
|---------|------|---------|
| `tes5` | Skyrim (LE and SE) | Yes |
| `fo4` | Fallout 4 | Planned |

## Documentation

- [API Reference](doc/api.md)
- [CLI Reference](doc/cli.md)

## Tests

```bash
pip install -e .
pytest tests/ -m "not gamefiles"    # Synthetic tests (no game files needed)
pytest tests/                        # All tests (requires Skyrim SE installed)
```

197 automated tests covering record parsing, round-trip fidelity, schema
resolution, CLI commands, and helpers.

## License

MPL 2.0
