"""Dump tint mask data for a race record.

Usage:
    python dump_race_tints.py <plugin_path> <race_edid> [--female] [-o output_file]

Example:
    python dump_race_tints.py "C:/Steam/.../Data/YASCanineRaces.esp" YASLykaiosRace
    python dump_race_tints.py "C:/Steam/.../Data/Skyrim.esm" NordRace --female
    python dump_race_tints.py "C:/Steam/.../Data/Skyrim.esm" NordRace -o nord_tints.txt
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from esplib import Plugin


def dump_tints(plugin_path, race_edid, female=False, out=None):
    if out is None:
        out = sys.stdout

    p = Plugin()
    p.load(plugin_path)

    race = None
    for r in p.get_records_by_signature('RACE'):
        if r.editor_id == race_edid:
            race = r
            break

    if race is None:
        print(f"Race '{race_edid}' not found in {plugin_path}", file=out)
        return

    sex_label = "Female" if female else "Male"
    print(f"=== {race_edid} {sex_label} Tint Masks ===\n", file=out)

    # Find correct Head Data section
    target_nam0 = 2 if female else 1
    nam0_count = 0
    in_section = False
    subs = race.subrecords

    i = 0
    while i < len(subs):
        sr = subs[i]

        if sr.signature == 'NAM0':
            nam0_count += 1
            if nam0_count == target_nam0:
                in_section = True
            elif in_section:
                break
            i += 1
            continue

        if not in_section or sr.signature != 'TINI':
            i += 1
            continue

        # Parse one tint entry
        tini = struct.unpack('<H', sr.data[:2])[0]
        tint_path = ''
        tinp_val = -1
        tind_fid = None
        presets = []

        j = i + 1
        while j < len(subs) and subs[j].signature not in ('TINI', 'NAM0'):
            s = subs[j]

            if s.signature == 'TINT':
                tint_path = s.data.decode('cp1252', errors='replace').rstrip('\x00')
            elif s.signature == 'TINP':
                tinp_val = struct.unpack('<H', s.data[:2])[0]
            elif s.signature == 'TIND':
                tind_fid = struct.unpack('<I', s.data[:4])[0]
            elif s.signature == 'TINC':
                color_fid = struct.unpack('<I', s.data[:4])[0]
                intensity = 0.0
                tirs_val = -1
                if j + 1 < len(subs) and subs[j + 1].signature == 'TINV':
                    intensity = struct.unpack('<f', subs[j + 1].data[:4])[0]
                if j + 2 < len(subs) and subs[j + 2].signature == 'TIRS':
                    tirs_val = struct.unpack('<H', subs[j + 2].data[:2])[0]
                presets.append((color_fid, intensity, tirs_val))
            j += 1

        # Print
        basename = tint_path.rsplit('\\', 1)[-1] if '\\' in tint_path else tint_path
        basename = basename.rsplit('/', 1)[-1] if '/' in basename else basename
        print(f"TINI={tini}  TINP={tinp_val}  file={basename}", file=out)
        print(f"  path: {tint_path}", file=out)
        if tind_fid is not None:
            print(f"  default color: {tind_fid:#010x}", file=out)
        print(f"  presets ({len(presets)}):", file=out)
        for color_fid, intensity, tirs in presets:
            print(f"    TINC={color_fid:#010x}  TINV={intensity:.4f}  TIRS={tirs}", file=out)
        print(file=out)

        i = j

    print(f"--- end {race_edid} {sex_label} ---", file=out)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    args = sys.argv[1:]
    plugin_path = args[0]
    race_edid = args[1]
    female = '--female' in args
    output_file = None

    if '-o' in args:
        idx = args.index('-o')
        if idx + 1 < len(args):
            output_file = args[idx + 1]
        else:
            print("Error: -o requires a filename")
            sys.exit(1)

    if not Path(plugin_path).exists():
        print(f"Error: file not found: {plugin_path}")
        sys.exit(1)

    try:
        if output_file:
            with open(output_file, 'w') as f:
                dump_tints(plugin_path, race_edid, female, out=f)
            print(f"Written to {output_file}")
        else:
            dump_tints(plugin_path, race_edid, female)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
