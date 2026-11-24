"""Offline local-link checks, inventory comparisons and registered screenshot checks."""
import argparse
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote
from workpaper_io import sha256, walk_files, workbook_inventory, write_json


def compare(before, after, protected=()):
    if before.get('schema') != 'research-inventory-v1' or after.get('schema') != 'research-inventory-v1':
        raise ValueError('Both reports must be research-inventory-v1.')
    a = {f['key']: f for f in before['files']}
    b = {f['key']: f for f in after['files']}
    changed = []
    for key in sorted(a.keys() & b.keys()):
        if a[key].get('sha256') == b[key].get('sha256') and not a[key].get('error') and not b[key].get('error'):
            continue
        item = {'key': key, 'status': 'changed; review against authorized scope'}
        if 'workbook' in a[key] and 'workbook' in b[key]:
            old, new = a[key]['workbook'], b[key]['workbook']
            os = {s['name']: s for s in old['sheets']}
            ns = {s['name']: s for s in new['sheets']}
            item.update(removed_sheets=sorted(os.keys()-ns.keys()), added_sheets=sorted(ns.keys()-os.keys()),
                        changed_sheets=[name for name in os.keys() & ns.keys() if os[name] != ns[name]])
            old_media, new_media = Counter(old['media'].values()), Counter(new['media'].values())
            item['missing_media_content_copies'] = sum((old_media-new_media).values())
            item['object_changes'] = []
            for name in sorted(os.keys() & ns.keys()):
                for kind in ('chart', 'image'):
                    old_items = [d for d in os[name]['drawings'] if d['kind'] == kind]
                    new_items = [d for d in ns[name]['drawings'] if d['kind'] == kind]
                    if old_items != new_items:
                        item['object_changes'].append({'sheet': name, 'kind': kind,
                                                       'before': len(old_items), 'after': len(new_items),
                                                       'references_changed': True})
        changed.append(item)
    checks = [{'key': key, 'unchanged': key in a and key in b and
               not a[key].get('error') and not b[key].get('error') and
               a[key].get('sha256') == b[key].get('sha256')} for key in protected]
    incomplete = [f['key'] for report in (before, after) for f in report['files'] if f.get('error')]
    return {'schema': 'research-comparison-v1', 'added': sorted(b.keys()-a.keys()),
            'removed': sorted(a.keys()-b.keys()), 'changed': changed, 'protected': checks,
            'incomplete_inputs': incomplete,
            'limitations': 'Differences need scope review. Equal object counts do not prove preservation; no native recalculation or visual audit.'}


def strip_code(text):
    text = re.sub(r'^(`{3,}|~{3,}).*?^\1[^\n]*$', '', text, flags=re.M | re.S)
    return re.sub(r'`[^`\n]*`', '', text)


