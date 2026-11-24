"""Inventory explicitly supplied research files or one root. Never alter inputs."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from workpaper_io import sha256, walk_files, workbook_inventory, write_json


def inventory(inputs, root=None):
    base = Path(root).resolve() if root else None
    if base is not None and not base.is_dir():
        raise ValueError('Root must be an existing directory.')
    paths = list(walk_files(base)) if base else [Path(p).resolve() for p in inputs]
    entries = []
    for path in sorted(set(paths)):
        key = path.relative_to(base).as_posix() if base else str(path)
        item = {'key': key, 'path': str(path), 'suffix': path.suffix.lower()}
        try:
            if not path.is_file():
                raise ValueError('Not a regular file')
            before = path.stat()
            item.update(bytes=before.st_size, sha256=sha256(path))
            if path.suffix.lower() in ('.xlsx', '.xlsm'):
                item['workbook'] = workbook_inventory(path)
            elif path.suffix.lower() in ('.xls', '.xlsb'):
                item['inspection_note'] = 'Legacy/binary workbook: fingerprint only; structure not inspected.'
            after = path.stat()
            item['stable_during_scan'] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            if not item['stable_during_scan']:
                item['error'] = 'File changed during scan; repeat after saving/closing the source.'
        except Exception as error:
            item['error'] = f'{type(error).__name__}: {error}'
        entries.append(item)
    return {'schema': 'research-inventory-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
            'root': str(base) if base else None, 'files': entries,
            'errors': sum('error' in e for e in entries)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--input', action='append', help='Repeat for explicitly authorized files.')
    choice.add_argument('--root', help='Explicitly authorized directory; no link/junction traversal.')
    parser.add_argument('--out', help='New JSON report path. Omit to print; existing files refused.')
    args = parser.parse_args()
    if args.out and Path(args.out).exists():
        parser.error('Output already exists; choose a new report path.')
    report = inventory(args.input or [], args.root)
    write_json(report, args.out)
    return 2 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
