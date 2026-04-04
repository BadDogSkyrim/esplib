# FormID Handling in esplib

## Background: How Bethesda FormIDs Work

A FormID is a 32-bit value: `[file_index:8][object_id:24]`.

The **file_index** byte indexes into the plugin's master list:
- Index 0 = first master (e.g. Skyrim.esm)
- Index 1 = second master
- Index N = the plugin itself, where N = len(masters)

The **object_id** is the record's identity within that file.

When a plugin references a record from another plugin, it uses that
plugin's position in its own master list. Different plugins may assign
different indices to the same master. For example:

    PluginA.esp masters: [Skyrim.esm, Dawnguard.esm]
    PluginB.esp masters: [Skyrim.esm, Update.esm, Dawnguard.esm]

Record 0x3A in Dawnguard.esm is `0x01003A` in PluginA but `0x02003A`
in PluginB. When copying a record from PluginA to PluginB, all FormID
references must be remapped.

## Current esplib Implementation

### Loading

When a plugin is loaded, FormIDs in records and subrecords use the
source plugin's master indexing. Record FormIDs and subrecord data are
stored as-is from disk.

### The Patch Plugin

The furrifier creates an empty patch plugin and builds it up by:

1. **Copying records** (`copy_record`) — deep-copies a record from a
   source plugin, remapping all FormIDs from the source's master
   indexing to the patch's master indexing.

2. **Creating new records** (`get_next_form_id`) — allocates a fresh
   FormID for records that are new to the patch (subraces, preset
   NPCs, schlong GLOBs).

3. **Writing cross-references** — code writes FormID values into
   subrecords (LNAM in FLSTs, RPRM in RACEs, etc.) referencing other
   records that may be in master plugins or in the patch itself.

### Master List Management

Masters are added **lazily** by `remap_formid`. When a FormID
references a master not yet in the patch's master list, that master is
appended. This means the master list grows incrementally as records
are copied.

The local file index (for records owned by the patch itself) is
`len(masters)`, which increases every time a new master is added.

### FormID Remapping (`remap_formid`)

Given a FormID from a source plugin:
1. Extract the file_index byte
2. Look up the master name in the source plugin's master list
3. Find (or lazily add) that master in the patch's master list
4. Return `(new_index << 24) | object_id`

This works correctly for records from master plugins. It does NOT
handle local records (records owned by the patch itself).

### New Record FormIDs (`get_next_form_id`)

Currently uses a **sentinel** approach:
- Allocates FormIDs with file_index = 0xFF (a value that can never
  be a real master index)
- At save time, `_finalize_local_form_ids` replaces 0xFF with the
  actual local index (`len(masters)`)

### Schema-Based FormID Discovery

Two operations need to find FormIDs within subrecord data:

1. **`_remap_subrecord_formids`** — called during `copy_record` to
   remap FormIDs from the source plugin's indexing to the patch's.
   Uses the record's schema to find FormID positions (EspFormID,
   EspArray of EspFormID, EspStruct containing EspFormID). Falls back
   to a hardcoded set for records without schemas.

2. **`_finalize_local_form_ids`** — called at save time to replace
   sentinel (0xFF) file indices with the real local index. Same
   schema-based discovery, same fallback.

Both share the same pattern: walk schema members, check for EspFormID
at each position. Neither handles FormIDs embedded in:
- VMAD (Papyrus script data) — complex binary format
- MO2S/MO3S/MO5S (Alternate Textures) — FormIDs inside variable-
  length struct arrays
- Other opaque binary blobs

## The Problem

### Cross-references to local records

When furrifier code writes a FormID that references a local record
(subrace, preset NPC, schlong GLOB), it uses `record.form_id.value`.
This value has the sentinel file index (0xFF). Examples:

- RPRM subrecord pointing to a preset NPC
- LNAM in a headpart FLST pointing to a furrified vanilla race
- LNAM in a schlong FLST pointing to a new GLOB

At save time, `_finalize_local_form_ids` scans subrecord data for
0xFF file indices and replaces them with the real local index. This
works IF the FormID is discoverable via the schema.

### Cross-references to master records

