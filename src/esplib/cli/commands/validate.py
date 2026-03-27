"""esplib validate -- validate plugin structure."""

import json
from esplib import Plugin


def run(args):
    plugin = Plugin(args.plugin)
    issues = plugin.validate()

    if args.format == 'json':
        output = {
            'plugin': str(plugin.file_path),
            'valid': len(issues) == 0,
            'issues': issues,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Validating: {plugin.file_path}")
        if not issues:
            print("OK -- no issues found")
        else:
            print(f"Found {len(issues)} issue(s):")
            for issue in issues:
                print(f"  ! {issue}")

    return 0 if not issues else 1
