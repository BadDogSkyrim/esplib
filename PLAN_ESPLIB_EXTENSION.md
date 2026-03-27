# Plan: esplib Extension -- Furrifier Support, FO4, Auto-Sort

## Context

esplib has 7 phases complete covering Skyrim SE with 14 record types, typed
access, multi-plugin loading, override resolution, and CLI tools. This plan
extends esplib to support converting the BDFurrySkyrim_Furrifier xEdit script
suite (~7500 lines of Pascal) to Python, adds Fallout 4 support, and implements
auto-sort subrecords.

---

## Phase A: Additional Skyrim Record Definitions

**Goal:** Define the record types the Furrifier needs that we don't have yet.

**Records to add to `defs/tes5.py`:**
- **RACE** -- central to Furrifier (Head Data, tint masks, skin textures, presets, RNAM, NAM8, WNAM, DATA flags)
- **HDPT** -- headpart records (PNAM type, Full name, model)
- **ARMA** -- armor addon (RNAM primary race, Additional Races array, BOD2 body template, MOD2/MOD4 models)
- **QUST** -- quest records (VMAD scripts for SOS detection -- simplified, mainly need VMAD access)

**Subrecords to add to NPC_ definition:**
- `Head Parts` -- array of HDPT FormID references
- `Tint Layers` -- array of tint layer structs (TINI index, TINC color, TIAS alpha, TINV value)
- `DOFT` -- default outfit FormID
- `QNAM` -- texture lighting color

**Automated tests:**
- Resolve RACE records from Skyrim.esm (NordRace, etc.), verify Head Data fields
- Resolve HDPT records, verify PNAM type values
- Resolve ARMA records, verify Additional Races list
- Resolve NPC_ Head Parts and Tint Layers from vanilla NPCs
- Bulk resolve 200 RACE, HDPT, ARMA records without error

**Manual tests:**
- Load Skyrim.esm, resolve NordRace -- compare Head Data tint mask list against xEdit
- Pick a vanilla NPC with tint layers, resolve in esplib, compare tint layer count/values against xEdit
- Pick an ARMA record, verify Additional Races list matches xEdit

---

## Phase B: Record Copy & Patch File Operations

**Goal:** Provide the core operations the Furrifier uses to build a patch file.

**New functionality in `plugin.py`:**
- `Plugin.new_plugin(name, masters)` -- create a new empty plugin with masters
- `Plugin.copy_record(record, source_plugin)` -- deep-copy a record into this plugin, automatically adding required masters
- `Plugin.add_master(master_name)` -- add a master dependency (with dedup)
- `Plugin.add_recursive_masters(source_plugin)` -- add a plugin and all its masters as dependencies

**New functionality in `record.py`:**
- `Record.copy()` -- deep copy a record (copies all subrecords)
- `Record.has_subrecord(sig)` -- convenience (alias for `sig in record`)

**Nested field access** -- xEdit uses dotted path strings like
`GetElementEditValues(rec, 'ACBS - Configuration\Flags\Female')` because Pascal
has no operator overloading. Python can do this more naturally with chained
`__getitem__`:

```python
rec['ACBS']['flags']              # read a struct field within a subrecord
rec['ACBS']['flags'] = 0x30       # write it back
```

This already works for one level (Phase 4). For deeper nesting, the resolved
dict from `rec['ACBS']` returns a plain Python dict, so `rec['ACBS']['flags']`
is just dict access. No `get_path()` / `set_path()` needed -- Python's native
syntax handles it. If we find a case where deeper access is awkward, we can
revisit.

