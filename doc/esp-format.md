# Bethesda Plugin File Format (.esp/.esm/.esl)

This documents the binary format of Bethesda plugin files as used by
Skyrim (LE/SE), Fallout 4, and related Creation Engine games. The format
is the same across games; the differences are in which record types exist
and what their subrecords mean.

## File Structure

A plugin file is a flat sequence of a TES4 header record followed by GRUP
containers. There is no file-level header or table of contents -- you parse
sequentially from the start.

```
TES4        (file header record -- always first, always exactly one)
GRUP "GMST" (all Game Settings)
  GMST record
  GMST record
  ...
GRUP "WEAP" (all Weapons)
  WEAP record
  WEAP record
  ...
GRUP "WRLD" (Worldspaces -- contains nested sub-groups)
  WRLD record
  GRUP (children of this worldspace)
    GRUP (cell block)
      GRUP (cell sub-block)
        CELL record
        GRUP (cell children)
          REFR record
          REFR record
          ...
```

Top-level GRUPs are organized by record signature. Interior/worldspace
GRUPs nest deeply. esplib flattens all records into a single list for
easy access while preserving the GRUP tree for byte-perfect round-trip.

---

## Record Format

Every record (TES4, GMST, WEAP, NPC_, etc.) has a 24-byte header followed
by a payload of subrecords.

```
Offset  Size  Type    Field
0       4     char[4] Signature    "WEAP", "NPC_", "TES4", etc.
4       4     uint32  Data Size    Byte count of the payload (not including header)
8       4     uint32  Flags        Bit flags (see below)
12      4     uint32  FormID       Unique record identifier
16      4     uint32  Timestamp    Version control timestamp
20      2     uint16  Version      Form version (44 for Skyrim SE)
22      2     uint16  VCI          Version control info
24      ...   bytes   Payload      Subrecord data (Data Size bytes)
```

Total record size on disk: 24 + Data Size.

### Record Flags

| Bit | Value | Meaning |
|-----|-------|---------|
| 0 | 0x00000001 | ESM flag (on TES4: file is .esm) |
| 5 | 0x00000020 | Deleted |
| 9 | 0x00000200 | Casts shadows (lights) |
| 10 | 0x00000400 | Quest item / persistent reference |
| 11 | 0x00000800 | Initially disabled |
| 12 | 0x00001000 | Ignored |
| 18 | 0x00040000 | Compressed (payload is zlib-compressed) |

### Compression

When the compressed flag (0x00040000) is set, the payload format changes:

```
Offset  Size  Type    Field
0       4     uint32  Uncompressed size
4       ...   bytes   zlib-compressed subrecord data
```

Decompress with zlib inflate. The decompressed data contains the subrecords
in normal format. On save, if the record was originally compressed, it must
be recompressed.

### FormID

The 32-bit FormID encodes both a file index and an object ID:

```
Bits 24-31 (top byte):    File index into the master list
Bits 0-23  (lower 3 bytes): Object ID within that file
```

The file index maps to the MAST entries in the TES4 header, starting at 0.
The plugin's own records use the next index after the last master.

```
Example: myPlugin.esp with masters [Skyrim.esm, Update.esm, USSEP.esm]

  0x00XXXXXX -> Skyrim.esm    (MAST index 0)
  0x01XXXXXX -> Update.esm    (MAST index 1)
  0x02XXXXXX -> USSEP.esm     (MAST index 2)
  0x03XXXXXX -> myPlugin.esp  (own records, index = master count)
```

An override record in myPlugin that modifies Skyrim.esm's Iron Sword
(0x00012EB7) keeps that same FormID -- the 0x00 prefix tells the engine
it originated in Skyrim.esm.

For ESL-flagged plugins, the format is different:

```
Bits 24-31: 0xFE (fixed)
Bits 12-23: ESL index
Bits 0-11:  Object ID (max 4096 records)
```

---

## Subrecord Format

Subrecords are the fields within a record. Each has a 6-byte header:

```
Offset  Size  Type    Field
0       4     char[4] Signature    "EDID", "DATA", "FULL", etc.
4       2     uint16  Data Size    Byte count of the data
6       ...   bytes   Data         Raw field data
```

Total subrecord size on disk: 6 + Data Size.

### Maximum Size and XXXX Overflow

The uint16 data size field limits subrecords to 65535 bytes. For larger data,
a special XXXX subrecord is placed immediately before the oversized subrecord:

```
XXXX  (signature)
4     (data size -- always 4)
N     (uint32 -- the actual data size of the next subrecord)

LNAM  (the actual subrecord signature)
0     (data size field -- ignored, use XXXX's value instead)
...   (N bytes of data)
```

This is rare -- mainly seen in FLST (FormList) records with thousands of entries.

### Common Subrecord Signatures

Some signatures appear across many record types with consistent meaning:

| Signature | Meaning | Data Format |
|-----------|---------|-------------|
| EDID | Editor ID | Null-terminated string |
| FULL | Display name | Localized string (uint32 ID or inline) |
| DESC | Description | Localized string |
| OBND | Object bounds | 6 x int16 (x1,y1,z1,x2,y2,z2) |
| MODL | Model filename | Null-terminated string |
| MODT | Model texture data | Raw bytes |
| KSIZ | Keyword count | uint32 |
| KWDA | Keywords | Array of uint32 FormIDs |
| VMAD | Script data | Papyrus VM attached scripts |

