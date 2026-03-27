"""Phase 3 Manual Test Script.

Creates test plugins using the schema definitions and prints
instructions for human validation in xEdit, CK, and in-game.
"""

import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from esplib import Plugin, Record, SubRecord, FormID
from esplib.utils import BinaryWriter
from esplib.defs import tes5, GameRegistry


OUTPUT_DIR = Path(__file__).parent.parent / 'output'


def generate_weapon_test():
    """Create a plugin with a new weapon built using WEAP schema knowledge."""
    plugin = Plugin()
    plugin.header.is_esm = False
    plugin.header.masters = ['Skyrim.esm']
    plugin.header.master_sizes = [0]
    plugin.header.version = 1.71

    # file_index = number of masters (1), so our records start at 0x01000800
    weap = Record('WEAP', FormID(0x01000800), 0)
    weap.timestamp = 0
    weap.version = 44
    weap.version_control_info = 0

    # Subrecords MUST be in xEdit's expected definition order.
    # WEAP order: EDID, VMAD, OBND, FULL, MODL, ICON, EITM, ETYP, BIDS,
    #             BAMT, YNAM, ZNAM, KSIZ, KWDA, DESC, ..., DATA, DNAM, CRDT,
    #             VNAM, CNAM

    weap.add_subrecord('EDID', b'esplib_TestSword\x00')
    weap.add_subrecord('OBND', struct.pack('<6h', -10, -1, -10, 10, 30, 10))
    weap.add_subrecord('FULL', b'Esplib Test Sword\x00')
    weap.add_subrecord('DESC', b'A test weapon created by esplib.\x00')

    # DATA: value=100, weight=5.0, damage=50
    weap.add_subrecord('DATA',
                       struct.pack('<I', 100) +
                       struct.pack('<f', 5.0) +
                       struct.pack('<H', 50))

    # DNAM: weapon data (100 bytes in SSE)
    dnam = bytearray(100)
    struct.pack_into('<B', dnam, 0, 1)     # animation_type = OneHandSword
    struct.pack_into('<f', dnam, 4, 1.0)   # speed
    struct.pack_into('<f', dnam, 8, 0.7)   # reach
    weap.add_subrecord('DNAM', bytes(dnam))

    # CRDT: critical data (24 bytes for SSE)
    crdt = bytearray(24)
    struct.pack_into('<H', crdt, 0, 10)    # crit damage
    struct.pack_into('<f', crdt, 4, 1.0)   # crit % mult
    weap.add_subrecord('CRDT', bytes(crdt))

    # VNAM: detection sound level = Normal (1)
    weap.add_subrecord('VNAM', struct.pack('<I', 1))

    plugin.add_record(weap)

    output_path = OUTPUT_DIR / 'esplib_weapon_test.esp'
    plugin.save(output_path)
    print(f"[OK  ] Generated: {output_path}")
    print(f"       Weapon: 'Esplib Test Sword' (damage=50, value=100, weight=5.0)")
    return True


def generate_armor_test():
    """Create a plugin with a new armor piece."""
    plugin = Plugin()
    plugin.header.is_esm = False
    plugin.header.masters = ['Skyrim.esm']
    plugin.header.master_sizes = [0]
    plugin.header.version = 1.71

    armo = Record('ARMO', FormID(0x01000800), 0)
    armo.timestamp = 0
    armo.version = 44
    armo.version_control_info = 0

    # ARMO order: EDID, VMAD, OBND, FULL, ..., BOD2, ..., RNAM, ..., DESC, ..., DATA, DNAM
    armo.add_subrecord('EDID', b'esplib_TestArmor\x00')
    armo.add_subrecord('OBND', struct.pack('<6h', -15, -5, -15, 15, 30, 15))
    armo.add_subrecord('FULL', b'Esplib Test Armor\x00')
    armo.add_subrecord('BOD2', struct.pack('<II', 0x00000004, 1))  # body, heavy armor
    armo.add_subrecord('RNAM', struct.pack('<I', 0x00013746))      # Nord race
    armo.add_subrecord('DESC', b'Test armor created by esplib.\x00')
    armo.add_subrecord('DATA', struct.pack('<if', 200, 35.0))
    # Armor rating stored as display value x100 (3000 = 30.0 in-game)
    armo.add_subrecord('DNAM', struct.pack('<i', 3000))

    plugin.add_record(armo)

    output_path = OUTPUT_DIR / 'esplib_armor_test.esp'
    plugin.save(output_path)
    print(f"[OK  ] Generated: {output_path}")
    print(f"       Armor: 'Esplib Test Armor' (rating=30, value=200, weight=35.0)")
    return True


