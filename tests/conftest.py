"""Shared test fixtures for esplib tests."""

import struct
import zlib
import pytest
from pathlib import Path

from esplib.game_discovery import (
    find_game_data, find_game_file, find_strings_dir,
)


def find_skyrim_data() -> Path | None:
    """Find Skyrim SE Data directory. Convenience alias for tests."""
    return find_game_data('tes5')


def find_skyrim_esm() -> Path | None:
    """Find Skyrim.esm. Convenience alias for tests."""
    return find_game_file('Skyrim.esm', 'tes5')


@pytest.fixture(scope="session")
def skyrim_plugin():
    """Skyrim.esm loaded once per session.

    When running from the workspace root, the root conftest provides this
    fixture instead (shared across esplib and furrifier tests).
    """
    from esplib import Plugin
    esm_path = find_skyrim_esm()
    assert esm_path, "Skyrim.esm not found"
    strings_dir = find_strings_dir()
    assert strings_dir, "String tables not found"
    p = Plugin()
    p.string_search_dirs = [str(strings_dir)]
    p.load(esm_path)
    return p


# --- Binary helpers for building synthetic plugin data ---

def make_subrecord(sig: str, data: bytes) -> bytes:
    """Build a raw subrecord: sig(4) + size(2) + data."""
    return sig.encode('ascii') + struct.pack('<H', len(data)) + data


def make_xxxx_subrecord(sig: str, data: bytes) -> bytes:
    """Build a subrecord using XXXX overflow."""
    xxxx = b'XXXX' + struct.pack('<H', 4) + struct.pack('<I', len(data))
    actual = sig.encode('ascii') + struct.pack('<H', 0) + data
    return xxxx + actual


def make_record(sig: str, form_id: int, flags: int, subrecord_bytes: bytes,
                timestamp: int = 0x12345678, version: int = 44,
                vci: int = 0xABCD) -> bytes:
    """Build a raw record with header."""
    if flags & 0x00040000:
        # Compressed: prepend uncompressed size, then compress
        uncompressed_size = struct.pack('<I', len(subrecord_bytes))
        compressed = zlib.compress(subrecord_bytes)
        payload = uncompressed_size + compressed
    else:
        payload = subrecord_bytes

    header = sig.encode('ascii')
    header += struct.pack('<I', len(payload))
    header += struct.pack('<I', flags)
    header += struct.pack('<I', form_id)
    header += struct.pack('<I', timestamp)
    header += struct.pack('<H', version)
    header += struct.pack('<H', vci)
    return header + payload


def make_group(label: str, group_type: int, content: bytes,
               timestamp: int = 0x11223344, version: int = 0,
               vci: int = 0) -> bytes:
    """Build a raw GRUP."""
    size = 24 + len(content)
    header = b'GRUP'
    header += struct.pack('<I', size)
    header += label.encode('ascii')[:4].ljust(4, b'\x00')
    header += struct.pack('<i', group_type)
    header += struct.pack('<I', timestamp)
    header += struct.pack('<H', version)
    header += struct.pack('<H', vci)
    return header + content


def make_tes4_record(flags: int = 0, masters: list[str] | None = None,
                     version: float = 1.71, num_records: int = 0,
                     next_object_id: int = 0x800) -> bytes:
    """Build a minimal TES4 header record."""
    subs = bytearray()

    # HEDR
    hedr_data = struct.pack('<f', version)
    hedr_data += struct.pack('<I', num_records)
    hedr_data += struct.pack('<I', next_object_id)
    subs.extend(make_subrecord('HEDR', hedr_data))

    # Masters
    if masters:
        for master in masters:
            encoded = master.encode('cp1252') + b'\x00'
            subs.extend(make_subrecord('MAST', encoded))
            subs.extend(make_subrecord('DATA', struct.pack('<Q', 0)))

    return make_record('TES4', 0, flags, bytes(subs), timestamp=0, version=44, vci=0)


def make_simple_plugin(records: list[tuple[str, int, bytes]] | None = None,
                       tes4_flags: int = 0,
                       masters: list[str] | None = None) -> bytes:
    """Build a complete synthetic plugin with optional records.

    records: list of (signature, form_id, subrecord_bytes) tuples.
    All records of the same signature are grouped together.
    """
    plugin_data = bytearray()

    num_records = len(records) if records else 0
    plugin_data.extend(make_tes4_record(
        flags=tes4_flags, masters=masters, num_records=num_records))

    if records:
        # Group records by signature
        groups: dict[str, list[bytes]] = {}
        for sig, fid, sub_bytes in records:
            rec = make_record(sig, fid, 0, sub_bytes)
            groups.setdefault(sig, []).append(rec)

        for sig, recs in groups.items():
            content = b''.join(recs)
            plugin_data.extend(make_group(sig, 0, content))

    return bytes(plugin_data)