### Type-Specific Subrecords

Most subrecords are specific to their parent record type. The same signature
can mean completely different things in different records:

| Parent | Signature | Meaning | Format |
|--------|-----------|---------|--------|
| WEAP | DATA | Game data | uint32 value + float weight + uint16 damage |
| ARMO | DATA | Armor data | int32 value + float weight |
| FACT | DATA | Flags | uint32 flags |
| GLOB | FNAM | Variable type | uint8 ('s', 'l', or 'f') |
| HDPT | PNAM | Head part type | uint32 enum |
| WEAP | DNAM | Weapon stats | 100+ bytes of combat parameters |
| ARMO | DNAM | Armor rating | int32 (stored as rating x 100) |

This is why esplib uses schema definitions (EspRecord, EspSubRecord) to
interpret raw bytes -- there is no self-describing type system in the format.

---

## GRUP Format

GRUPs are containers that organize records. They have a 24-byte header:

```
Offset  Size  Type    Field
0       4     char[4] Signature    Always "GRUP"
4       4     uint32  Total Size   Size of entire GRUP including this header
8       4     varies  Label        Depends on group type (see below)
12      4     int32   Group Type   What kind of group this is
16      4     uint32  Timestamp
20      2     uint16  Version
22      2     uint16  VCI
24      ...   bytes   Contents     Records and nested GRUPs
```

### Group Types

| Type | Label | Description |
|------|-------|-------------|
| 0 | char[4] signature | Top-level: all records of one type (e.g. "WEAP") |
| 1 | uint32 FormID | World children |
| 2 | int32 block number | Interior cell block |
| 3 | int32 sub-block | Interior cell sub-block |
| 4 | uint32 FormID | Exterior cell block (grid coords packed) |
| 5 | uint32 FormID | Exterior cell sub-block |
| 6 | uint32 FormID | Cell children |
| 7 | uint32 FormID | Topic children |
| 8 | uint32 FormID | Cell persistent children |
| 9 | uint32 FormID | Cell temporary children |

Type 0 groups are the most common. Each record type gets one top-level GRUP
containing all records of that type. Interior and worldspace GRUPs nest
within each other to organize cells, references, and landscape data.

---

## TES4 Header Record

The first record in every plugin. Signature is "TES4", FormID is always 0.

Key subrecords:

| Signature | Meaning | Format |
|-----------|---------|--------|
| HEDR | Header data | float version + uint32 record count + uint32 next object ID |
| CNAM | Author | Null-terminated string |
| SNAM | Description | Null-terminated string |
| MAST | Master filename | Null-terminated string (repeats for each master) |
| DATA | Master data | uint64 (always 0, follows each MAST) |
| ONAM | Overridden forms | Array of uint32 FormIDs (see below) |
| INTV | Internal version | uint32 |
| INCC | Internal cell count | uint32 |

MAST/DATA pairs appear in load order. A plugin's FormIDs reference masters
by index: file index 0 = first MAST, index 1 = second MAST, etc. The
plugin's own new records use the next index (equal to its master count).

### ONAM -- Overridden Forms

ONAM lists the FormIDs of specific overridden records from master files.
It is **only written for ESM-flagged files** (and ESLs). Regular ESPs do
not have it.

Despite the name, ONAM does not list *all* overrides. It only includes
overrides of **non-persistent temporary references and related records**
with these signatures:

- Skyrim: NAVM, LAND, REFR, PGRE, PMIS, ACHR, PARW, PBEA, PFLA, PCON, PBAR, PHZD
- Fallout 4 adds: SCEN, DLBR, DIAL, INFO

Persistent references are excluded. The engine uses ONAM to quickly identify
which temporary world references an ESM modifies, without scanning every record.

**When esplib writes ONAM:** Currently esplib preserves ONAM from the original
file on round-trip but does not generate it for new plugins. Most modding use
cases produce ESP files which don't need ONAM. If you need to create an ESM
with correct ONAM, the entries must be added manually or the plugin should be
finalized in the Creation Kit or xEdit.

### Header Version

The float in HEDR identifies the game:

| Version | Game |
|---------|------|
| 0.94 | Skyrim LE |
| 1.71 | Skyrim SE |
| 0.95 | Fallout 4 |

---

## Localized Strings

When TES4 flags include 0x00000080 (localized), string subrecords (FULL, DESC,
etc.) contain a uint32 string table ID instead of inline text. The actual
strings are stored in separate .STRINGS, .DLSTRINGS, and .ILSTRINGS files
alongside the plugin.

### String Table Format

Each string table file has a header followed by a directory and string data:

```
Offset  Size  Type    Field
0       4     uint32  Count       Number of entries
4       4     uint32  Data Size   Total bytes of string data

Directory (Count entries):
  0     4     uint32  String ID
  4     4     uint32  Offset into string data block

String Data:
  Null-terminated strings (STRINGS) or
  uint32 length + string bytes (DLSTRINGS, ILSTRINGS)
```

File naming: `PluginName_Language.STRINGS` (e.g. `Skyrim_English.STRINGS`).

---

## Byte Order

All multi-byte values are little-endian. All strings use Windows-1252 encoding
(cp1252) unless localized, in which case string tables may use UTF-8.

## Alignment

There is no alignment padding. Records, subrecords, and GRUPs are packed
contiguously. A record's payload starts immediately after its 24-byte header.
