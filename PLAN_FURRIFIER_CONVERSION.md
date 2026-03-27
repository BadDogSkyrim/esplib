# Plan: Convert BDFurrySkyrim_Furrifier to esplib

## Context

The BDFurrySkyrim_Furrifier is a ~7500-line xEdit Pascal script suite that
batch-modifies Skyrim NPCs to use furry races. It modifies RACE, NPC_, ARMO,
ARMA, HDPT, FLST, and GLOB records, creating a patch file with overrides.

This plan converts it to a standalone Python application using esplib. The goal
is functional equivalence -- same patch output, no xEdit dependency. The result
should be packable into a distributable exe (via PyInstaller or similar).

**Prerequisite:** PLAN_ESPLIB_EXTENSION phases A-C must be complete.

---

## Design Decisions

### CLI-first, optional UI
- If all required parameters are provided on the command line, it runs headless.
- If parameters are missing, it can pop up a simple UI (tkinter -- stdlib, no
  extra dependencies, bundles into exe easily).
- Use `argparse` for CLI. UI is a future enhancement, not blocking.

### Hash function
Use Python's built-in `hash()` for deterministic pseudo-random selection (same
NPC always gets same headpart). No need for backward compatibility with the
Pascal hash -- NPC assignments will differ from old patches but that's fine.

### Exe packaging
- No dependencies outside stdlib + esplib.
- No dynamic imports, `__import__()`, or `importlib` tricks.
- No reading from `__file__`-relative paths at runtime (use `importlib.resources`
  or bundle data as Python modules).
- tkinter is fine (ships with Python, works with PyInstaller).
- Test with PyInstaller early (Phase 8) to catch packaging issues.

### Preferences / configuration
- Current approach: users edit Pascal preference files to set race assignments.
- Python equivalent: preferences defined as Python data in `.py` files that
  users can edit. This is the most natural for the existing user base and
  requires no config parser. Example:
  ```python
  # preferences_allraces.py
  RACE_ASSIGNMENTS = {
      'NordRace': 'BDWolfRace',
      'ImperialRace': 'BDLionRace',
      ...
  }
  ```
- Future: consider TOML or YAML config files as an alternative, but Python
  modules are simplest for now and non-coders can read/edit them.

### Logging
- Use Python's `logging` module with configurable levels.
- Default: `WARNING` for normal use, `INFO` for progress, `DEBUG` for
  troubleshooting.
- Ship a `--debug` CLI flag that sets `DEBUG` and writes to a log file.
- Users reporting bugs can run with `--debug` and send the log file.
- Consider: `--debug` could also dump the furrifier's internal state
  (race assignments, headpart mappings) to a JSON file for inspection.

### Data structures
The Pascal code uses `TStringList` as maps, nested `TStringList.Objects[]` for
multi-level lookups, and integer arrays indexed by constants. This is because
Pascal has no dict type. In Python we use a `RaceInfo` object that holds the
race record and all its pre-indexed data, eliminating multi-level dict lookups:

```python
class HeadpartType(Enum):
    HAIR = 0
    SCAR = 1
    EYES = 2
    EYEBROWS = 3
    FACIAL_HAIR = 4

class Sex(Enum):
    MALE = 0
    FEMALE = 1
    MALE_CHILD = 2
    FEMALE_CHILD = 3

@dataclass
class RaceInfo:
    """All pre-indexed data about a race."""
    record: Record                  # The race record itself
    editor_id: str
    is_child: bool
    # Headparts indexed by sex and type
    # e.g. race_info.headparts[Sex.MALE][HeadpartType.HAIR] -> list[Record]
    headparts: dict[Sex, dict[HeadpartType, list[Record]]]
    # Tint assets indexed by sex
    # e.g. race_info.tints[Sex.MALE] -> list[TintAsset]
    tints: dict[Sex, list[TintAsset]]

@dataclass
class RaceAssignment:
    vanilla: RaceInfo               # The vanilla race (e.g. NordRace)
    furry: RaceInfo                  # The furry race (e.g. BDWolfRace)
    labels: list[str]

# Top-level lookup: races['NordRace'].headparts[Sex.MALE][HeadpartType.HAIR]
races: dict[str, RaceInfo]          # All known races, keyed by EditorID
assignments: dict[str, RaceAssignment]  # Vanilla EditorID -> assignment
faction_races: dict[str, str]       # Faction EditorID -> race EditorID
```

