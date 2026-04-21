"""Minimal read-only BSA archive reader for Skyrim LE/SE.

Supports BSA version 0x68 (Skyrim LE, zlib compression) and 0x69
(Skyrim SE, LZ4-frame compression). Only provides file listing and
extraction by path.

LE and SE differ in their compression format. Calling code treats
`read_file` opaquely — the reader picks the right codec based on the
version header.
"""

import struct
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Union


class BsaError(Exception):
    """Error reading a BSA archive."""
    pass


class _FileEntry:
    __slots__ = ('size', 'offset', 'folder_name', 'file_name')

    def __init__(self, size: int, offset: int,
                 folder_name: str, file_name: str):
        self.size = size
        self.offset = offset
        self.folder_name = folder_name
        self.file_name = file_name

    @property
    def path(self) -> str:
        return f"{self.folder_name}\\{self.file_name}"


# Header flags
_COMPRESSED_BY_DEFAULT = 0x0004
_EMBED_FILE_NAMES = 0x0100


class BsaReader:
    """Read-only access to a Bethesda BSA archive (Skyrim LE/SE).

    Usage:
        with BsaReader(path) as bsa:
            data = bsa.read_file('strings/skyrim_english.strings')
    """

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self._file = None
        self._files: Dict[str, _FileEntry] = {}
        self._compressed_by_default = False
        self._embed_file_names = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    def open(self) -> None:
        if not self.path.exists():
            raise BsaError(f"Archive not found: {self.path}")
        self._file = open(self.path, 'rb')
        self._read_index()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def list_files(self) -> List[str]:
        return list(self._files.keys())

    def has_file(self, path: str) -> bool:
        return path.replace('/', '\\').lower() in self._files

    def read_file(self, path: str) -> bytes:
        """Read and decompress a file from the archive."""
        key = path.replace('/', '\\').lower()
        entry = self._files.get(key)
        if entry is None:
            raise BsaError(f"File not found in archive: {path}")
        return self._extract(entry)

    def _read_index(self) -> None:
        f = self._file

        # Header: 4 (sig) + 32 (8 uint32s) = 36 bytes
        sig = f.read(4)
        if sig != b'BSA\x00':
            raise BsaError(f"Not a BSA file: {self.path}")

        (version, _rec_offset, archive_flags, folder_count, file_count,
         folder_names_len, file_names_len, _file_flags,
         ) = struct.unpack('<8I', f.read(32))

        if version not in (0x68, 0x69):
            raise BsaError(
                f"Unsupported BSA version 0x{version:02x} in {self.path}")

        is_sse = (version == 0x69)
        self._is_sse = is_sse
        self._compressed_by_default = bool(
            archive_flags & _COMPRESSED_BY_DEFAULT)
        self._embed_file_names = bool(
            archive_flags & _EMBED_FILE_NAMES)

        # Read folder records
        # SSE: hash(8) + count(4) + padding(4) + offset(8) = 24 bytes
        # LE:  hash(8) + count(4) + offset(4) = 16 bytes
        folder_recs = []
        for _ in range(folder_count):
            if is_sse:
                _hash, fcount, _pad, offset = struct.unpack(
                    '<QIIQ', f.read(24))
            else:
                _hash, fcount, offset = struct.unpack(
                    '<QII', f.read(16))
            folder_recs.append((fcount, offset))

        # Folder name + file record blocks are stored sequentially
        # right after the folder records. Read them in order.
        all_file_records = []  # (size, offset, folder_name)
        for fcount, _offset in folder_recs:
            # Folder name: length-prefixed, null-terminated
            name_len = struct.unpack('<B', f.read(1))[0]
            folder_name = f.read(name_len).rstrip(b'\x00').decode(
                'ascii', errors='replace')

            # File records for this folder
            for _ in range(fcount):
                _fhash, size, foffset = struct.unpack('<QII', f.read(16))
                all_file_records.append((size, foffset, folder_name))

        # File name block follows immediately
        file_names_data = f.read(file_names_len)
        file_names = file_names_data.split(b'\x00')

        # Build index
        for i, (size, foffset, folder_name) in enumerate(all_file_records):
            if i < len(file_names):
                fname = file_names[i].decode('ascii', errors='replace')
            else:
                fname = f'unknown_{i}'
            entry = _FileEntry(size, foffset, folder_name, fname)
            self._files[entry.path.lower()] = entry

    def _extract(self, entry: _FileEntry) -> bytes:
        f = self._file
        f.seek(entry.offset)

        # Check compression: bit 30 of size toggles the default
        is_compressed = self._compressed_by_default
        raw_size = entry.size
        if raw_size & 0x40000000:
            is_compressed = not is_compressed
            raw_size &= ~0x40000000

        # Embedded file name (SSE with flag 0x0100)
        if self._embed_file_names:
            bname_len = struct.unpack('<B', f.read(1))[0]
            f.read(bname_len)  # skip embedded name
            raw_size -= 1 + bname_len

        if is_compressed:
            original_size = struct.unpack('<I', f.read(4))[0]
            compressed_data = f.read(raw_size - 4)
            if self._is_sse:
                # SSE BSAs (v0x69) use LZ4 frame format (magic
                # 04224d18). Lazy-import so LE-only deployments don't
                # need the `lz4` wheel.
                try:
                    import lz4.frame
                except ImportError as e:
                    raise BsaError(
                        f"SSE BSA requires the `lz4` package to decompress "
                        f"{entry.path}: {e}")
                try:
                    return lz4.frame.decompress(compressed_data)
                except Exception as e:
                    raise BsaError(
                        f"LZ4 decompression failed for {entry.path}: {e}")
            try:
                return zlib.decompress(compressed_data)
            except zlib.error as e:
                raise BsaError(
                    f"zlib decompression failed for {entry.path}: {e}")
        else:
            return f.read(raw_size)