When furrifier code writes a FormID that references a record in a
master plugin, it needs to use the patch's master indexing. The code
currently does this in various ad-hoc ways:

- `remap_formid(fid, source_plugin)` — correct, but requires knowing
  which plugin the FormID came from
- Using `record.form_id.value` from a record loaded from a source
  plugin — this value uses the SOURCE plugin's indexing, not the
  patch's. It must be remapped.

### Where things go wrong

1. **`race_obj_to_fid` in headpart FLST code** — builds a lookup of
   `{object_id: (form_id_value, plugin)}`. For master-plugin races,
   `form_id_value` uses the source plugin's indexing. For local races
   (subraces), `plugin` is None and `form_id_value` has the sentinel.
   When writing to LNAM, the code remaps master-plugin FormIDs but
   passes through local FormIDs as-is (sentinel). Finalization should
   fix them, but races with `object_id` matching records in other
   plugins may collide or be missed.

2. **Races not in `race_obj_to_fid`** — vampire variants, child
   races, etc. that aren't in the furrifier's race set. These hit
   the fallback path and produce broken FormIDs.

3. **Schlong GLOBs** — created with sentinel FormIDs, added to FLSTs
   via `flst_add` which writes the raw sentinel value. Finalization
   fixes these if the schema is available.

## What Should Change

The core issue is that we have two kinds of FormID values floating
around: source-indexed and patch-indexed. Code that writes FormIDs
into subrecords must always produce patch-indexed values. For local
records, the sentinel approach handles this (write sentinel, fix at
save). For master records, the value must be explicitly remapped.

The `race_obj_to_fid` approach of storing raw FormID values from
source plugins is fragile — the caller must remember to remap. A
cleaner approach would be to always store patch-indexed FormIDs, or
to provide a helper that resolves an object_id to a patch-indexed
FormID.

## Possible Strategies

### Strategy A: Normalize to load-order index (xEdit approach)

xEdit normalizes all FormIDs to a "session" index — the global load
order — on load. All work happens in that space. When saving, FormIDs
are remapped from session index to the plugin's own master list.

In our case, PluginSet represents the global load order. On load,
every record's FormIDs would be rewritten to use load-order indices.
All cross-references, comparisons, and lookups work without remapping.
The patch writes in load-order space; `save()` remaps back to the
patch's master list.

**Pros:**
- Eliminates all per-copy remapping — no more `remap_formid` at
  copy time
- Cross-references between any plugins just work
- The furrifier never has to think about which plugin a FormID came
  from
- Matches xEdit's mental model, so modders familiar with xEdit
  understand the behavior

**Cons:**
- Minimal. Without a PluginSet, the accessor just returns the raw
  FormID — the plugin's master list is effectively the load order.
  Cross-plugin comparisons don't work, but you don't need them when
  working with a single plugin. The PluginSet case is the one that
  matters, and there the normalization is well-defined.

Note: normalization does NOT have to happen eagerly on load. FormIDs
can be normalized lazily when read through an accessor (same principle
as string delocalization). Raw bytes stay as-is on disk and in memory
until something reads a FormID, at which point the accessor converts
from per-plugin indexing to load-order indexing on the fly. This
preserves round-trip fidelity for unmodified records and avoids
parsing subrecord data during load.

### Strategy B: Keep per-plugin indexing, remap at copy time (current)

What we do now. `copy_record` remaps FormIDs from source to
destination. Cross-reference code must explicitly remap or use the
sentinel for local records.

**Pros:**
- Simple load path — FormIDs match disk
- Works for single-plugin use without a PluginSet

**Cons:**
- Every write site must know which plugin a FormID came from and
  remap it correctly
- The sentinel dance for local records is fragile
- Bugs are subtle: wrong file index produces a valid-looking FormID
  that points to the wrong record

### Strategy C: Object-ID only (REJECTED)

Strip the file index entirely, work with 24-bit object IDs, and
reconstruct the full FormID at save time.

**Rejected** because object_ids are NOT unique across plugins.
Different plugins can define records with the same object_id (e.g.
CellanRace.esp object 0x801 is a HDPT, while the patch's local
record 0x801 is a subrace RACE). Without the file index there is
no way to distinguish them.

