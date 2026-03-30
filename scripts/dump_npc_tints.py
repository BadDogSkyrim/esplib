"""Dump tint layer data for an NPC record.

Usage:
    python dump_npc_tints.py <plugin_path> <npc_edid> [-o output_file]

Example:
    python dump_npc_tints.py "C:/Steam/.../Data/Skyrim.esm" BalgruuftheGreater
    python dump_npc_tints.py "C:/Steam/.../Data/FurrifierTEST.esp" BalgruuftheGreater
    python dump_npc_tints.py "C:/Steam/.../Data/Skyrim.esm" Athis -o athis_tints.txt
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from esplib import Plugin


def dump_npc_tints(plugin_path, npc_edid, out=None):
    if out is None:
        out = sys.stdout

    p = Plugin()
    p.load(plugin_path)

    npc = None
    for r in p.records:
        if r.signature == 'NPC_' and r.editor_id == npc_edid:
            npc = r
            break

    if npc is None:
        print(f"NPC '{npc_edid}' not found in {plugin_path}", file=out)
        return

    print(f"=== {npc_edid} [{npc.form_id}] Tint Layers ===\n", file=out)
    print(f"Plugin: {Path(plugin_path).name}", file=out)
    print(f"Masters: {p.header.masters}\n", file=out)

    # Show QNAM if present
    qnam = npc.get_subrecord('QNAM')
    if qnam and qnam.size >= 12:
        r_val, g_val, b_val = struct.unpack('<fff', qnam.data[:12])
        print(f"QNAM (texture lighting): R={r_val:.4f} G={g_val:.4f} B={b_val:.4f}", file=out)
        print(f"  as RGB 0-255: R={round(r_val*255)} G={round(g_val*255)} B={round(b_val*255)}", file=out)
        print(file=out)

    # Collect tint layers as groups of TINI/TINC/TINV/TIAS
    subs = npc.subrecords
    layers = []
    i = 0
    while i < len(subs):
        if subs[i].signature == 'TINI':
            layer = {'TINI': struct.unpack('<H', subs[i].data[:2])[0]}
            j = i + 1
            while j < len(subs) and subs[j].signature in ('TINC', 'TINV', 'TIAS'):
                s = subs[j]
                if s.signature == 'TINC':
                    layer['TINC'] = struct.unpack('<I', s.data[:4])[0]
                elif s.signature == 'TINV':
                    # Could be float or int depending on context
                    raw = s.data[:4]
                    val_i = struct.unpack('<I', raw)[0]
                    val_f = struct.unpack('<f', raw)[0]
                    if val_i <= 200:
                        layer['TINV'] = val_i
                        layer['TINV_fmt'] = 'int'
                    else:
                        layer['TINV'] = val_f
                        layer['TINV_fmt'] = 'float'
                elif s.signature == 'TIAS':
                    layer['TIAS'] = struct.unpack('<H', s.data[:2])[0]
                j += 1
            layers.append(layer)
            i = j
        else:
            i += 1

    print(f"Tint layers ({len(layers)}):", file=out)
    for idx, layer in enumerate(layers):
        tini = layer.get('TINI', '?')
        tinc = layer.get('TINC')
        tinv = layer.get('TINV', '?')
        tinv_fmt = layer.get('TINV_fmt', '?')
        tias = layer.get('TIAS', '?')

        if tinc is not None:
            # NPC TINC is inline RGBA color, not a FormID
            r = tinc & 0xFF
            g = (tinc >> 8) & 0xFF
            b = (tinc >> 16) & 0xFF
            a = (tinc >> 24) & 0xFF
            tinc_str = f"R={r} G={g} B={b} A={a}"
        else:
            tinc_str = "missing"

        if tinv_fmt == 'int':
            tinv_str = f"{tinv} ({tinv}%)"
        elif tinv_fmt == 'float':
            tinv_str = f"{tinv:.4f} (FLOAT — may be wrong format)"
        else:
            tinv_str = str(tinv)

        print(f"  [{idx:2d}] TINI={tini:5d}  TINC={tinc_str}", file=out)
        print(f"        TINV={tinv_str}  TIAS={tias}", file=out)

    if not layers:
        print("  (none)", file=out)

    print(f"\n--- end {npc_edid} ---", file=out)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    args = sys.argv[1:]
    plugin_path = args[0]
    npc_edid = args[1]
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
                dump_npc_tints(plugin_path, npc_edid, out=f)
            print(f"Written to {output_file}")
        else:
            dump_npc_tints(plugin_path, npc_edid)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
