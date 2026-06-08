"""BA2 archive reading for Fallout 4 (and compatible Starfield archives).

Minimal reader focused on extracting files (especially string tables and
loose-equivalent assets) from Bethesda BA2 archives. Mirrors the public
API of :class:`esplib.bsa.BsaReader` so callers can treat the two
interchangeably:

    with Ba2Reader("Fallout4 - Interface.ba2") as ba2:
        data = ba2.read_file("strings/fallout4_en.strings")

Two archive types exist:
  - GNRL: general files (meshes, strings, scripts, …). Stored verbatim or
    zlib-compressed. Fully supported here.
  - DX10: textures, stored as a per-texture header plus chunked, individually
    zlib-compressed mip data with no on-disk DDS header. We index them and
    reconstruct a valid DDS on extract: a DX10-extended header (built from the
    texture header's width/height/mip-count/DXGI-format) followed by the
    decompressed mip chunks concatenated in order. PIL and PyNifly can then
    open the result by path like any loose .dds.
"""

import struct
import zlib
import logging
from pathlib import Path
from typing import Dict, List, Optional

_log = logging.getLogger(__name__)

# --- DDS header reconstruction for DX10 textures ---------------------------
_DDS_MAGIC = b"DDS "
_DDSD_CAPS = 0x1
_DDSD_HEIGHT = 0x2
_DDSD_WIDTH = 0x4
_DDSD_PIXELFORMAT = 0x1000
_DDSD_PITCH = 0x8
_DDSD_LINEARSIZE = 0x80000
_DDSD_MIPMAPCOUNT = 0x20000
_DDSCAPS_TEXTURE = 0x1000
_DDSCAPS_COMPLEX = 0x8
_DDSCAPS_MIPMAP = 0x400000
_DDPF_FOURCC = 0x4
_D3D10_RESOURCE_DIMENSION_TEXTURE2D = 3

# DXGI_FORMAT -> bytes per 4x4 block, for the block-compressed formats. BC1
# and BC4 pack a block in 8 bytes; every other BC format uses 16.
_BC_BLOCK_BYTES = {
    70: 8, 71: 8, 72: 8,            # BC1 (typeless/unorm/srgb)
    73: 16, 74: 16, 75: 16,         # BC2
    76: 16, 77: 16, 78: 16,         # BC3
    79: 8, 80: 8, 81: 8,            # BC4
    82: 16, 83: 16, 84: 16,         # BC5
    94: 16, 95: 16, 96: 16,         # BC6H
    97: 16, 98: 16, 99: 16,         # BC7
}

# DXGI_FORMAT -> bytes per pixel, for the uncompressed formats FO4 textures
# occasionally use (face/body maps are almost always BC, but be complete).
_UNCOMPRESSED_BPP = {
    2: 16, 10: 8,                   # R32G32B32A32, R16G16B16A16
    28: 4, 29: 4,                   # R8G8B8A8 (unorm/srgb)
    87: 4, 88: 4, 91: 4,           # B8G8R8A8 / B8G8R8X8 variants
    49: 2, 61: 1, 80: 1,           # R8G8, R8, A8 (80 is BC4 above; A8 is 65)
    65: 1,                          # A8_UNORM
}


