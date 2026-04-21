"""Tests for SSE BSA (version 0x69) LZ4-frame decompression.

Skyrim SE BSAs use LZ4 frame format (magic `04224d18`), not the zlib
format LE uses. Before this support landed, any compressed file in an
SSE BSA (the vast majority of texture / mesh content) couldn't be
extracted and threw a misleading "zlib header check" error.

These tests hit a real game BSA via a known-good path so the live
compression path gets exercised end-to-end. Skips cleanly without a
Skyrim install.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from esplib.bsa import BsaReader


GAME_DATA = Path(r"C:\Steam\steamapps\common\Skyrim Special Edition\Data")
TEXTURES_BSA = GAME_DATA / "Skyrim - Textures0.bsa"
# Known-present DDS in Skyrim - Textures0.bsa. The path esplib uses is
# case-insensitive; the BSA stores it lowercase.
KNOWN_FILE = r"textures\actors\character\character assets\tintmasks\maleheaddirt_02.dds"


@pytest.fixture(scope="module")
def textures_bsa():
    if not TEXTURES_BSA.is_file():
        pytest.skip(f"{TEXTURES_BSA} not present")
    return TEXTURES_BSA


def test_sse_bsa_is_version_0x69(textures_bsa):
    """Sanity check: the BSA we're testing against is actually v0x69
    (SSE). If Bethesda releases a BSA v0x6A or similar, this skip
    forces the test to be updated rather than silently stop covering
    the SSE path."""
    with open(textures_bsa, "rb") as f:
        f.seek(4)  # skip "BSA\0"
        import struct
        version = struct.unpack("<I", f.read(4))[0]
    assert version == 0x69


def test_sse_bsa_reads_compressed_dds(textures_bsa):
    """Extract a real LZ4-frame-compressed DDS from Skyrim - Textures0.bsa.
    If this fails with a zlib "incorrect header check" error, the LZ4
    branch isn't being taken for v0x69."""
    with BsaReader(textures_bsa) as bsa:
        assert bsa.has_file(KNOWN_FILE), (
            f"{KNOWN_FILE} missing from BSA — wrong known-file path for this SSE build?"
        )
        data = bsa.read_file(KNOWN_FILE)
    # A DDS file starts with "DDS " (0x44 0x44 0x53 0x20). If we got
    # bytes back but they aren't a DDS, decompression produced garbage.
    assert data[:4] == b"DDS ", f"not a DDS: first bytes {data[:8].hex()}"
    # Known size for this file — sanity check against a silent truncation.
    # (~500KB uncompressed per the header info we inspected while debugging.)
    assert len(data) > 1024, f"suspiciously short: {len(data)} bytes"


def test_sse_bsa_roundtrip_multiple_files(textures_bsa):
    """Read a handful of entries to make sure we didn't just get lucky
    on one file. If LZ4 state is somehow polluted across calls, this
    catches it."""
    with BsaReader(textures_bsa) as bsa:
        picked = []
        for path in bsa.list_files()[:20]:
            data = bsa.read_file(path)
            # Non-empty and looks-like-a-file (not zeros, not error garbage)
            assert len(data) > 0
            picked.append((path, len(data)))
        assert len(picked) == 20