This replaces the Pascal pattern of `raceHeadparts[HP_HAIR, SEX_MALE].IndexOf('LykaiosRace')`
with `races['LykaiosRace'].headparts[Sex.MALE][HeadpartType.HAIR]` -- direct
attribute access on a typed object instead of nested list searches.

### Record lookup performance
`plugin.get_record_by_editor_id()` searches the EditorID index (dict lookup,
O(1)). It does not need a group signature parameter -- the index covers all
records. If profiling shows this is a bottleneck (unlikely given dict lookup),
we can add `get_record_by_editor_id(id, signature=None)` to optionally filter,
but don't optimize prematurely.

### PluginSet access by index
Add `PluginSet.__getitem__` for index-based access:
```python
plugin_set[0]                    # First plugin in load order
plugin_set['Skyrim.esm']         # By name
```

---

## Module Structure

```
furrifier/
    __init__.py
    main.py              -- entry point: CLI + optional UI
    config.py            -- settings dataclass, CLI arg parsing
    race_defs.py         -- race definitions (furry races, faction races)
    preferences/         -- race preference schemes
        __init__.py
        all_races.py
        cats_dogs.py
        legacy.py
        user.py
    setup.py             -- load vanilla data from plugins into data structures
    models.py            -- RaceAssignment, TintAsset, HeadpartInfo dataclasses
    headparts.py         -- headpart loading, label matching, selection
    tints.py             -- tint layer logic
    npc.py               -- NPC furrification (race, headparts, tints)
    armor.py             -- armor addon modification
    schlongs.py          -- SOS compatibility (FLST/GLOB manipulation)
    tests/
        __init__.py
        test_hash.py
        test_labels.py
        test_npc.py
        test_armor.py
        test_integration.py  -- full run comparison against xEdit output
```

---

## Conversion Phases

### Phase 1: Infrastructure & Models

**Convert:**
- Hash functions from `BDScriptTools.pas` -> port verbatim for compatibility
- Color helpers (RedPart, GreenPart, BluePart)
- `models.py` -- dataclasses for RaceAssignment, HeadpartInfo, TintAsset, etc.
- `config.py` -- settings dataclass + argparse CLI

**Key translations:**
| xEdit Pascal | esplib Python |
|---|---|
| `TStringList` as dict | `dict[str, Any]` |
| `TStringList.Objects[]` | Typed dataclasses |
| `FindFile(name)` | `load_order.plugin_path(name)` |
| `FileByIndex(i)` | `plugin_set[i]` |
| `AddMessage(s)` | `logging.info(s)` |
| `Hash(alias, seed, count)` | Verbatim port (compatibility) |

**Tests:**
- Hash-based selection is deterministic (same input -> same output across runs)
- Config dataclass serializes/deserializes correctly

### Phase 2: Race Definitions & Preferences

**Convert:**
- `BDFurrySkyrimRaceDefs.pas` -> `race_defs.py`
- `BDFurrySkyrimUserRaceDefs.pas` -> merged into `race_defs.py`
- `BDFurrySkyrim_Preferences_*.pas` -> `preferences/*.py`

**Data structures use `RaceInfo` objects (see Design Decisions above):**
```python
# Build RaceInfo for each vanilla and furry race
races['NordRace'] = RaceInfo(record=nord_record, ...)
races['BDWolfRace'] = RaceInfo(record=wolf_record, ...)

# Race assignments link them
assignments['NordRace'] = RaceAssignment(
    vanilla=races['NordRace'],
    furry=races['BDWolfRace'],
    labels=['MILITARY', 'MESSY'],
)
```