def generate_potion_test():
    """Create a plugin with a new potion."""
    plugin = Plugin()
    plugin.header.is_esm = False
    plugin.header.masters = ['Skyrim.esm']
    plugin.header.master_sizes = [0]
    plugin.header.version = 1.71

    alch = Record('ALCH', FormID(0x01000800), 0)
    alch.timestamp = 0
    alch.version = 44
    alch.version_control_info = 0

    # ALCH order: EDID, OBND, FULL, KWDA, DESC, MODL, ..., ETYP, DATA, ENIT, effects
    alch.add_subrecord('EDID', b'esplib_TestPotion\x00')
    alch.add_subrecord('OBND', struct.pack('<6h', -3, -3, -7, 3, 3, 7))
    alch.add_subrecord('FULL', b'Esplib Test Potion\x00')
    alch.add_subrecord('DESC', b'A test potion from esplib.\x00')

    # DATA: weight=0.5
    alch.add_subrecord('DATA', struct.pack('<f', 0.5))

    # ENIT: value=50, flags=0 (no auto-calc), no addiction, no sound
    enit = struct.pack('<i', 50)       # value
    enit += struct.pack('<I', 0)       # flags
    enit += struct.pack('<I', 0)       # addiction (none)
    enit += struct.pack('<f', 0.0)     # addiction chance
    enit += struct.pack('<I', 0)       # sound consume (none)
    alch.add_subrecord('ENIT', enit)

    # Effect: Restore Health (0x0003EB15 in Skyrim.esm)
    alch.add_subrecord('EFID', struct.pack('<I', 0x0003EB15))
    # EFIT: magnitude=50, area=0, duration=0
    alch.add_subrecord('EFIT', struct.pack('<fII', 50.0, 0, 0))

    plugin.add_record(alch)

    output_path = OUTPUT_DIR / 'esplib_potion_test.esp'
    plugin.save(output_path)
    print(f"[OK  ] Generated: {output_path}")
    print(f"       Potion: 'Esplib Test Potion' (Restore Health 50pts, value=50)")
    return True


