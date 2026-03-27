"""Main Plugin class for reading and modifying Bethesda plugin files."""

import struct
import shutil
from pathlib import Path
from typing import List, Optional, Union, Dict, Iterator, Any
from .record import Record, SubRecord, GroupRecord
from .utils import FormID, BinaryReader, BinaryWriter
from .exceptions import PluginError, ParseError, ValidationError


class PluginHeader:
    """Represents the TES4 header record of a plugin."""

    def __init__(self):
        self.version: float = 1.0
        self.num_records: int = 0
        self.next_object_id: int = 0x800
        self.author: str = ""
        self.description: str = ""
        self.masters: List[str] = []
        self.master_sizes: List[int] = []
        self.is_esm: bool = False
        self.is_esl: bool = False
        self.is_localized: bool = False
        self.override_records: List[FormID] = []
        # Preserve the raw TES4 record for round-trip fidelity
        self._raw_record: Optional[Record] = None

    @classmethod
    def from_record(cls, record: Record) -> 'PluginHeader':
        header = cls()
        header._raw_record = record

        # Parse header flags
        header.is_esm = bool(record.flags & 0x00000001)
        header.is_esl = bool(record.flags & 0x00000200)
        header.is_localized = bool(record.flags & 0x00000080)

        for subrecord in record.subrecords:
            if subrecord.signature == "HEDR":
                if subrecord.size >= 12:
                    reader = subrecord.get_reader()
                    header.version = reader.read_float()
                    header.num_records = reader.read_uint32()
                    header.next_object_id = reader.read_uint32()

            elif subrecord.signature == "CNAM":
                header.author = subrecord.get_string()

            elif subrecord.signature == "SNAM":
                header.description = subrecord.get_string()

            elif subrecord.signature == "MAST":
                header.masters.append(subrecord.get_string())

            elif subrecord.signature == "DATA":
                if subrecord.size >= 8:
                    header.master_sizes.append(
                        struct.unpack('<Q', subrecord.data[:8])[0])

            elif subrecord.signature == "ONAM":
                header.override_records = subrecord.get_form_id_array()

        return header

    def to_record(self) -> Record:
        """Convert header back to TES4 record.

        If we loaded from a file, reuse the raw record to preserve
        any subrecords we don't explicitly model (INTV, INCC, etc.)
        Only update the fields we track.
        """
        if self._raw_record is not None:
            record = self._raw_record

            # Update flags
            record.flags &= ~(0x00000001 | 0x00000200 | 0x00000080)
            if self.is_esm:
                record.flags |= 0x00000001
            if self.is_esl:
                record.flags |= 0x00000200
            if self.is_localized:
                record.flags |= 0x00000080

            # Update HEDR
            hedr = record.get_subrecord("HEDR")
            if hedr:
                writer = BinaryWriter()
                writer.write_float(self.version)
                writer.write_uint32(self.num_records)
                writer.write_uint32(self.next_object_id)
                hedr.data = writer.get_bytes()

            return record

        # Build from scratch
        record = Record("TES4", FormID(0))
        flags = 0
        if self.is_esm:
            flags |= 0x00000001
        if self.is_esl:
            flags |= 0x00000200
        if self.is_localized:
            flags |= 0x00000080
        record.flags = flags

        hedr = record.add_subrecord("HEDR")
        writer = BinaryWriter()
        writer.write_float(self.version)
        writer.write_uint32(self.num_records)
        writer.write_uint32(self.next_object_id)
        hedr.data = writer.get_bytes()

        if self.author:
            record.add_subrecord("CNAM").set_string(self.author)

        if self.description:
            record.add_subrecord("SNAM").set_string(self.description)

        for i, master in enumerate(self.masters):
            record.add_subrecord("MAST").set_string(master)
            if i < len(self.master_sizes):
                data_rec = record.add_subrecord("DATA")
                data_rec.data = struct.pack('<Q', self.master_sizes[i])

        if self.override_records:
            onam = record.add_subrecord("ONAM")
            onam.set_form_id_array(self.override_records)

        return record


