"""Phase 1 Manual Test Script.

Generates test plugins and prints instructions for human validation
in xEdit, Creation Kit, and in-game.

Run from the esplib directory:
    python tests/manual/phase_1_manual.py
"""

import sys
import struct
from pathlib import Path

# Add parent dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from esplib import Plugin, Record, SubRecord, GroupRecord, FormID
from esplib.utils import BinaryWriter


OUTPUT_DIR = Path(__file__).parent.parent / 'output'


def generate_roundtrip_test():
    """Load Skyrim.esm if available, save a copy for xEdit comparison."""
    skyrim_paths = [
        Path(r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
        Path(r"D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
    ]

    esm_path = None
    for p in skyrim_paths:
        if p.exists():
            esm_path = p
            break

    if not esm_path:
        print("[SKIP] Skyrim.esm not found -- skipping round-trip test file generation")
        return False

    print(f"[....] Loading {esm_path}...")
    plugin = Plugin(esm_path)
    print(f"[OK  ] Loaded: {len(plugin.records)} records, "
          f"{len(plugin.groups)} groups, "
          f"localized={plugin.is_localized}")

    output_path = OUTPUT_DIR / 'Skyrim_roundtrip.esm'
    print(f"[....] Saving round-trip copy to {output_path}...")

    # Compare in memory first
    with open(esm_path, 'rb') as f:
        original = f.read()

    output = plugin.to_bytes()

    if output == original:
        print(f"[OK  ] Byte-perfect round-trip ({len(output):,} bytes)")
    else:
        print(f"[FAIL] Round-trip mismatch: original={len(original):,}, output={len(output):,}")
        # Find first difference
        for i in range(min(len(original), len(output))):
            if original[i] != output[i]:
                print(f"       First difference at offset 0x{i:08X}")
                break

    # Write the file for xEdit inspection
    with open(output_path, 'wb') as f:
        f.write(output)
    print(f"[OK  ] Written: {output_path}")

    return True


def generate_gmst_override():
    """Create a minimal plugin that overrides a single GMST."""
    plugin = Plugin()
    plugin.header.is_esm = False
    plugin.header.masters = ['Skyrim.esm']
    plugin.header.master_sizes = [0]
    plugin.header.version = 1.71

    # Override fJumpHeightMin (FormID 0x00066C5B in Skyrim.esm)
    gmst = Record('GMST', FormID(0x00066C5B), 0)
    gmst.timestamp = 0
    gmst.version = 44
    gmst.version_control_info = 0
    gmst.add_subrecord('EDID').set_string('fJumpHeightMin')
    # Set to a large value so it's obvious in-game
    data_sr = gmst.add_subrecord('DATA')
    data_sr.data = struct.pack('<f', 500.0)  # Super high jumps

    plugin.add_record(gmst)

    output_path = OUTPUT_DIR / 'esplib_gmst_test.esp'
    plugin.save(output_path)
    print(f"[OK  ] Generated: {output_path}")
    print(f"       Overrides fJumpHeightMin = 500.0 (should make jumps very high)")
    return True


def generate_stats():
    """Print some stats about Skyrim.esm if available."""
    skyrim_paths = [
        Path(r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
        Path(r"D:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
    ]

    esm_path = None
    for p in skyrim_paths:
        if p.exists():
            esm_path = p
            break

    if not esm_path:
        return

    plugin = Plugin(esm_path)

    compressed = sum(1 for r in plugin.records if r.is_compressed)
    print(f"\n--- Skyrim.esm Stats ---")
    print(f"Total records:      {len(plugin.records):,}")
    print(f"Compressed records: {compressed:,}")
    print(f"Groups:             {len(plugin.groups):,}")
    print(f"Masters:            {plugin.header.masters}")
    print(f"Version:            {plugin.header.version}")
    print(f"Localized:          {plugin.is_localized}")

    stats = plugin.get_statistics()
    print(f"\nRecord types (top 15):")
    sorted_types = sorted(stats['record_types'].items(), key=lambda x: -x[1])
    for sig, count in sorted_types[:15]:
        print(f"  {sig}: {count:,}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("=== MANUAL TEST: Phase 1 Round-Trip Fidelity ===")
    print("=" * 60)
    print()

    has_skyrim = generate_roundtrip_test()
    print()
    generate_gmst_override()

    if has_skyrim:
        generate_stats()

    # Build checklist
    lines = []
    lines.append("=" * 60)
    lines.append("PHASE 1 MANUAL TEST CHECKLIST")
    lines.append("=" * 60)
    lines.append("")

    step = 1
    if has_skyrim:
        lines.append(f"{step}. ROUND-TRIP CHECK (xEdit):")
        lines.append(f"   Open tests/output/Skyrim_roundtrip.esm in xEdit")
        lines.append(f"   alongside the original Skyrim.esm.")
        lines.append(f"   (Automated test confirmed byte-identical output;")
        lines.append(f"   this verifies xEdit can load it and fields display correctly.)")
        lines.append(f"   [ ] xEdit loads the round-tripped file without errors.")
        lines.append(f"   [ ] Spot-check a GMST record -- value matches original.")
        lines.append(f"   [ ] Spot-check a WEAP record -- all subrecords match.")
        lines.append(f"   [ ] Spot-check an NPC_ record -- stats and name match.")
        lines.append(f"   [ ] Spot-check an ARMO record -- all subrecords match.")
        lines.append(f"   [ ] Spot-check a compressed record (e.g. NAVM) -- data intact.")
        lines.append(f"   NOTE: Skyrim.esm is localized. String fields (FULL, DESC) will show")
        lines.append(f"   'No strings file for lstring ID ...' because the round-tripped file")
        lines.append(f"   is not in the Data directory where the .STRINGS files live. This is")
        lines.append(f"   expected. Verify the string IDs (hex values) match the original.")
        lines.append("")
        step += 1

    lines.append(f"{step}. GMST OVERRIDE CHECK (CK):")
    lines.append(f"   Open tests/output/esplib_gmst_test.esp in Creation Kit.")
    lines.append(f"   [ ] Should load without errors.")
    lines.append(f"   [ ] Find fJumpHeightMin in GameSettings, verify value = 500.0")
    lines.append("")
    step += 1

    lines.append(f"{step}. IN-GAME TEST:")
    lines.append(f"   Copy tests/output/esplib_gmst_test.esp to Skyrim Data folder.")
    lines.append(f"   Enable it in your load order. Launch Skyrim SE.")
    lines.append(f"   [ ] Game reaches main menu without crash.")
    lines.append(f"   [ ] Load a save, jump -- should jump extremely high.")
    lines.append(f"   (Remove the esp after testing!)")
    lines.append("")

    checklist = '\n'.join(lines)

    # Print to console
    print()
    print(checklist)

    # Write to file
    checklist_path = OUTPUT_DIR / 'phase_1_checklist.txt'
    with open(checklist_path, 'w') as f:
        f.write(checklist)
    print(f"[OK  ] Checklist written to: {checklist_path}")


if __name__ == '__main__':
    main()