### Strategy D: Normalize to patch-indexed on receipt

A middle ground: don't normalize everything on load, but ensure that
any FormID the furrifier stores or passes around is already in patch-
indexed form. This means:

- When reading a FormID from a source record to use later, immediately
  remap it to patch indexing: `patch.remap_formid(fid, source_plugin)`
- For local records, use the sentinel (0xFF) which gets finalized at
  save time
- Lookups and cross-reference dicts store patch-indexed FormIDs

This is essentially what we're trying to do now, but applied
consistently. The problem is that code sometimes stores source-indexed
FormIDs and forgets to remap.

**Pros:**
- No big architectural change
- Only touches code that reads FormIDs for later use

**Cons:**
- Still requires discipline at every read site
- Still requires the sentinel for local records

### Strategy E: Schema-driven accessor functions

The schema already knows which subrecord fields are FormIDs. Instead
of exposing raw bytes and expecting callers to remap, provide accessor
functions that handle the indexing automatically.

**Reading:** A FormID accessor on a subrecord (or via record typed
access) returns a value normalized to some working space — either
the load-order index (if a PluginSet is available) or a
(plugin, object_id) pair. The caller never sees the raw file index.

**Writing:** A FormID setter accepts a record reference (or a
normalized FormID) and writes the correct bytes for the destination
plugin's master list. For the patch, this means computing the correct
master index (or sentinel for local records) at write time.

This could look like:

    # Reading: returns a normalized FormID or record reference
    race_fid = npc['RNAM']              # typed access, already works
    race_rec = plugin_set.resolve(race_fid)  # get the actual record

    # Writing: accepts a record or normalized FormID
    patched.set_formid('RNAM', race_rec.form_id, race_rec.plugin)
    # or:
    patched.set_formid('RNAM', patch_indexed_fid)

For bulk operations like FLST LNAM lists, the same principle applies:
the write function takes care of remapping.

The key insight: since the schema marks every FormID field, the
accessor layer can intercept all reads and writes. No caller ever
handles raw file indices. `copy_record` uses the same accessors
internally.

**Pros:**
- FormID handling is centralized — bugs can only be in one place
- Callers never see or manipulate file indices
- Works naturally with the existing schema infrastructure
- `copy_record` remapping becomes a special case of the general
  accessor, not separate machinery
- The sentinel approach for local records is an implementation detail
  hidden inside the accessor

**Cons:**
- Requires changing all call sites that currently read/write FormIDs
  via raw subrecord bytes (`sr.get_uint32()`, `struct.pack`, etc.)
- Need to decide what the "working space" FormID looks like — load-
  order indexed, (plugin, object_id) pair, or something else
- Bulk data (KWDA arrays, FLST LNAMs) needs efficient batch access

### Strategy F: Fixup list for local references

Since masters are always appended (never reordered), references to
master-plugin records never go stale — their file index is correct
at write time and stays correct. The only problem is references to
the patch's own local records, where the file index isn't known until
save time (because more masters may be added).

Instead of a sentinel byte or schema scanning, track every local
FormID write explicitly. Every time code writes a FormID that
references a local record into subrecord data, register it on a
fixup list: `(subrecord, byte_offset)`. At save time, walk the list
and set the file index byte to `len(masters)`.

