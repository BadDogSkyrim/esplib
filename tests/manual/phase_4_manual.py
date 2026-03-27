"""Phase 4 Manual Test Script.

Demonstrates the typed access API by loading Skyrim.esm, reading and
modifying records via record['SIG']['field'] syntax, and creating a
test plugin with modified weapons.
"""

import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from esplib import Plugin, Record, SubRecord, FormID
import esplib.defs.tes5 as tes5


OUTPUT_DIR = Path(__file__).parent.parent / 'output'


def demo_typed_access():
    """Load Skyrim.esm and demonstrate typed field access."""
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
        print("[SKIP] Skyrim.esm not found")
        return False

    print(f"[....] Loading {esm_path}...")
    plugin = Plugin(esm_path)
    plugin.set_game('tes5')
    print(f"[OK  ] Loaded with schemas bound")

    # Read weapon fields
    iron_sword = plugin.get_record_by_editor_id('IronSword')
    if iron_sword:
        data = iron_sword['DATA']
        print(f"[OK  ] IronSword['DATA'] = {data}")
        print(f"       damage={data['damage']}, value={data['value']}, weight={data['weight']}")

        dnam = iron_sword['DNAM']
        if dnam:
            print(f"       speed={dnam['speed']}, reach={dnam['reach']}")
    else:
        print("[WARN] IronSword not found")

    # Read armor fields
    iron_armor = plugin.get_record_by_editor_id('ArmorIronCuirass')
    if iron_armor:
        data = iron_armor['DATA']
        rating = iron_armor['DNAM']
        print(f"[OK  ] ArmorIronCuirass['DATA'] = {data}")
        print(f"       Armor Rating (raw) = {rating}")

    # Read NPC fields
    npcs = plugin.get_records_by_signature('NPC_')
    for npc in npcs[:50]:
        if npc.get_subrecord('ACBS') and npc.editor_id:
            acbs = npc['ACBS']
            if acbs:
                print(f"[OK  ] {npc.editor_id}['ACBS'] level={acbs['level']}, "
                      f"flags=0x{acbs['flags']:08X}")
                break

    # Read a weapon with CNAM (template)
    axe = plugin.get_record_by_editor_id('EnchSteelWarAxeStamina2')
    if axe:
        cnam = axe['CNAM']
        data = axe['DATA']
        print(f"[OK  ] EnchSteelWarAxeStamina2['CNAM'] (template) = {cnam}")
        print(f"       DATA: value={data['value']}, damage={data['damage']}")
    else:
        print("[WARN] EnchSteelWarAxeStamina2 not found")

    return True


