"""esplib CLI entry point."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog='esplib',
        description='esplib -- Bethesda plugin toolkit',
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # --- info ---
    info_parser = subparsers.add_parser('info', help='Show plugin header and statistics')
    info_parser.add_argument('plugin', help='Path to plugin file')
    info_parser.add_argument('--format', choices=['text', 'json'], default='text', type=str.lower)
    info_parser.add_argument('-o', '--output', help='Write output to file instead of stdout')

    # --- dump ---
    dump_parser = subparsers.add_parser('dump', help='Dump records with typed fields')
    dump_parser.add_argument('plugin', help='Path to plugin file')
    dump_parser.add_argument('--type', dest='record_type', help='Filter by record signature (e.g. WEAP)')
    dump_parser.add_argument('--form-id', help='Filter by FormID (hex, e.g. 00012EB7)')
    dump_parser.add_argument('--editor-id', help='Filter by Editor ID')
    dump_parser.add_argument('--game', choices=['tes5', 'fo4', 'sf1'], help='Game (auto-detected if omitted)')
    dump_parser.add_argument('--format', choices=['text', 'json', 'csv'], default='text', type=str.lower)
    dump_parser.add_argument('--limit', type=int, default=0, help='Max records to dump (0=all)')
    dump_parser.add_argument('-o', '--output', help='Write output to file instead of stdout')

    # --- diff ---
    diff_parser = subparsers.add_parser('diff', help='Differences between two plugins')
    diff_parser.add_argument('plugin1', help='First plugin')
    diff_parser.add_argument('plugin2', help='Second plugin')
    diff_parser.add_argument('--field-level', action='store_true', help='Show field-level diffs (requires --game)')
    diff_parser.add_argument('--game', choices=['tes5', 'fo4', 'sf1'])
    diff_parser.add_argument('--format', choices=['text', 'json'], default='text', type=str.lower)
    diff_parser.add_argument('-o', '--output', help='Write output to file instead of stdout')

    # --- validate ---
    val_parser = subparsers.add_parser('validate', help='Validate plugin structure')
    val_parser.add_argument('plugin', help='Path to plugin file')
    val_parser.add_argument('--game', choices=['tes5', 'fo4', 'sf1'])
    val_parser.add_argument('--format', choices=['text', 'json'], default='text', type=str.lower)
    val_parser.add_argument('-o', '--output', help='Write output to file instead of stdout')

    # --- rename-master ---
    rm_parser = subparsers.add_parser('rename-master', help='Rename a master dependency')
    rm_parser.add_argument('plugin', help='Path to plugin file')
    rm_parser.add_argument('old_name', help='Current master filename')
    rm_parser.add_argument('new_name', help='New master filename')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Dispatch to command handlers
    from .commands import info, dump, diff, validate, rename_master

    commands = {
        'info': info.run,
        'dump': dump.run,
        'diff': diff.run,
        'validate': validate.run,
        'rename-master': rename_master.run,
    }

    handler = commands.get(args.command)
    if handler:
        # Check that plugin files exist
        import os
        for attr in ('plugin', 'plugin1', 'plugin2'):
            path = getattr(args, attr, None)
            if path and not os.path.isfile(path):
                print(f"Error: file not found: {path}", file=sys.stderr)
                return 1

        # Handle --output / -o redirection
        output_file = getattr(args, 'output', None)
        if output_file:
            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                ret = handler(args)
                content = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Output written to: {output_file}")
            return ret
        else:
            return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