def validate_against_skyrim():
    """Load Skyrim.esm and resolve some records to show field values."""
    skyrim_paths = [
        Path(r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm"),
    ]
    esm_path = None
    for p in skyrim_paths:
        if p.exists():
            esm_path = p
            break
    if not esm_path:
        print("[SKIP] Skyrim.esm not found -- skipping field validation")
        return

    print(f"[....] Loading {esm_path}...")
    plugin = Plugin(esm_path)

    # Resolve Iron Sword
    iron_sword = plugin.get_record_by_editor_id('IronSword')
    if iron_sword:
        result = tes5.WEAP.from_record(iron_sword)
        data = result.get('Game Data', {})
        print(f"[OK  ] IronSword: damage={data.get('damage')}, "
              f"value={data.get('value')}, weight={data.get('weight')}")
    else:
        print("[WARN] IronSword not found (may be localized EDID)")

    # Resolve Iron Armor
    iron_armor = plugin.get_record_by_editor_id('ArmorIronCuirass')
    if iron_armor:
        result = tes5.ARMO.from_record(iron_armor)
        data = result.get('Data', {})
        rating = result.get('Armor Rating', '?')
        print(f"[OK  ] ArmorIronCuirass: value={data.get('value')}, "
              f"weight={data.get('weight')}, rating={rating}")

    # Count how many WEAP records resolve without error
    weapons = plugin.get_records_by_signature('WEAP')
    errors = 0
    for w in weapons:
        try:
            tes5.WEAP.from_record(w)
        except Exception:
            errors += 1
    print(f"[OK  ] Resolved {len(weapons)} WEAP records, {errors} errors")

    armors = plugin.get_records_by_signature('ARMO')
    errors = 0
    for a in armors:
        try:
            tes5.ARMO.from_record(a)
        except Exception:
            errors += 1
    print(f"[OK  ] Resolved {len(armors)} ARMO records, {errors} errors")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("=== MANUAL TEST: Phase 3 Record Definitions ===")
    print("=" * 60)
    print()

    generate_weapon_test()
    generate_armor_test()
    generate_potion_test()
    print()
    validate_against_skyrim()

    # Build checklist
    lines = []
    lines.append("=" * 60)
    lines.append("PHASE 3 MANUAL TEST CHECKLIST")
    lines.append("=" * 60)
    lines.append("")

    lines.append("1. WEAPON CHECK (xEdit + CK + in-game):")
    lines.append("   Open tests/output/esplib_weapon_test.esp in xEdit.")
    lines.append("   [ ] WEAP record 'esplib_TestSword' exists with correct subrecords.")
    lines.append("   [ ] DATA shows: value=100, weight=5.0, damage=50.")
    lines.append("   [ ] DNAM shows: animation_type=OneHandSword, speed=1.0, reach=0.7.")
    lines.append("   Copy to Skyrim Data folder, enable in load order.")
    lines.append("   [ ] Game reaches main menu without crash.")
    lines.append("   [ ] Console: help \"Esplib Test\" -> finds the sword.")
    lines.append("   [ ] player.additem <id> 1 -> sword appears in inventory.")
    lines.append("   [ ] Sword shows correct name, damage (50), value (100).")
    lines.append("")

    lines.append("2. ARMOR CHECK (xEdit + in-game):")
    lines.append("   Open tests/output/esplib_armor_test.esp in xEdit.")
    lines.append("   [ ] ARMO record 'esplib_TestArmor' has correct fields.")
    lines.append("   [ ] DATA: value=200, weight=35.0. DNAM: rating=30.")
    lines.append("   Copy to Skyrim Data folder, enable.")
    lines.append("   [ ] Console: help \"Esplib Test Armor\" -> finds it.")
    lines.append("   [ ] player.additem -> armor appears with correct stats.")
    lines.append("")

    lines.append("3. POTION CHECK (xEdit + in-game):")
    lines.append("   Open tests/output/esplib_potion_test.esp in xEdit.")
    lines.append("   [ ] ALCH record 'esplib_TestPotion' has correct fields.")
    lines.append("   [ ] ENIT: value=50. EFID: Restore Health. EFIT: magnitude=50.")
    lines.append("   Copy to Skyrim Data folder, enable.")
    lines.append("   [ ] Console: help \"Esplib Test Potion\" -> finds it.")
    lines.append("   [ ] player.additem -> potion appears, restores health when used.")
    lines.append("")

    lines.append("4. FIELD COMPARISON (xEdit):")
    lines.append("   Load Skyrim.esm in xEdit. Pick these records and compare")
    lines.append("   field values against esplib's resolve output (printed above):")
    lines.append("   [ ] IronSword (WEAP) -- damage, value, weight match.")
    lines.append("   [ ] ArmorIronCuirass (ARMO) -- value, weight, rating match.")
    lines.append("   [ ] A FACT record -- flags decode correctly.")
    lines.append("   [ ] An NPC_ record -- level, race FormID match.")
    lines.append("")

    lines.append("(Remove test .esp files from Data folder after testing!)")

    checklist = '\n'.join(lines)
    print()
    print(checklist)

    checklist_path = OUTPUT_DIR / 'phase_3_checklist.txt'
    with open(checklist_path, 'w') as f:
        f.write(checklist)
    print(f"\n[OK  ] Checklist written to: {checklist_path}")


if __name__ == '__main__':
    main()