**Automated tests:**
- Copy a WEAP record from one plugin to another, verify all subrecords intact
- Copy preserves FormID, flags, timestamp, version
- add_recursive_masters: plugin A depends on B which depends on C, copying A's record to D adds both A and B as masters
- add_master deduplicates
- Record.copy() produces independent copy (modifying copy doesn't affect original)

**Manual tests:**
- Create a patch plugin that copies IronSword from Skyrim.esm and modifies damage. Open in xEdit -- should show as override of Skyrim.esm's IronSword with correct master references.
- Load the patch in-game, verify the modified weapon works.

---

## Phase C: Auto-Sort Subrecords on Save

**Goal:** Automatically reorder subrecords to match schema definition order when saving.

**Implementation:**
- In `Record.to_bytes()`: if `self.schema` is set, reorder subrecords to match `schema.members` order before serializing. Unknown subrecords (not in schema) go at the end in their original relative order.
- This is transparent -- users never need to think about subrecord order.

**Automated tests:**
- Create a WEAP record with subrecords in wrong order, bind schema, save, reload -- verify xEdit-compatible order
- Unknown subrecords preserved at end in original relative order
- Records without schema: order unchanged
- Round-trip test: load Skyrim.esm (all records have correct order), save, byte-identical

**Manual tests:**
- Create a weapon with subrecords added in random order. Save with auto-sort. Open in xEdit -- all fields should display correctly (no blank panes or missing data).
- Compare against a weapon created with manual correct ordering -- output should be identical.

---

## Phase D: Fallout 4 Record Definitions

**Goal:** Port Tier 0 and Tier 1 definitions for Fallout 4.

**Files:**
- `src/esplib/defs/fo4.py` -- FO4 definitions

**Records (Tier 0):** TES4, GMST, GLOB, KYWD, FLST

**Records (Tier 1):** WEAP, ARMO, NPC_, ALCH, AMMO, BOOK, MISC, LVLI, COBJ, FACT, RACE, ARMA, HDPT

**Key FO4 differences from Skyrim:**
- WEAP DATA and DNAM have different layouts (FO4 weapons use OMOD system)
- ARMO has different bodypart flags
- NPC_ ACBS has additional fields
- BOD2 has different biped object flags
- Header version 1.0 vs Skyrim's 1.71

**Approach:** Hand-port using the same approach as Skyrim. Reference `wbDefinitionsFO4.pas` (14K lines). Focus on the record types listed above.

**Automated tests:**
- Resolve WEAP, ARMO, NPC_ from Fallout4.esm
- Bulk resolve 200 records per type without error
- Round-trip Fallout4.esm (byte-perfect)
- Game auto-detection: header version 1.0 -> fo4

**Manual tests:**
- `esplib info Fallout4.esm` -- record count matches FO4Edit
- `esplib dump Fallout4.esm --type WEAP --limit 5` -- field values match FO4Edit
- Create a test weapon plugin for FO4, open in FO4Edit, verify fields display correctly

---

## Phase E: FormList and Global Variable Helpers

**Goal:** Higher-level helpers for FLST and GLOB manipulation, used heavily by the Furrifier.

**API:**
```python
# FormList helpers
flst_record.add_form(form_id)       # Append to LNAM entries
flst_record.remove_form(form_id)
flst_record.contains_form(form_id)
flst_record.forms -> list[FormID]

# Global variable helpers
glob_record.value -> float           # Read FLTV
glob_record.value = 1.5              # Write FLTV
glob_record.copy_as(new_editor_id, new_form_id) -> Record
```

These could be convenience methods on Record when the schema is known, or standalone helper functions.

**Automated tests:**
- Add/remove/check forms in FLST records
- Read/write GLOB values
- Copy a GLOB with new EditorID
- Round-trip: create FLST, add forms, save, reload, verify list intact

**Manual tests:**
- Create a FLST plugin with 3 form references. Open in xEdit -- should show 3 entries in FormIDs list.
- Modify a GLOB value, save, open in xEdit -- value matches.

---

## Dependency Graph

```
Phase A (More Skyrim defs) ---+
                               |
Phase B (Copy & Patch ops) ----+---> Phase C (Auto-sort) ---> Ready for Furrifier conversion
                               |
Phase D (FO4 definitions) -----+
                               |
Phase E (FLST/GLOB helpers) ---+
```

Phases A, B, D, E can proceed in parallel. Phase C depends on A (needs schemas to sort against).

## Test Harness

Same as existing: pytest with synthetic tests + `@pytest.mark.gamefiles` for real ESM validation.
Manual test scripts at each phase with checklists written to `tests/output/`.