**Tests:**
- Race assignment loading produces correct mappings
- Each preference scheme assigns expected races

### Phase 3: Setup & Data Loading

**Convert:**
- `BDFurrySkyrimSetup.pas` -> `setup.py`
- Loads vanilla races, headparts, tint data from plugins using esplib

**esplib access patterns:**
```python
# Find a race record
nord = plugin_set.get_plugin('Skyrim.esm').get_record_by_editor_id('NordRace')

# Read nested fields
is_child = nord['DATA']['Child'] if nord.schema else False

# Iterate all headparts
for hdpt in plugin.get_records_by_signature('HDPT'):
    hp_type = hdpt['PNAM']  # headpart type enum
```

**Tests:**
- Setup loads expected number of vanilla races
- Headpart lists built correctly for NordRace male/female

### Phase 4: Headpart & Tint Logic

**Convert:**
- `BDFurrySkyrimTools.pas` headpart functions -> `headparts.py`
- `BDFurrySkyrimTools.pas` tint functions -> `tints.py`
- Label scoring algorithm (pure logic, ports directly)
- Hash-based deterministic selection

**Tests (port from `BDFurrySkyrimTEST.pas`):**
- Label conflict detection (MILITARY vs MESSY, SHORT vs LONG, etc.)
- Label scoring produces expected scores for known NPC/headpart combinations
- Hash-based selection is deterministic (same input -> same output)
- Tint layer count per type matches expected values

### Phase 5: NPC Furrification

**Convert:**
- `FurrifyNPC()` -> `npc.py`
- Race determination (faction-based, override-based, vanilla)
- Headpart replacement
- Tint layer application

**Core flow:**
```python
def furrify_npc(npc: Record, patch: Plugin, ctx: FurrifyContext):
    assignment = determine_npc_race(npc, ctx)
    patched = patch.copy_record(npc, source_plugin)
    patched['RNAM'] = assignment.furry.record.form_id

    new_headparts = choose_headparts(npc, assignment, ctx)
    patched['Head Parts'] = new_headparts

    tint_layers = choose_tints(npc, assignment, ctx)
    patched['Tint Layers'] = tint_layers
```

**Tests:**
- Furrify a known NPC, verify race/headpart/tint assignments match xEdit output
- Gender detection works correctly
- Faction-based race override works

### Phase 6: Race & Armor Furrification

**Convert:**
- `FurrifyRace()` and `FurrifyAllRaces()`
- `BDArmorFixup.pas` + `BDFurryArmorFixup.pas` -> `armor.py`

**Tests:**
- Race furrification copies correct subrecords (RNAM, NAM8, WNAM, Head Data)
- Armor addon adds furrified races to Additional Races
- Bodypart flag detection (BP_HAIR, BP_LONGHAIR, BP_HANDS) works

### Phase 7: SOS Compatibility

**Convert:**
- `BDFurrifySchlongs.pas` -> `schlongs.py`
- FLST manipulation (add/remove furry races from schlong race lists)
- GLOB copying for probability/size values

**Tests:**
- Schlong list modification adds correct races
- GLOB copy produces valid records

### Phase 8: Entry Point, CLI & Packaging

**`main.py`:**
```python
def main():
    args = parse_args()  # --config, --scheme, --patch-file, --debug, etc.

    if not args_complete(args):
        # Future: pop up tkinter UI to fill in missing options
        print("Missing required arguments. Use --help for options.")
        return 1

    # Load plugins
    load_order = LoadOrder.from_game('tes5')
    plugin_set = PluginSet(load_order)
    plugin_set.load_all()

    # Create patch
    patch = Plugin.new_plugin(args.patch_filename, masters=[...])

    # Run
    ctx = FurrifyContext(args, plugin_set)
    ctx.setup()
    ctx.furrify_all_races(patch)
    ctx.furrify_all_npcs(patch)
    if args.furrify_armor:
        ctx.furrify_all_armors(patch)
    if args.furrify_schlongs:
        ctx.furrify_all_schlongs(patch)

    patch.save()
```

