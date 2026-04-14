"""Phase 5 Manual Test Script.

Demonstrates game discovery, load order reading, multi-plugin loading,
and override chain resolution.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from esplib import (
    Plugin, LoadOrder, PluginSet, FormID,
    discover_games, find_game,
)
import esplib.defs.tes5 as tes5


OUTPUT_DIR = Path(__file__).parent.parent / 'output'


def test_game_discovery():
    """Test game discovery on this machine."""
    print("--- Game Discovery ---")
    games = discover_games()
    for g in games:
        print(f"[OK  ] {g.name}")
        print(f"       data_dir: {g.data_dir}")
        print(f"       exe:      {g.exe_path}")
        print(f"       appdata:  {g.app_data_dir}")
        ptxt = g.plugins_txt()
        print(f"       plugins.txt: {ptxt}")
    if not games:
        print("[WARN] No games found")
    return len(games) > 0


def test_load_order():
    """Test reading Skyrim's load order."""
    game = find_game('tes5')
    if not game:
        print("[SKIP] Skyrim not installed")
        return False

    print("\n--- Load Order (Skyrim SE) ---")
    lo = LoadOrder.from_game('tes5')
    print(f"[OK  ] {len(lo)} plugins in load order")
    for i, name in enumerate(lo.plugins[:15]):
        print(f"       [{i:3d}] {name}")
    if len(lo) > 15:
        print(f"       ... and {len(lo) - 15} more")
    return True


def test_override_chains():
    """Load Skyrim.esm + Update.esm and show override chains."""
    game = find_game('tes5')
    if not game:
        print("[SKIP] Skyrim not installed")
        return

    print("\n--- Override Chains (Skyrim.esm + Update.esm) ---")
    lo = LoadOrder.from_list(
        ['Skyrim.esm', 'Update.esm'],
        data_dir=game.data_dir, game_id='tes5')
    ps = PluginSet(lo)
    loaded = ps.load_all()
    print(f"[OK  ] Loaded {loaded} plugins")

    overrides = list(ps.overridden_records())
    print(f"[OK  ] {len(overrides)} records overridden by Update.esm")

    # Show a few examples
    skyrim = ps.get_plugin('Skyrim.esm')
    update = ps.get_plugin('Update.esm')
    if skyrim and update:
        skyrim.set_game('tes5')
        update.set_game('tes5')

    shown = 0
    for fid, chain in overrides[:20]:
        base = chain[0]
        winner = chain[-1]
        edid = base.editor_id or winner.editor_id
        if edid:
            print(f"       {edid} [{base.signature}:{fid:08X}] "
                  f"overridden by {chain.plugin_names[-1]}")
            shown += 1
            if shown >= 10:
                break


def test_dawnguard_reference():
    """Load Skyrim + Dawnguard and resolve a cross-plugin reference."""
    game = find_game('tes5')
    if not game:
        print("[SKIP] Skyrim not installed")
        return

    dawnguard_path = game.data_dir / 'Dawnguard.esm'
    if not dawnguard_path.exists():
        print("[SKIP] Dawnguard.esm not found")
        return

    print("\n--- Cross-Plugin Reference (Dawnguard) ---")
    lo = LoadOrder.from_list(
        ['Skyrim.esm', 'Update.esm', 'Dawnguard.esm'],
        data_dir=game.data_dir, game_id='tes5')
    ps = PluginSet(lo)
    ps.load_all()

    # Find a Dawnguard weapon
    dawnguard = ps.get_plugin('Dawnguard.esm')
    if dawnguard:
        dawnguard.set_game('tes5')
        weapons = list(dawnguard.get_records_by_signature('WEAP'))
        for w in weapons[:20]:
            edid = w.editor_id
            if edid and 'Crossbow' in edid:
                data = tes5.WEAP.from_record(w)
                game_data = data.get('Game Data', {})
                print(f"[OK  ] {edid}: damage={game_data.get('damage')}, "
                      f"value={game_data.get('value')}")
                break


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("=== MANUAL TEST: Phase 5 Master Resolution ===")
    print("=" * 60)
    print()

    has_games = test_game_discovery()
    has_lo = test_load_order()
    test_override_chains()
    test_dawnguard_reference()

    lines = []
    lines.append("=" * 60)
    lines.append("PHASE 5 MANUAL TEST CHECKLIST")
    lines.append("=" * 60)
    lines.append("")

    lines.append("1. GAME DISCOVERY:")
    lines.append("   [ ] Skyrim SE found with correct Data directory.")
    lines.append("   [ ] Fallout 4 found (if installed).")
    lines.append("   [ ] plugins.txt path is correct for each game.")
    lines.append("")

    lines.append("2. LOAD ORDER:")
    lines.append("   [ ] Load order matches what's in your plugins.txt.")
    lines.append("   [ ] Implicit masters (Skyrim.esm, Update.esm, etc.) appear first.")
    lines.append("")

    lines.append("3. OVERRIDE CHAINS:")
    lines.append("   [ ] Update.esm overrides are detected (should be >0).")
    lines.append("   [ ] Compare a few overridden records against xEdit:")
    lines.append("       Load Skyrim.esm + Update.esm in xEdit, find a record")
    lines.append("       that shows as overridden, verify esplib lists it too.")
    lines.append("")

    lines.append("4. CROSS-PLUGIN REFERENCE:")
    lines.append("   [ ] Dawnguard crossbow weapon resolves with correct damage/value.")
    lines.append("   [ ] Compare against xEdit's values for the same weapon.")
    lines.append("")

    checklist = '\n'.join(lines)
    print()
    print(checklist)

    checklist_path = OUTPUT_DIR / 'phase_5_checklist.txt'
    with open(checklist_path, 'w') as f:
        f.write(checklist)
    print(f"[OK  ] Checklist written to: {checklist_path}")


if __name__ == '__main__':
    main()
