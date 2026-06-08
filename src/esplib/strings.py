"""String table support for localized Bethesda plugins.

Bethesda plugins with the Localized flag (0x80) store strings in external
string table files instead of inline in subrecords. Three file types:

  .STRINGS    -- null-terminated strings (used for FULL names, etc.)
  .DLSTRINGS  -- length-prefixed strings (used for DESC descriptions, etc.)
  .ILSTRINGS  -- length-prefixed null-terminated strings (used for INFO responses, etc.)

File format (all three types share the same header):
  uint32  count       -- number of entries
  uint32  data_size   -- total size of string data section
  [count entries of]:
    uint32  id        -- string ID
    uint32  offset    -- offset into string data section
  [string data section]:
    strings at the offsets listed above
"""

import struct
from pathlib import Path
from typing import Dict, List, Optional
from .utils import BinaryReader, BinaryWriter
from .exceptions import ParseError


# Skyrim spells English as 'english'; Fallout 4 uses the ISO-ish 'en'.
# Each logical language expands to the tokens seen in string-file names,
# tried in order. Unknown languages just try themselves.
_LANGUAGE_ALIASES = {
    'english': ['english', 'en'],
    'en': ['en', 'english'],
    'french': ['french', 'fr'],
    'german': ['german', 'de'],
    'italian': ['italian', 'it'],
    'spanish': ['spanish', 'es'],
    'russian': ['russian', 'ru'],
    'polish': ['polish', 'pl'],
    'japanese': ['japanese', 'ja'],
    'chinese': ['chinese', 'zh', 'cn'],
}


def _language_aliases(language: str) -> List[str]:
    """Ordered language tokens to try for a logical language name."""
    return _LANGUAGE_ALIASES.get(language.lower(), [language])


class StringTable:
    """Reads and writes a single string table file."""

    # String table types
    STRINGS = 'STRINGS'      # null-terminated
    DLSTRINGS = 'DLSTRINGS'  # uint32 length prefix + raw data
    ILSTRINGS = 'ILSTRINGS'  # uint32 length prefix + null-terminated data

    def __init__(self, table_type: str = STRINGS):
        self.table_type = table_type
        self.strings: Dict[int, str] = {}

    def get(self, string_id: int) -> Optional[str]:
        return self.strings.get(string_id)

    def set(self, string_id: int, value: str) -> None:
        self.strings[string_id] = value

    def remove(self, string_id: int) -> bool:
        if string_id in self.strings:
            del self.strings[string_id]
            return True
        return False

    @classmethod
    def from_bytes(cls, data: bytes, table_type: str = 'STRINGS') -> 'StringTable':
        table = cls(table_type)
        if len(data) < 8:
            return table

        reader = BinaryReader(data)
        count = reader.read_uint32()
        data_size = reader.read_uint32()

        # Read directory
        directory = []
        for _ in range(count):
            if reader.remaining() < 8:
                break
            string_id = reader.read_uint32()
            offset = reader.read_uint32()
            directory.append((string_id, offset))

        # data section starts right after the directory
        data_section_start = 8 + count * 8

        for string_id, offset in directory:
            abs_offset = data_section_start + offset

            if abs_offset >= len(data):
                continue

            if table_type == cls.STRINGS:
                # Null-terminated string
                end = data.index(b'\x00', abs_offset) if b'\x00' in data[abs_offset:] else len(data)
                text = data[abs_offset:end].decode('cp1252', errors='replace')

            elif table_type == cls.DLSTRINGS:
                # uint32 length prefix, then raw string data (no null terminator)
                if abs_offset + 4 > len(data):
                    continue
                str_len = struct.unpack('<I', data[abs_offset:abs_offset + 4])[0]
                str_start = abs_offset + 4
                if str_start + str_len > len(data):
                    str_len = len(data) - str_start
                text = data[str_start:str_start + str_len].decode('cp1252', errors='replace')

            elif table_type == cls.ILSTRINGS:
                # uint32 length prefix (includes null terminator), then null-terminated string
                if abs_offset + 4 > len(data):
                    continue
                str_len = struct.unpack('<I', data[abs_offset:abs_offset + 4])[0]
                str_start = abs_offset + 4
                if str_start + str_len > len(data):
                    str_len = len(data) - str_start
                raw = data[str_start:str_start + str_len]
                text = raw.rstrip(b'\x00').decode('cp1252', errors='replace')

            else:
                raise ParseError(f"Unknown string table type: {table_type}")

            table.strings[string_id] = text

        return table

    def to_bytes(self) -> bytes:
        # Build string data section and directory
        data_parts = bytearray()
        directory = []

        for string_id in sorted(self.strings.keys()):
            text = self.strings[string_id]
            offset = len(data_parts)
            encoded = text.encode('cp1252', errors='replace')

            if self.table_type == self.STRINGS:
                data_parts.extend(encoded)
                data_parts.append(0)  # null terminator

            elif self.table_type == self.DLSTRINGS:
                data_parts.extend(struct.pack('<I', len(encoded)))
                data_parts.extend(encoded)

            elif self.table_type == self.ILSTRINGS:
                data_parts.extend(struct.pack('<I', len(encoded) + 1))
                data_parts.extend(encoded)
                data_parts.append(0)  # null terminator

            directory.append((string_id, offset))

        # Write header + directory + data
        writer = BinaryWriter()
        writer.write_uint32(len(directory))
        writer.write_uint32(len(data_parts))

        for string_id, offset in directory:
            writer.write_uint32(string_id)
            writer.write_uint32(offset)

        writer.write_bytes(data_parts)
        return writer.get_bytes()

    @classmethod
    def from_file(cls, path: Path, table_type: Optional[str] = None) -> 'StringTable':
        if table_type is None:
            suffix = path.suffix.upper().lstrip('.')
            if suffix in (cls.STRINGS, cls.DLSTRINGS, cls.ILSTRINGS):
                table_type = suffix
            else:
                table_type = cls.STRINGS

        with open(path, 'rb') as f:
            data = f.read()

        return cls.from_bytes(data, table_type)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(self.to_bytes())

    def __len__(self) -> int:
        return len(self.strings)

    def __contains__(self, string_id: int) -> bool:
        return string_id in self.strings

    def __repr__(self) -> str:
        return f"StringTable(type={self.table_type}, entries={len(self.strings)})"