class Plugin:
    """Represents a complete Bethesda plugin file (ESP/ESM/ESL)."""

    def __init__(self, file_path: Union[str, Path, None] = None):
        self.file_path: Optional[Path] = Path(file_path) if file_path else None
        self.header: PluginHeader = PluginHeader()
        self.groups: List[GroupRecord] = []
        self.records: List[Record] = []
        self.load_order: int = -1
        self.modified = False
        self._game_registry = None

        # Indexes for fast lookups
        self._form_id_index: Dict[int, Record] = {}
        self._editor_id_index: Dict[str, Record] = {}
        self._signature_index: Dict[str, List[Record]] = {}

        if file_path and Path(file_path).exists():
            self.load()

    def load(self, file_path: Optional[Union[str, Path]] = None) -> None:
        if file_path:
            self.file_path = Path(file_path)

        if not self.file_path or not self.file_path.exists():
            raise PluginError(f"Plugin file not found: {self.file_path}")

        with open(self.file_path, 'rb') as f:
            data = f.read()

        reader = BinaryReader(data)
        self._parse_plugin(reader)
        self._build_indexes()
        self.modified = False
        self.auto_detect_game()

    def _parse_plugin(self, reader: BinaryReader) -> None:
        self.groups.clear()
        self.records.clear()

        if reader.remaining() < 24:
            raise ParseError("File too small to contain valid plugin header")

        header_record = Record.from_bytes(reader)
        if header_record.signature != "TES4":
            raise ParseError(f"Expected TES4 header, got {header_record.signature}")

        self.header = PluginHeader.from_record(header_record)

        while not reader.at_end():
            if reader.remaining() < 4:
                break

            signature = reader.data[reader.position:reader.position + 4]

            if signature == b'GRUP':
                group = GroupRecord.from_bytes(reader)
                self.groups.append(group)
                self._collect_records_from_group(group)
            else:
                record = Record.from_bytes(reader)
                self.records.append(record)

    def _collect_records_from_group(self, group: GroupRecord) -> None:
        for item in group.records:
            if isinstance(item, Record):
                self.records.append(item)
            else:
                self._collect_records_from_group(item)

    def _build_indexes(self) -> None:
        self._form_id_index.clear()
        self._editor_id_index.clear()
        self._signature_index.clear()

        for record in self.records:
            self._form_id_index[record.form_id.value] = record

            if record.editor_id:
                self._editor_id_index[record.editor_id.lower()] = record

            if record.signature not in self._signature_index:
                self._signature_index[record.signature] = []
            self._signature_index[record.signature].append(record)

    def set_game(self, game_id: str) -> None:
        """Bind record schemas from a game registry.

        Valid game IDs: 'tes5' (Skyrim LE/SE), 'fo4' (Fallout 4), 'sf1' (Starfield).
        After calling this, records support typed field access via
        record['DATA']['damage'] etc.
        """
        from .defs.game import GameRegistry
        resolved = self._GAME_ALIASES.get(game_id, game_id)
        registry = GameRegistry.get_game(resolved)
        if registry is None:
            raise PluginError(f"Unknown game: {game_id}")
        self._game_registry = registry
        self._bind_schemas()

    def auto_detect_game(self) -> None:
        """Auto-detect game from header version and bind schemas."""
        from .defs.game import GameRegistry
        registry = GameRegistry.detect_game(self.header.version)
        if registry is not None:
            self._game_registry = registry
            self._bind_schemas()

    def _bind_schemas(self) -> None:
        """Bind schema definitions to all records based on their signatures."""
        if self._game_registry is None:
            return
        for record in self.records:
            schema = self._game_registry.get(record.signature)
            if schema is not None:
                record.bind_schema(schema)

    def get_record_by_form_id(self, form_id: Union[FormID, int]) -> Optional[Record]:
        if isinstance(form_id, FormID):
            form_id = form_id.value
        return self._form_id_index.get(form_id)

    def get_record_by_editor_id(self, editor_id: str) -> Optional[Record]:
        return self._editor_id_index.get(editor_id.lower())

    def get_records_by_signature(self, signature: str) -> List[Record]:
        return self._signature_index.get(signature, []).copy()

    def add_record(self, record: Record, group_signature: Optional[str] = None) -> None:
        self.records.append(record)

        target_group = None
        group_sig = group_signature or record.signature

        for group in self.groups:
            if (group.group_type == 0 and
                    isinstance(group.label, str) and
                    group.label == group_sig):
                target_group = group
                break

        if not target_group:
            target_group = GroupRecord(0, group_sig)
            self.groups.append(target_group)

        target_group.add_record(record)

        self._form_id_index[record.form_id.value] = record
        if record.editor_id:
            self._editor_id_index[record.editor_id.lower()] = record

        if record.signature not in self._signature_index:
            self._signature_index[record.signature] = []
        self._signature_index[record.signature].append(record)

        self.modified = True

    def remove_record(self, record: Record) -> bool:
        if record not in self.records:
            return False

        self.records.remove(record)

        for group in self.groups:
            if self._remove_record_from_group(group, record):
                break

        self._form_id_index.pop(record.form_id.value, None)
        if record.editor_id:
            self._editor_id_index.pop(record.editor_id.lower(), None)

        if record.signature in self._signature_index:
            try:
                self._signature_index[record.signature].remove(record)
                if not self._signature_index[record.signature]:
                    del self._signature_index[record.signature]
            except ValueError:
                pass

        self.modified = True
        return True

    def _remove_record_from_group(self, group: GroupRecord, record: Record) -> bool:
        if record in group.records:
            group.remove_record(record)
            return True
        for item in group.records:
            if isinstance(item, GroupRecord):
                if self._remove_record_from_group(item, record):
                    return True
        return False

    _GAME_VERSIONS = {
        'tes5': 1.71,
        'tes5le': 0.94,
        'fo4': 0.95,
        'sf1': 0.96,
    }
    # Aliases for set_game() -- tes5le uses the same schemas as tes5
    _GAME_ALIASES = {
        'tes5le': 'tes5',
    }

    @classmethod
    def new_plugin(cls, file_path: Union[str, Path],
                   masters: Optional[List[str]] = None,
                   game: str = 'tes5',
                   is_esm: bool = False) -> 'Plugin':
        """Create a new empty plugin with the given masters.

        game: 'tes5' (Skyrim LE/SE), 'fo4' (Fallout 4), 'sf1' (Starfield).
        Also accepts 'tes5le' to create with LE header version (0.94).
        Sets header version and binds schemas automatically.
        """
        plugin = cls()
        plugin.file_path = Path(file_path)
        plugin.header.version = cls._GAME_VERSIONS.get(game, 1.71)
        plugin.header.is_esm = is_esm
        if masters:
            plugin.header.masters = list(masters)
            plugin.header.master_sizes = [0] * len(masters)
        plugin.set_game(game)
        return plugin

    def add_master(self, master_name: str) -> None:
        """Add a master dependency if not already present."""
        if master_name.lower() not in [m.lower() for m in self.header.masters]:
            self.header.masters.append(master_name)
            self.header.master_sizes.append(0)

    def add_recursive_masters(self, source_plugin: 'Plugin') -> None:
        """Add a plugin and all its masters as dependencies."""
        # Add the source's masters first (in order)
        for master in source_plugin.header.masters:
            self.add_master(master)
        # Then add the source plugin itself
        if source_plugin.file_path:
            self.add_master(source_plugin.file_path.name)

    def copy_record(self, record: 'Record',
                    source_plugin: Optional['Plugin'] = None) -> 'Record':
        """Deep-copy a record into this plugin.

        If source_plugin is provided, automatically adds required masters.
        Returns the new record.
        """
        if source_plugin:
            self.add_recursive_masters(source_plugin)

        new_record = record.copy()
        self.add_record(new_record)
        return new_record

    def get_next_form_id(self) -> FormID:
        max_object_id = self.header.next_object_id - 1
        for record in self.records:
            if record.form_id.file_index == 0:
                max_object_id = max(max_object_id, record.form_id.object_index)
        next_id = max_object_id + 1
        self.header.next_object_id = next_id + 1
        return FormID(next_id)

    def _count_records_and_groups(self) -> int:
        """Count all records and groups (HEDR num_records includes both)."""
        count = 0
        for group in self.groups:
            count += self._count_in_group(group)
        return count

    def _count_in_group(self, group: GroupRecord) -> int:
        """Recursively count a group + all its contents."""
        count = 1  # the group itself
        for item in group.records:
            if isinstance(item, GroupRecord):
                count += self._count_in_group(item)
            else:
                count += 1
        return count

    def save(self, file_path: Optional[Union[str, Path]] = None) -> None:
        if file_path:
            self.file_path = Path(file_path)

        if not self.file_path:
            raise PluginError("No file path specified for saving")

        # Update header record count (includes both records and groups)
        self.header.num_records = self._count_records_and_groups()

        # Create backup if file exists
        if self.file_path.exists():
            backup_path = self.file_path.with_suffix(self.file_path.suffix + '.bak')
            if not backup_path.exists():
                shutil.copy2(self.file_path, backup_path)

        # Write plugin data
        writer = BinaryWriter()
        header_record = self.header.to_record()
        writer.write_bytes(header_record.to_bytes())

        for group in self.groups:
            writer.write_bytes(group.to_bytes())

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, 'wb') as f:
            f.write(writer.get_bytes())

        self.modified = False

    def save_as(self, file_path: Union[str, Path]) -> None:
        old_path = self.file_path
        try:
            self.save(file_path)
        finally:
            self.file_path = old_path

    def to_bytes(self) -> bytes:
        """Serialize the entire plugin to bytes without writing to disk."""
        writer = BinaryWriter()
        header_record = self.header.to_record()
        writer.write_bytes(header_record.to_bytes())
        for group in self.groups:
            writer.write_bytes(group.to_bytes())
        return writer.get_bytes()

    @property
    def is_esm(self) -> bool:
        return self.header.is_esm

    @property
    def is_esl(self) -> bool:
        return self.header.is_esl

    @property
    def is_esp(self) -> bool:
        return not self.header.is_esm and not self.header.is_esl

    @property
    def is_localized(self) -> bool:
        return self.header.is_localized

    def validate(self) -> List[str]:
        issues = []

        seen_form_ids = set()
        for record in self.records:
            if record.form_id.value in seen_form_ids:
                issues.append(f"Duplicate FormID: {record.form_id}")
            seen_form_ids.add(record.form_id.value)

        if self.header.is_esl:
            esl_records = [r for r in self.records if r.form_id.file_index == 0]
            if len(esl_records) > 2048:
                issues.append(
                    f"ESL file has {len(esl_records)} records, maximum is 2048")
            for record in esl_records:
                if record.form_id.object_index >= 0x1000:
                    issues.append(f"ESL FormID out of range: {record.form_id}")

        for record in self.records:
            if record.form_id.file_index > len(self.header.masters):
                issues.append(
                    f"FormID references unknown master file: {record.form_id}")

        return issues

    def get_statistics(self) -> Dict[str, Any]:
        stats = {
            'file_path': str(self.file_path) if self.file_path else None,
            'file_type': 'ESM' if self.is_esm else 'ESL' if self.is_esl else 'ESP',
            'total_records': self._count_records_and_groups(),
            'total_groups': len(self.groups),
            'masters': self.header.masters[:],
            'author': self.header.author,
            'description': self.header.description,
            'version': self.header.version,
            'next_object_id': f"0x{self.header.next_object_id:06X}",
            'is_localized': self.header.is_localized,
        }

        record_types = {}
        for record in self.records:
            record_types[record.signature] = record_types.get(record.signature, 0) + 1
        stats['record_types'] = record_types

        return stats

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[Record]:
        return iter(self.records)

    def __str__(self) -> str:
        file_name = self.file_path.name if self.file_path else "<unsaved>"
        file_type = 'ESM' if self.is_esm else 'ESL' if self.is_esl else 'ESP'
        return f"Plugin({file_name}, {file_type}, {len(self.records)} records)"

    def __repr__(self) -> str:
        return f"Plugin(file_path={self.file_path!r}, records={len(self.records)})"
