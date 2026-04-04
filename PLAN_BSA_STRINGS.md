# BSA String Table Extraction

## Problem

Localized plugins store display strings (FULL, SHRT, DESC) as 4-byte
string table IDs. The actual text lives in `.STRINGS`, `.DLSTRINGS`,
and `.ILSTRINGS` files. For vanilla Skyrim these are extracted to a
Strings folder, but Creation Club and mod plugins often keep them
inside BSA archives. When esplib copies a record to a non-localized
patch, it needs to resolve these IDs to inline strings. Without access
to the BSA, the text is lost.

## Goal

esplib transparently resolves localized strings from BSA archives when
extracted string files aren't available. No manual extraction required.

## Scope

Read-only BSA support, limited to extracting files by path. Skyrim SE
format (version 0x69, optional zlib per-file compression). No write
support, no BA2 (Fallout 4/Starfield) support initially.

## Design

### Responsibility split

**esplib owns everything.** The caller should not need to know about
BSAs. Today the caller sets `plugin.string_search_dirs` and esplib
handles the rest; after this change, esplib also searches BSAs
automatically.

**Caller responsibility:** None beyond what exists today. The existing
`string_search_dirs` mechanism continues to work. BSA lookup is a
transparent fallback inside esplib.

### New module: `esplib/bsa.py`

Minimal BSA reader (~150 lines):

```
class BsaReader:
    """Read-only access to a Bethesda BSA archive."""

    def __init__(self, path: Path)
    def list_files() -> list[str]
    def read_file(path: str) -> bytes
```

Parses the BSA header, folder records, file records, and filename
block on open. `read_file` seeks to the file's offset and reads/
decompresses (zlib) as needed. Paths are case-insensitive, forward-
slash separated (e.g. `strings/skyrim_english.strings`).

### Integration point: `StringTableManager.load_for_plugin`

Current flow:
1. Search `Strings/` subdir next to plugin
2. Search each `string_search_dirs` entry

New flow (append after step 2):
3. Find BSA(s) associated with the plugin
4. Check if BSA contains matching string files
5. If found, read them into memory via `BsaReader.read_file`
6. Parse the bytes with `StringTable.from_bytes` (new classmethod)

### BSA discovery

A plugin's BSA is found by naming convention:
- `PluginName.bsa` (e.g. `ccBGSSSE025-AdvDSGS.bsa`)
- `PluginName - Textures.bsa` (skip -- no strings here)

Search in the plugin's directory (i.e. the Data folder).

### Changes to existing code

1. **`strings.py`** -- add `StringTable.from_bytes(data, table_type)`
   classmethod. Currently `from_file` reads from disk; factor out the
   parsing so it can accept raw bytes from BSA extraction.

2. **`strings.py` `StringTableManager.load_for_plugin`** -- after the
   existing directory search loop, if any table is still None, try BSA
   fallback.

3. **`plugin.py`** -- no changes needed. `_load_string_tables` already
   calls `load_for_plugin` which will now transparently try BSAs.

### Reference implementation

`xedit_python/core/wb_bsa.py` has a working BSA reader (522 lines,
supports multiple versions). We only need the SSE path, which is much
simpler.

## Implementation steps

1. Add `BsaReader` class in `esplib/bsa.py`
2. Add `StringTable.from_bytes` classmethod
3. Add BSA fallback to `StringTableManager.load_for_plugin`
4. Test with a CC plugin that has strings only in its BSA
5. Verify no change in behavior for plugins with extracted strings

## Out of scope

- BA2 archives (Fallout 4, Starfield)
- BSA write support
- Extracting non-string files from BSAs
- Texture/mesh BSAs