def _build_dx10_dds_header(width: int, height: int, num_mips: int,
                           dxgi_format: int) -> bytes:
    """Construct a DDS magic + DDS_HEADER + DDS_HEADER_DXT10 prefix for a
    texture of the given dimensions/format. Mirrors the writer in the
    furrifier's facegen.dds but parameterized on the DXGI format and mip
    count read back from the BA2 texture header."""
    num_mips = max(1, num_mips)
    block_bytes = _BC_BLOCK_BYTES.get(dxgi_format)
    if block_bytes is not None:
        # Compressed: pitchOrLinearSize = total bytes of the top mip.
        blocks_w = max(1, (width + 3) // 4)
        blocks_h = max(1, (height + 3) // 4)
        pitch_or_linear = blocks_w * blocks_h * block_bytes
        flags = (_DDSD_CAPS | _DDSD_HEIGHT | _DDSD_WIDTH
                 | _DDSD_PIXELFORMAT | _DDSD_LINEARSIZE)
    else:
        # Uncompressed: pitchOrLinearSize = bytes in one scanline.
        bpp = _UNCOMPRESSED_BPP.get(dxgi_format, 4)
        pitch_or_linear = width * bpp
        flags = (_DDSD_CAPS | _DDSD_HEIGHT | _DDSD_WIDTH
                 | _DDSD_PIXELFORMAT | _DDSD_PITCH)

    caps1 = _DDSCAPS_TEXTURE
    if num_mips > 1:
        flags |= _DDSD_MIPMAPCOUNT
        caps1 |= _DDSCAPS_COMPLEX | _DDSCAPS_MIPMAP

    pixelformat = struct.pack(
        "<I I 4s I I I I I",
        32, _DDPF_FOURCC, b"DX10", 0, 0, 0, 0, 0)
    header = struct.pack(
        "<I I I I I I I 11I 32s 5I",
        124, flags, height, width, pitch_or_linear, 0, num_mips,
        *([0] * 11), pixelformat, caps1, 0, 0, 0, 0)
    dxt10 = struct.pack(
        "<I I I I I",
        dxgi_format, _D3D10_RESOURCE_DIMENSION_TEXTURE2D, 0, 1, 0)
    return _DDS_MAGIC + header + dxt10


class _Ba2Entry:
    """Metadata for a single file in a BA2 archive."""

    def __init__(self):
        self.name_hash = 0
        self.ext = ""
        self.dir_hash = 0
        self.offset = 0
        self.packed_size = 0
        self.unpacked_size = 0
        self.name = ""  # full in-archive path, set from the name table
        # DX10 texture fields (unused for GNRL entries).
        self.is_dx10 = False
        self.dx10_width = 0
        self.dx10_height = 0
        self.dx10_num_mips = 0
        self.dx10_format = 0
        self.chunks: List[tuple] = []  # (offset, packed_size, unpacked_size)

    def __repr__(self):
        return f"_Ba2Entry({self.name!r})"


class Ba2Reader:
    """Reads Bethesda BA2 archives (Fallout 4).

    Usage:
        with Ba2Reader("Fallout4 - Interface.ba2") as ba2:
            data = ba2.read_file("strings/fallout4_en.strings")
    """

    def __init__(self, path):
        self.path = Path(path)
        self._file = None
        self.archive_type: Optional[str] = None  # 'GNRL' or 'DX10'
        self._version = None
        self._entries: List[_Ba2Entry] = []
        self._by_name: Dict[str, _Ba2Entry] = {}


    def __enter__(self):
        self.open()
        return self


    def __exit__(self, *args):
        self.close()


    def open(self):
        self._file = open(self.path, 'rb')
        self._read_index()
        return self


    def close(self):
        if self._file:
            self._file.close()
            self._file = None


    def _read_index(self):
        f = self._file
        magic = f.read(4)
        if magic != b'BTDX':
            raise ValueError(f"Not a BA2 file: {self.path}")

        self._version = struct.unpack('<I', f.read(4))[0]
        archive_type = f.read(4)
        self.archive_type = archive_type.decode('ascii', 'replace').rstrip('\x00')
        file_count = struct.unpack('<I', f.read(4))[0]
        name_table_offset = struct.unpack('<Q', f.read(8))[0]

        if self.archive_type == 'GNRL':
            self._read_gnrl(f, file_count)
        elif self.archive_type == 'DX10':
            self._read_dx10(f, file_count)
        else:
            raise ValueError(
                f"Unknown BA2 type {self.archive_type!r}: {self.path}")

        self._read_name_table(f, name_table_offset, file_count)


    def _read_gnrl(self, f, file_count):
        # GNRL entry: name_hash(4) ext(4) dir_hash(4) flags(4)
        #             offset(8) packed_size(4) unpacked_size(4) align(4)
        for _ in range(file_count):
            name_hash = struct.unpack('<I', f.read(4))[0]
            ext = f.read(4)
            dir_hash = struct.unpack('<I', f.read(4))[0]
            _flags = struct.unpack('<I', f.read(4))[0]
            offset = struct.unpack('<Q', f.read(8))[0]
            packed_size = struct.unpack('<I', f.read(4))[0]
            unpacked_size = struct.unpack('<I', f.read(4))[0]
            _align = struct.unpack('<I', f.read(4))[0]
            entry = _Ba2Entry()
            entry.name_hash = name_hash
            entry.ext = ext.decode('ascii', 'replace').rstrip('\x00')
            entry.dir_hash = dir_hash
            entry.offset = offset
            entry.packed_size = packed_size
            entry.unpacked_size = unpacked_size
            self._entries.append(entry)


    def _read_dx10(self, f, file_count):
        # DX10 entry header (24 bytes) then chunk_count chunks (24 bytes each).
        # We record the texture header (width/height/mips/format) and every
        # chunk so _extract can rebuild a valid DDS (see module docstring).
        for _ in range(file_count):
            name_hash = struct.unpack('<I', f.read(4))[0]
            ext = f.read(4)
            dir_hash = struct.unpack('<I', f.read(4))[0]
            _unk = f.read(1)
            chunk_count = f.read(1)[0]
            _chunk_hdr_size = struct.unpack('<H', f.read(2))[0]
            height = struct.unpack('<H', f.read(2))[0]
            width = struct.unpack('<H', f.read(2))[0]
            num_mips = f.read(1)[0]
            fmt = f.read(1)[0]
            _unk2 = f.read(2)  # isCubemap(u8) + tileMode(u8) — unused here
            entry = _Ba2Entry()
            entry.name_hash = name_hash
            entry.ext = ext.decode('ascii', 'replace').rstrip('\x00')
            entry.dir_hash = dir_hash
            entry.is_dx10 = True
            entry.dx10_width = width
            entry.dx10_height = height
            entry.dx10_num_mips = num_mips
            entry.dx10_format = fmt
            for ci in range(chunk_count):
                ch_offset = struct.unpack('<Q', f.read(8))[0]
                ch_packed = struct.unpack('<I', f.read(4))[0]
                ch_unpacked = struct.unpack('<I', f.read(4))[0]
                _start_mip = struct.unpack('<H', f.read(2))[0]
                _end_mip = struct.unpack('<H', f.read(2))[0]
                _ch_align = struct.unpack('<I', f.read(4))[0]
                entry.chunks.append((ch_offset, ch_packed, ch_unpacked))
                if ci == 0:
                    entry.offset = ch_offset
                    entry.packed_size = ch_packed
                    entry.unpacked_size = ch_unpacked
            self._entries.append(entry)


    def _read_name_table(self, f, offset, file_count):
        f.seek(offset)
        for i in range(file_count):
            if i >= len(self._entries):
                break
            len_bytes = f.read(2)
            if len(len_bytes) < 2:
                break
            name_len = struct.unpack('<H', len_bytes)[0]
            name = f.read(name_len).decode('cp1252', 'replace')
            self._entries[i].name = name
            self._by_name[_norm(name)] = self._entries[i]


    def list_files(self) -> List[str]:
        """Return every in-archive file path."""
        return [e.name for e in self._entries]


    def has_file(self, path: str) -> bool:
        """True if the given path exists in the archive (case-insensitive)."""
        return _norm(path) in self._by_name


    def read_file(self, path: str) -> Optional[bytes]:
        """Extract a file by its archive path (e.g. 'strings/foo.strings').

        Matching is case-insensitive and slash-insensitive. Returns None if
        not found. GNRL files are fully decompressed; DX10 entries are
        reassembled into a complete DX10-headered DDS (see module docstring).
        """
        entry = self._by_name.get(_norm(path))
        if entry is None:
            return None
        if entry.is_dx10:
            return self._extract_dx10(entry)
        return self._extract(entry)


    def _extract(self, entry: _Ba2Entry) -> bytes:
        f = self._file
        f.seek(entry.offset)
        size = entry.packed_size or entry.unpacked_size
        raw = f.read(size)
        # Compressed when a non-zero packed size differs from unpacked.
        if entry.packed_size and entry.packed_size != entry.unpacked_size:
            return zlib.decompress(raw)
        return raw


    def _extract_dx10(self, entry: _Ba2Entry) -> bytes:
        """Rebuild a DDS for a DX10 texture: header reconstructed from the
        texture metadata, body = the decompressed mip chunks concatenated in
        archive order (largest mip first)."""
        f = self._file
        body = bytearray()
        for offset, packed, unpacked in entry.chunks:
            f.seek(offset)
            size = packed or unpacked
            raw = f.read(size)
            if packed and packed != unpacked:
                raw = zlib.decompress(raw)
            body += raw
        header = _build_dx10_dds_header(
            entry.dx10_width, entry.dx10_height,
            entry.dx10_num_mips, entry.dx10_format)
        return bytes(header) + bytes(body)


    def __repr__(self):
        return f"Ba2Reader({self.path}, type={self.archive_type})"


def _norm(path: str) -> str:
    """Normalize an archive path for case/slash-insensitive matching."""
    return path.replace('/', '\\').lower()
