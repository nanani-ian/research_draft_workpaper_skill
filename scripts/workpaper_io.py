"""Read-only OOXML inspection and exclusive report writing. Standard library only."""
import hashlib
import json
import os
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(data, output=None):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output is None:
        print(text)
        return
    # Never overwrite a source file or prior report. Parents must already exist.
    with Path(output).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text + '\n')


def relationships(z, part):
    name = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
    if name not in z.namelist():
        return {}
    result = {}
    for node in ET.fromstring(z.read(name)):
        target = node.get('Target', '')
        external = node.get('TargetMode') == 'External'
        if not external:
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
        result[node.get('Id')] = {'target': target, 'external': external,
                                 'type': node.get('Type', '').split('/')[-1]}
    return result


def workbook_inventory(path):
    """Inspect actual cells, formula locations and objects, without Excel or re-saving."""
    result = {'sheets': [], 'external_links': 0, 'media': {}, 'limitations': [
        'OOXML structure only; no recalculation, visual review or correctness certification.',
        'Charts/images include referenced drawing objects; unsupported extensions may need native review.']}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        wr = relationships(z, 'xl/workbook.xml')
        result['external_links'] = sum(bool(re.fullmatch(r'xl/externalLinks/externalLink\d+\.xml', n)) for n in names)
        for name in sorted(names):
            if name.startswith('xl/media/') and not name.endswith('/'):
                result['media'][name] = hashlib.sha256(z.read(name)).hexdigest()
        for sn in workbook.findall(S + 'sheets/' + S + 'sheet'):
            part = wr[sn.get(R + 'id')]['target']
            root = ET.fromstring(z.read(part))
            sr = relationships(z, part)
            addresses, formulas, errors = [], [], []
            for cell in root.iter(S + 'c'):
                if cell.find(S + 'v') is None and cell.find(S + 'f') is None and cell.find(S + 'is') is None:
                    continue
                addresses.append(cell.get('r'))
                formula = cell.find(S + 'f')
                if formula is not None:
                    # Keep shared-formula metadata; do not claim these are fully expanded formulas.
                    formulas.append([cell.get('r'), formula.text or '', sorted(formula.attrib.items())])
                if cell.get('t') == 'e':
                    errors.append({'cell': cell.get('r'), 'cached_error': cell.findtext(S + 'v')})
            drawings = []
            active_drawings = {n.get(R + 'id') for n in root.findall(S + 'drawing')}
            for rid, rel in sr.items():
                if rid not in active_drawings:
                    continue
                if rel['type'] != 'drawing' or rel['external']:
                    continue
                drawing = ET.fromstring(z.read(rel['target']))
                dr = relationships(z, rel['target'])
                drawing_hash = hashlib.sha256(z.read(rel['target'])).hexdigest()
                for node in drawing.iter():
                    if node.tag.endswith('}blip'):
                        rid = node.get(R + 'embed') or node.get(R + 'link')
                        target = dr.get(rid, {})
                        drawings.append({'kind': 'image', 'drawing_sha256': drawing_hash, **target})
                    elif node.tag == C + 'chart':
                        target = dr.get(node.get(R + 'id'), {})
                        item = {'kind': 'chart', 'drawing_sha256': drawing_hash, **target}
                        if target.get('target') in names:
                            chart = ET.fromstring(z.read(target['target']))
                            item['refs'] = [n.text for n in chart.iter(C + 'f')]
                            item['chart_sha256'] = hashlib.sha256(z.read(target['target'])).hexdigest()
                        drawings.append(item)
            pane = root.find(S + 'sheetViews/' + S + 'sheetView/' + S + 'pane')
            dimension = root.find(S + 'dimension')
            result['sheets'].append({
                'name': sn.get('name'), 'state': sn.get('state', 'visible'),
                'declared_dimension': dimension.get('ref') if dimension is not None else None,
                'populated_cells': len(addresses), 'formula_cells': len(formulas),
                'formula_fingerprint': hashlib.sha256(json.dumps(formulas, ensure_ascii=False).encode()).hexdigest(),
                'sheet_xml_sha256': hashlib.sha256(z.read(part)).hexdigest(),
                'cached_errors': errors[:30], 'cached_error_count': len(errors),
                'freeze_panes': pane.attrib if pane is not None else {},
                'merged_ranges': [m.get('ref') for m in root.findall(S + 'mergeCells/' + S + 'mergeCell')],
                'drawings': drawings,
                'tables': [r['target'] for r in sr.values() if r['type'] == 'table'],
                'hyperlinks': len(root.findall(S + 'hyperlinks/' + S + 'hyperlink')),
            })
    return result


def walk_files(root):
    """Do not traverse symlinks/junctions, or hidden configuration/cache directories."""
    root = Path(root)
    def fail(error):
        raise error
    for current, directories, files in os.walk(root, followlinks=False, onerror=fail):
        directories[:] = sorted(d for d in directories if not d.startswith('.') and
                                not (Path(current) / d).is_symlink() and
                                not bool(getattr((Path(current) / d).stat(), 'st_file_attributes', 0) & 1024))
        for name in sorted(files):
            path = Path(current) / name
            if not path.is_symlink() and not name.startswith('~$'):
                yield path