class StringTableManager:
    """Manages the three string tables for a localized plugin."""

    def __init__(self):
        self.strings: Optional[StringTable] = None      # .STRINGS
        self.dlstrings: Optional[StringTable] = None     # .DLSTRINGS
        self.ilstrings: Optional[StringTable] = None     # .ILSTRINGS

    def load_for_plugin(self, plugin_path: Path, language: str = 'english',
                        search_dirs: Optional[list] = None) -> None:
        """Load string tables for a plugin.

        Searches for files like Skyrim_english.STRINGS in:
        1. The Strings/ subdirectory next to the plugin
        2. Any additional directories in search_dirs
        3. BSA archives matching the plugin name (e.g. PluginName.bsa)
        """
        plugin_name = plugin_path.stem
        langs = _language_aliases(language)
        dirs = [plugin_path.parent / 'Strings']
        if search_dirs:
            dirs.extend(Path(d) for d in search_dirs)

        tables = [
            (StringTable.STRINGS, 'strings'),
            (StringTable.DLSTRINGS, 'dlstrings'),
            (StringTable.ILSTRINGS, 'ilstrings'),
        ]

        # Step 1-2: search extracted string files on disk. Try each
        # language alias (e.g. 'english' then 'en' for FO4 naming).
        for table_type, attr in tables:
            hit = None
            for d in dirs:
                for lang in langs:
                    filepath = d / f"{plugin_name}_{lang}.{table_type}"
                    if filepath.exists():
                        hit = filepath
                        break
                if hit:
                    break
            if hit is not None:
                setattr(self, attr, StringTable.from_file(hit, table_type))

        # Step 3: if any tables are still missing, try BSA/BA2
        missing = [(tt, attr) for tt, attr in tables
                   if getattr(self, attr) is None]
        if missing:
            self._load_from_bsa(plugin_path, plugin_name, langs, missing)

    def _load_from_bsa(self, plugin_path: Path, plugin_name: str,
                       langs, missing: list) -> None:
        """Try to load missing string tables from BSA/BA2 archives.

        ``langs`` is the ordered list of language tokens to try (e.g.
        ['english', 'en']) — Skyrim BSAs use 'english', FO4 BA2s use 'en'.

        Search order:
        1. PluginName.bsa/.ba2, PluginName - Main.bsa/.ba2 (plugin-specific)
        2. All other BSAs/BA2s in the Data directory (vanilla strings live in
           shared archives like Skyrim - Interface.bsa / Fallout4 - Interface.ba2)
        """
        import logging
        from .bsa import BsaReader, BsaError
        from .ba2 import Ba2Reader

        # Accept a bare string for backward compatibility.
        if isinstance(langs, str):
            langs = [langs]

        data_dir = plugin_path.parent
        if not data_dir.exists():
            return

        # (path, reader_class) pairs, plugin-specific archives first.
        candidates = []
        for ext, reader_cls in (('bsa', BsaReader), ('ba2', Ba2Reader)):
            for stem in (plugin_name, f"{plugin_name} - Main"):
                p = data_dir / f"{stem}.{ext}"
                if p.exists():
                    candidates.append((p, reader_cls))
        # Then every other archive in the data dir.
        for ext, reader_cls in (('bsa', BsaReader), ('ba2', Ba2Reader)):
            for p in sorted(data_dir.glob(f'*.{ext}')):
                if not any(p == c[0] for c in candidates):
                    candidates.append((p, reader_cls))

        for arch_path, reader_cls in candidates:
            if not missing:
                break
            try:
                with reader_cls(arch_path) as arch:
                    still_missing = []
                    for table_type, attr in missing:
                        data = None
                        for lang in langs:
                            key = f"strings\\{plugin_name}_{lang}.{table_type}"
                            if arch.has_file(key):
                                data = arch.read_file(key)
                                break
                        if data:
                            setattr(self, attr,
                                    StringTable.from_bytes(data, table_type))
                        else:
                            still_missing.append((table_type, attr))
                    missing = still_missing
            except (BsaError, ValueError, OSError) as e:
                logging.getLogger(__name__).debug(
                    "Could not read archive %s: %s", arch_path.name, e)
                continue


    def get_string(self, string_id: int) -> Optional[str]:
        """Look up a string ID across all loaded tables."""
        if self.strings and string_id in self.strings:
            return self.strings.get(string_id)
        if self.dlstrings and string_id in self.dlstrings:
            return self.dlstrings.get(string_id)
        if self.ilstrings and string_id in self.ilstrings:
            return self.ilstrings.get(string_id)
        return None

    def __repr__(self) -> str:
        counts = []
        if self.strings:
            counts.append(f"STRINGS={len(self.strings)}")
        if self.dlstrings:
            counts.append(f"DLSTRINGS={len(self.dlstrings)}")
        if self.ilstrings:
            counts.append(f"ILSTRINGS={len(self.ilstrings)}")
        return f"StringTableManager({', '.join(counts) or 'empty'})"