For record-level FormIDs (the record's own `form_id`), keep
`_new_records` and fix those the same way.

    # Writing a local FormID:
    fid = new_race.form_id   # has placeholder file index
    patch.write_local_formid(sr, offset, fid.object_index)
    # internally: writes (0 << 24) | object_index to sr.data
    #             appends (sr, offset) to fixup list

    # At save time:
    for sr, offset in fixup_list:
        sr.data[offset + 3] = len(masters)  # set file index byte

**Pros:**
- Exact — no scanning, no false matches, no schema dependency
- Simple — the fixup is a byte poke, not a search
- No sentinel needed (can use 0 or any placeholder)
- Works for any subrecord format including VMAD, alternate textures,
  or anything else — as long as the write goes through the helper
- Master-indexed FormIDs are never touched

**Cons:**
- Every write site for local FormIDs must call the helper instead of
  raw `struct.pack`. If someone forgets, the FormID silently has the
  wrong file index.
- The fixup list holds references to SubRecord objects — must not be
  invalidated between write and save (this should be fine in practice)

### Recommendation

Strategy F is the most targeted fix. It solves exactly the problem
we have (local FormID file index is unknown at write time) without
requiring architectural changes to how we handle master-indexed
FormIDs, which already work correctly.

Strategy E (accessor functions) is the right long-term direction —
it would eliminate raw FormID manipulation entirely. But it's a bigger
change and Strategy F can be a stepping stone: the `write_local_formid`
helper is the seed of a proper FormID write accessor.

The sentinel approach (current) tries to solve the same problem as F
but uses a magic value and schema scanning instead of an explicit
list. F is strictly better: exact, no false matches, no schema
dependency for finalization.

## Proposed Design: Load-Order FormIDs + Fixup List

Combine the best parts of A, E, and F:

### Read side: load-order indexed FormIDs

When a PluginSet is available, FormID accessors return values indexed
by load-order position. The PluginSet assigns each plugin a stable
index (its position in the load order). A FormID `(2, 0x3A)` always
means "object 0x3A from the third plugin in the load order" regardless
of which plugin's master list you read it from.

This is a property of the accessor, not the on-disk data. The raw
bytes are not modified on load. The accessor converts on the fly:

    # record loaded from PluginA.esp
    # PluginA masters: [Skyrim.esm, Dawnguard.esm]
    # Load order: Skyrim(0), Update(1), Dawnguard(2), PluginA(3)
    sr = record.get_subrecord('RNAM')
    raw = sr.get_uint32()         # 0x01003A (Dawnguard in PluginA's list)
    normalized = accessor(sr)     # 0x02003A (Dawnguard in load order)

The client works exclusively with load-order FormIDs. Comparisons
between records from different plugins just work. Dict keys just work.

### Write side: master-list indexed + fixup for local

When writing a FormID into a patch subrecord, the write accessor:

1. Converts the load-order FormID to the patch's master indexing
   (adding the master if needed)
2. If the FormID references the patch itself (a local record), writes
   a placeholder file index and appends `(subrecord, offset)` to the
   fixup list
3. At save time, walks the fixup list and sets the file index to
   `len(masters)` — which is now final

    # Writing to the patch
    # patch.write_formid(sr, offset, load_order_fid)
    # internally:
    #   if fid references a master plugin:
    #     convert to patch master index, write it
    #   if fid references the patch itself:
    #     write (0xFF << 24) | object_id
    #     fixup_list.append((sr, offset))
    #   0xFF is a deliberate sentinel — if the fixup somehow fails,
    #   it will fail obviously (xEdit/game reject file index 0xFF)
    #   rather than silently pointing to the wrong record

### What this means for the furrifier

The furrifier code becomes simple. No `remap_formid` calls. No
tracking which plugin a FormID came from. No sentinel. Example:

    # Read race FormID from source NPC (in load-order space)
    race_fid = npc['RNAM']  # load-order indexed

    # Write it to patched NPC (auto-converts to patch indexing)
    patched.write_formid('RNAM', race_fid)

    # Read FormIDs from an FLST, modify, write back
    race_fids = [sr.get_formid() for sr in flst.get_subrecords('LNAM')]
    race_fids.append(new_subrace.form_id)  # local, also load-order indexed
    patched_flst.remove_subrecords('LNAM')
    for fid in race_fids:
        patched_flst.write_formid('LNAM', fid)

### Implementation phases

1. Add load-order-indexed FormID read accessors (on Record/SubRecord,
   using plugin back-reference + PluginSet)
2. Add write accessor on Plugin that converts from load-order to
   master-list indexing, with fixup list for local records
3. Add save-time fixup: walk the fixup list and replace 0xFF file
   indices with the final `len(masters)`. Also fix `record.form_id`
   on `_new_records`.
4. Migrate furrifier code from raw `get_uint32`/`struct.pack` to
   the new accessors
5. Remove `remap_formid` from `copy_record` — the schema-driven
   copy uses the new accessors internally
6. Remove `_finalize_local_form_ids`, the schema-scanning fixup,
   and the fallback FormID sets