**Packaging:**
- Test with PyInstaller: `pyinstaller --onefile main.py`
- Verify exe runs on a clean Windows install (no Python required)
- Include preference .py files as data files in the bundle

**Tests:**
- CLI `--help` works
- CLI with all args runs headless
- PyInstaller produces working exe

---

## xEdit API -> esplib Translation Table

| xEdit Pascal | esplib Python |
|---|---|
| `GroupBySignature(f, 'NPC_')` | `plugin.get_records_by_signature('NPC_')` |
| `MainRecordByEditorID(g, id)` | `plugin.get_record_by_editor_id(id)` |
| `GetElementEditValues(r, path)` | `record['SIG']['field']` (chained access) |
| `SetElementEditValues(r, path, v)` | `record['SIG'] = value` |
| `ElementExists(r, path)` | `'SIG' in record` |
| `LinksTo(element)` | `plugin_set.resolve_form_id(fid, plugin)` |
| `WinningOverride(record)` | `plugin_set.get_override_chain(fid)[-1]` |
| `wbCopyElementToFile(r, f, a, b)` | `plugin.copy_record(record, source)` |
| `AddRecursiveMaster(f, src)` | `plugin.add_recursive_masters(source)` |
| `Add(parent, name, True)` | `record.add_subrecord(sig, data)` |
| `Remove(element)` | `record.remove_subrecord(sr)` |
| `EditorID(record)` | `record.editor_id` |
| `Signature(record)` | `record.signature` |
| `GetLoadOrderFormID(r)` | `record.form_id` |
| `FileByIndex(i)` | `plugin_set[i]` |
| `FileCount` | `len(plugin_set)` |
| `Hash(alias, seed, count)` | `hash(alias) % count` (Python builtin) |

---

## Testing Strategy

### Automated tests
1. **Unit tests** for each module:
   - Hash-based selection is deterministic (same NPC alias -> same choice)
   - Label conflict detection and scoring
   - Race assignment logic per preference scheme
   - Bodypart flag parsing
2. **Port `BDFurrySkyrimTEST.pas`** tests to Python:
   - `NPCTintLayerCount` verification
   - Schlong list tests
   - Armor fixup tests
3. **Integration test**: Run furrifier on Skyrim.esm + furry race mod, compare
   output patch against xEdit-generated patch (byte-level or record-level diff)

### Manual tests
- Load both patches (Python-generated and xEdit-generated) in xEdit side-by-side
- Spot-check 10 NPCs: same race, same headparts, same tint layers
- Load Python-generated patch in-game, verify NPCs appear correctly

---

## Estimated Scope

| Module | Pascal lines | Python estimate | Complexity |
|---|---|---|---|
| models.py | -- | ~100 | Low (dataclasses) |
| config.py | 110 | ~100 | Low (argparse + dataclass) |
| race_defs.py | 508 | ~200 | Low (data definitions) |
| preferences/ | 663 | ~200 | Low (assignment dicts) |
| setup.py | 356 | ~200 | Medium (plugin traversal) |
| headparts.py | ~800 | ~300 | High (label matching, selection) |
| tints.py | ~700 | ~250 | High (tint layer logic) |
| npc.py | ~500 | ~250 | High (core furrification) |
| armor.py | 1386 | ~350 | Medium (bodypart flags, race lists) |
| schlongs.py | ~300 | ~100 | Medium (FLST/GLOB) |
| main.py | 1058 | ~120 | Low (orchestration) |
| tests/ | 936 | ~400 | Medium (port from Pascal + new) |
| **Total** | **~7500** | **~2600** | |

The Python version should be roughly 1/3 the line count due to:
- Proper data structures (dicts, dataclasses, enums) vs TStringList workarounds
- Direct record field access vs xEdit API boilerplate
- No UI form code (CLI + future tkinter)
- Python string/list handling vs Pascal equivalents
- `logging` module vs manual log infrastructure