def generate_modified_weapon():
    """Create a plugin that overrides IronSword with boosted damage."""
    plugin = Plugin()
    plugin.header.is_esm = False
    plugin.header.masters = ['Skyrim.esm']
    plugin.header.master_sizes = [0]
    plugin.header.version = 1.71

    # IronSword FormID in Skyrim.esm = 0x00012EB7
    # Master index 0 = Skyrim.esm, so FormID stays 0x00012EB7
    weap = Record('WEAP', FormID(0x00012EB7), 0)
    weap.timestamp = 0
    weap.version = 44
    weap.version_control_info = 0
    weap.schema = tes5.WEAP

    # Order must match real WEAP: EDID, OBND, FULL, ..., DESC, ...,
    # DATA, DNAM, CRDT, VNAM, CNAM
    weap.add_subrecord('EDID', b'IronSword\x00')
    weap.add_subrecord('OBND', struct.pack('<6h', -7, -1, -25, 8, 27, 25))
    weap.add_subrecord('FULL', b'Esplib Mega Sword\x00')
    weap.add_subrecord('DESC', b'An absurdly powerful Iron Sword, modified by esplib.\x00')

    # Use typed access to set DATA
    weap['DATA'] = {'value': 9999, 'weight': 5.0, 'damage': 100}

    # DNAM: OneHandSword, speed=1.3, reach=1.0
    dnam = bytearray(100)
    struct.pack_into('<B', dnam, 0, 1)     # OneHandSword
    struct.pack_into('<f', dnam, 4, 1.3)   # speed
    struct.pack_into('<f', dnam, 8, 1.0)   # reach
    weap.add_subrecord('DNAM', bytes(dnam))

    crdt = bytearray(24)
    weap.add_subrecord('CRDT', bytes(crdt))
    weap.add_subrecord('VNAM', struct.pack('<I', 1))  # Normal detection level

    plugin.add_record(weap)

    # Also override EnchSteelWarAxeStamina2 (has CNAM template)
    # FormID = 0x000139A3 in Skyrim.esm
    axe = Record('WEAP', FormID(0x000139A3), 0)
    axe.timestamp = 0
    axe.version = 44
    axe.version_control_info = 0
    axe.schema = tes5.WEAP

    axe.add_subrecord('EDID', b'EnchSteelWarAxeStamina2\x00')
    axe.add_subrecord('OBND', struct.pack('<6h', -7, -1, -25, 8, 27, 25))
    axe.add_subrecord('FULL', b'Esplib Mega Axe\x00')
    axe.add_subrecord('DESC', b'A stupidly powerful axe with a template reference.\x00')
    axe['DATA'] = {'value': 5555, 'weight': 8.0, 'damage': 75}
    dnam2 = bytearray(100)
    struct.pack_into('<B', dnam2, 0, 3)     # OneHandAxe
    struct.pack_into('<f', dnam2, 4, 1.0)   # speed
    struct.pack_into('<f', dnam2, 8, 0.7)   # reach
    axe.add_subrecord('DNAM', bytes(dnam2))
    axe.add_subrecord('CRDT', bytearray(24))
    axe.add_subrecord('VNAM', struct.pack('<I', 1))
    # CNAM: template = SteelWarAxe [WEAP:00013983]
    axe.add_subrecord('CNAM', struct.pack('<I', 0x00013983))

    plugin.add_record(axe)

    output_path = OUTPUT_DIR / 'esplib_modify_test.esp'
    plugin.save(output_path)
    print(f"[OK  ] Generated: {output_path}")
    print(f"       Overrides IronSword: damage=100, value=9999, name='Esplib Mega Sword'")
    print(f"       Overrides EnchSteelWarAxeStamina2: damage=75, value=5555, template=SteelWarAxe")

    # Verify by re-loading and using typed access
    verify = Plugin(output_path)
    verify.set_game('tes5')
    sword = verify.get_record_by_editor_id('IronSword')
    data = sword['DATA']
    print(f"[OK  ] Verified IronSword: damage={data['damage']}, value={data['value']}")
    axe_v = verify.get_record_by_editor_id('EnchSteelWarAxeStamina2')
    data2 = axe_v['DATA']
    cnam = axe_v['CNAM']
    print(f"[OK  ] Verified Axe: damage={data2['damage']}, value={data2['value']}, template={cnam}")
    return True


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("=== MANUAL TEST: Phase 4 Typed Record Access ===")
    print("=" * 60)
    print()

    has_skyrim = demo_typed_access()
    print()
    generate_modified_weapon()

    lines = []
    lines.append("=" * 60)
    lines.append("PHASE 4 MANUAL TEST CHECKLIST")
    lines.append("=" * 60)
    lines.append("")

    lines.append("1. MODIFIED WEAPONS CHECK (xEdit):")
    lines.append("   Open tests/output/esplib_modify_test.esp in xEdit with Skyrim.esm.")
    lines.append("   [ ] IronSword [WEAP:00012EB7]: FULL='Esplib Mega Sword',")
    lines.append("       DATA: value=9999, weight=5.0, damage=100. VNAM shows value.")
    lines.append("   [ ] EnchSteelWarAxeStamina2 [WEAP:000139A3]: FULL='Esplib Mega Axe',")
    lines.append("       DATA: value=5555, weight=8.0, damage=75.")
    lines.append("       CNAM (Template) = SteelWarAxe [WEAP:00013983].")
    lines.append("")

    lines.append("2. IN-GAME TEST:")
    lines.append("   Copy tests/output/esplib_modify_test.esp to Skyrim Data folder.")
    lines.append("   Enable it in your load order (after Skyrim.esm).")
    lines.append("   [ ] Game loads without crash.")
    lines.append("   [ ] Console: help \"Esplib Mega\" -> finds the sword.")
    lines.append("   [ ] player.additem 12EB7 1 -> sword in inventory.")
    lines.append("   [ ] Sword shows 'Esplib Mega Sword', damage=100, value=9999.")
    lines.append("   (Remove the esp after testing!)")
    lines.append("")

    if has_skyrim:
        lines.append("3. FIELD VALUES CHECK:")
        lines.append("   Compare the typed access output above against xEdit:")
        lines.append("   [ ] IronSword damage/value/weight match xEdit.")
        lines.append("   [ ] ArmorIronCuirass value/weight match xEdit.")
        lines.append("   [ ] NPC level matches xEdit.")
        lines.append("")

    checklist = '\n'.join(lines)
    print()
    print(checklist)

    checklist_path = OUTPUT_DIR / 'phase_4_checklist.txt'
    with open(checklist_path, 'w') as f:
        f.write(checklist)
    print(f"[OK  ] Checklist written to: {checklist_path}")


if __name__ == '__main__':
    main()
