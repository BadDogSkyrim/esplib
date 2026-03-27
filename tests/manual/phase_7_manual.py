"""Phase 7 Manual Test Script -- CLI tools.

Runs each CLI command and prints a checklist.
"""

import sys
import subprocess
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


OUTPUT_DIR = Path(__file__).parent.parent / 'output'

SKYRIM_ESM = Path(r"C:\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm")


def run_cmd(args, label):
    """Run an esplib CLI command and print result."""
    cmd = ['esplib'] + args
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = result.stdout
    if result.returncode != 0 and result.stderr:
        output += result.stderr
    # Truncate long output
    lines = output.splitlines()
    if len(lines) > 30:
        for line in lines[:25]:
            print(f"  {line}")
        print(f"  ... ({len(lines) - 25} more lines)")
    else:
        for line in lines:
            print(f"  {line}")
    status = "[OK  ]" if result.returncode == 0 else "[FAIL]"
    print(f"{status} {label} (exit code {result.returncode})")
    return result.returncode == 0


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("=== MANUAL TEST: Phase 7 CLI Tools ===")
    print("=" * 60)

    results = {}

    # info
    if SKYRIM_ESM.exists():
        results['info text'] = run_cmd(
            ['info', str(SKYRIM_ESM)], 'info (text)')
        results['info json'] = run_cmd(
            ['info', str(SKYRIM_ESM), '--format', 'json'], 'info (json)')

    # dump
    if SKYRIM_ESM.exists():
        results['dump text'] = run_cmd(
            ['dump', str(SKYRIM_ESM), '--type', 'WEAP', '--editor-id', 'IronSword'],
            'dump WEAP IronSword (text)')
        results['dump json'] = run_cmd(
            ['dump', str(SKYRIM_ESM), '--type', 'WEAP', '--editor-id', 'IronSword',
             '--format', 'json'],
            'dump WEAP IronSword (json)')
        results['dump csv'] = run_cmd(
            ['dump', str(SKYRIM_ESM), '--type', 'GLOB', '--limit', '5',
             '--format', 'csv'],
            'dump GLOB --limit 5 (csv)')

    # validate
    modify_esp = OUTPUT_DIR / 'esplib_modify_test.esp'
    if modify_esp.exists():
        results['validate'] = run_cmd(
            ['validate', str(modify_esp)], 'validate esplib_modify_test.esp')

    # diff
    weapon_esp = OUTPUT_DIR / 'esplib_weapon_test.esp'
    if weapon_esp.exists() and modify_esp.exists():
        results['diff'] = run_cmd(
            ['diff', str(weapon_esp), str(modify_esp)],
            'diff weapon_test vs modify_test')

    # rename-master
    # Create a copy to test rename on
    rename_test = OUTPUT_DIR / 'esplib_rename_test.esp'
    if modify_esp.exists():
        shutil.copy2(modify_esp, rename_test)
        results['rename-master'] = run_cmd(
            ['rename-master', str(rename_test), 'Skyrim.esm', 'Skyrim_Renamed.esm'],
            'rename-master Skyrim.esm -> Skyrim_Renamed.esm')
        # Verify with info
        if results.get('rename-master'):
            run_cmd(['info', str(rename_test)], 'verify renamed master')

    # Summary
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("PHASE 7 MANUAL TEST CHECKLIST")
    lines.append("=" * 60)
    lines.append("")

    lines.append("1. CLI COMMANDS:")
    lines.append("   [ ] 'esplib info Skyrim.esm' shows correct header, record counts.")
    lines.append("   [ ] 'esplib info --format json' produces valid JSON.")
    lines.append("   [ ] 'esplib dump --type WEAP --editor-id IronSword' shows damage=7.")
    lines.append("   [ ] 'esplib dump --format json' produces valid JSON.")
    lines.append("   [ ] 'esplib dump --format csv' produces valid CSV with headers.")
    lines.append("   [ ] 'esplib validate' reports 'no issues' for a valid plugin.")
    lines.append("   [ ] 'esplib diff' shows added/removed/changed counts.")
    lines.append("   [ ] 'esplib rename-master' renames master and info shows new name.")
    lines.append("")

    lines.append("2. ERROR HANDLING:")
    lines.append("   Try: esplib info nonexistent.esp")
    lines.append("   [ ] Reports error gracefully (not a Python traceback).")
    lines.append("   Try: esplib validate (no args)")
    lines.append("   [ ] Shows usage help.")
    lines.append("")

    checklist = '\n'.join(lines)
    print(checklist)

    checklist_path = OUTPUT_DIR / 'phase_7_checklist.txt'
    with open(checklist_path, 'w') as f:
        f.write(checklist)
    print(f"[OK  ] Checklist written to: {checklist_path}")


if __name__ == '__main__':
    main()