def check_links(root, notes=None):
    root = Path(root).resolve(strict=True)
    all_files = list(walk_files(root))
    targets = [Path(p).resolve(strict=True) for p in notes] if notes else [p for p in all_files if p.suffix == '.md']
    by_name = {}
    for path in all_files:
        by_name.setdefault(path.name.casefold(), []).append(path)
    findings = []
    for note in targets:
        if note.suffix != '.md':
            raise ValueError('Notes must be Markdown files.')
        content = strip_code(note.read_text(encoding='utf-8-sig'))
        links = [('wiki', m.group(1)) for m in re.finditer(r'!?\[\[([^\]\n]+)\]\]', content)]
        # Simple inline Markdown syntax only. Balanced parentheses/reference-style links are not certified.
        links += [('markdown', m.group(1)) for m in re.finditer(r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)', content)]
        for kind, raw in links:
            cleaned = raw.replace('\\|', '|').split('|', 1)[0] if kind == 'wiki' else raw.strip('<>')
            cleaned = unquote(cleaned)
            if re.match(r'^[a-zA-Z][\w+.-]*:', cleaned) and not re.match(r'^[A-Za-z]:[/\\]', cleaned):
                findings.append({'note': str(note), 'target': raw, 'status': 'external_not_checked'})
                continue
            filepart, _, anchor = cleaned.partition('#')
            candidates = []
            if not filepart:
                candidates = [note]
            elif kind == 'wiki':
                names = [filepart] if Path(filepart).suffix else [filepart + '.md']
                for name in names:
                    for path in (note.parent / name, root / name):
                        if path.is_file(): candidates.append(path.resolve())
                    # Path-qualified wiki links must match the trailing path, not just a basename.
                    suffix = name.replace('\\', '/').casefold()
                    candidates.extend(p for p in by_name.get(Path(name).name.casefold(), [])
                                      if p.as_posix().casefold().endswith('/' + suffix))
            else:
                path = Path(filepart)
                candidate = path if path.is_absolute() else note.parent / path
                if candidate.is_file(): candidates = [candidate.resolve()]
            candidates = sorted(set(candidates))
            status = 'file_found' if len(candidates) == 1 else 'ambiguous' if candidates else 'missing_or_outside_root'
            if len(candidates) == 1 and anchor:
                status = 'file_found_anchor_unverified'
            findings.append({'note': str(note), 'target': raw, 'status': status,
                             'candidates': [str(p) for p in candidates]})
    return {'schema': 'research-links-v1', 'root': str(root), 'notes_checked': len(targets), 'findings': findings,
            'limitations': 'Offline local targets only; headings/blocks, Obsidian resolver plugins, reference-style and nested-parenthesis Markdown links require review. External URLs are not fetched.'}


def check_evidence(registry_path):
    registry_path = Path(registry_path).resolve(strict=True)
    registry = json.loads(registry_path.read_text(encoding='utf-8-sig'))
    results = []
    for record in registry['records']:
        entry = {'evidence_id': record['evidence_id']}
        try:
            book = (registry_path.parent / record['workbook']).resolve(strict=True)
            image = (registry_path.parent / record['external_image']).resolve(strict=True)
            details = workbook_inventory(book)
            sheet = next((s for s in details['sheets'] if s['name'] == record['sheet']), None)
            if sheet is None:
                entry['status'] = 'sheet_missing'
            else:
                matching_parts = {part for part, digest in details['media'].items() if digest == sha256(image)}
                embedded = [d['target'] for d in sheet['drawings'] if d['kind'] == 'image' and
                            not d.get('external') and d.get('target') in matching_parts]
                entry.update(status='exact_embedded_image_found' if embedded else 'embedding_unconfirmed',
                             workbook=str(book), sheet=record['sheet'], data_range=record.get('data_range'),
                             matched_media=embedded)
        except Exception as error:
            entry.update(status='error', error=f'{type(error).__name__}: {error}')
        results.append(entry)
    return {'schema': 'research-evidence-check-v1', 'records': results,
            'limitations': 'Exact image bytes and sheet attachment only. Re-encoded images need manual review; data-range meaning and screenshot relevance are not verified.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    links = sub.add_parser('links'); links.add_argument('--root', required=True); links.add_argument('--note', action='append')
    diff = sub.add_parser('compare'); diff.add_argument('--before', required=True); diff.add_argument('--after', required=True)
    diff.add_argument('--protect', action='append', default=[], help='Exact inventory key that must remain unchanged.')
    evidence = sub.add_parser('evidence'); evidence.add_argument('--registry', required=True)
    for command in (links, diff, evidence): command.add_argument('--out')
    args = parser.parse_args()
    if args.out and Path(args.out).exists(): parser.error('Output exists; choose a new report path.')
    if args.mode == 'links':
        report = check_links(args.root, args.note)
        problem = any(f['status'] in ('ambiguous', 'missing_or_outside_root') for f in report['findings'])
    elif args.mode == 'compare':
        report = compare(json.loads(Path(args.before).read_text(encoding='utf-8-sig')),
                         json.loads(Path(args.after).read_text(encoding='utf-8-sig')), args.protect)
        problem = bool(report['incomplete_inputs']) or any(not x['unchanged'] for x in report['protected'])
    else:
        report = check_evidence(args.registry)
        problem = any(r['status'] != 'exact_embedded_image_found' for r in report['records'])
    write_json(report, args.out)
    return 2 if problem else 0


if __name__ == '__main__':
    raise SystemExit(main())
