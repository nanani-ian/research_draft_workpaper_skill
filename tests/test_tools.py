"""Run in disposable directories. Fixtures are synthetic, never user originals."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inventory import inventory
from workpaper_io import sha256, workbook_inventory, write_json
from check_delivery import compare, check_links, check_evidence
from capture_pdf import capture, parse_pages


def fixture_book(path, media=b'fixture-image', formula='A1*2', drawing=True):
    """Minimal OOXML parser fixture, not an Excel deliverable or authoring backend."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rn = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    pn = 'http://schemas.openxmlformats.org/package/2006/relationships'
    parts = {
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="{rn}"><sheets><sheet name="模块" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{pn}"><Relationship Id="rId1" Type="{rn}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{ns}" xmlns:r="{rn}"><dimension ref="A1:XFD9999"/><sheetData><row r="1"><c r="A1"><v>3</v></c><c r="B1"><f>{formula}</f><v>6</v></c></row><row r="2"><c r="B2"><f t="shared" si="0"/><v>8</v></c></row></sheetData>' + ('<drawing r:id="rD"/>' if drawing else '') + '</worksheet>',
    }
    if drawing:
        parts.update({
            'xl/worksheets/_rels/sheet1.xml.rels': f'<Relationships xmlns="{pn}"><Relationship Id="rD" Type="{rn}/drawing" Target="../drawings/drawing1.xml"/></Relationships>',
            'xl/drawings/drawing1.xml': f'<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="{rn}"><xdr:twoCellAnchor><xdr:pic><a:blip r:embed="rImg"/></xdr:pic></xdr:twoCellAnchor></xdr:wsDr>',
            'xl/drawings/_rels/drawing1.xml.rels': f'<Relationships xmlns="{pn}"><Relationship Id="rImg" Type="{rn}/image" Target="../media/image1.png"/></Relationships>',
            'xl/media/image1.png': media,
        })
    with zipfile.ZipFile(path, 'w') as z:
        for name, content in parts.items(): z.writestr(name, content)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='research-tool-tests-')
        self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def test_inventory_actual_cells_shared_formula_and_no_mutation(self):
        book = self.root / '原件.xlsx'; fixture_book(book)
        before = sha256(book)
        result = inventory([book])
        sheet = result['files'][0]['workbook']['sheets'][0]
        self.assertEqual(sheet['populated_cells'], 3)
        self.assertEqual(sheet['formula_cells'], 2)
        self.assertEqual(sheet['declared_dimension'], 'A1:XFD9999')
        self.assertEqual(sha256(book), before)
        self.assertEqual(result['errors'], 0)

    def test_missing_and_corrupt_inputs_are_not_pass(self):
        book = self.root / 'broken.xlsx'; book.write_bytes(b'not zip')
        result = inventory([book, self.root / 'missing.xlsx'])
        self.assertEqual(result['errors'], 2)

    def test_no_overwrite_report(self):
        report = self.root / 'report.json'; report.write_text('original')
        with self.assertRaises(FileExistsError): write_json({'test': 1}, report)
        self.assertEqual(report.read_text(), 'original')

    def test_detect_same_count_media_replacement_and_formula_change(self):
        before_path = self.root / 'before.xlsx'; after_path = self.root / 'after.xlsx'
        fixture_book(before_path, b'old'); fixture_book(after_path, b'new', 'A1*3')
        a = inventory([before_path]); b = inventory([after_path])
        a['files'][0]['key'] = b['files'][0]['key'] = '底稿.xlsx'
        result = compare(a, b, ['底稿.xlsx'])
        self.assertFalse(result['protected'][0]['unchanged'])
        self.assertEqual(result['changed'][0]['missing_media_content_copies'], 1)
        self.assertIn('模块', result['changed'][0]['changed_sheets'])

    def test_unchanged_and_absent_protected_file(self):
        p = self.root / '正文.md'; p.write_text('保留', encoding='utf-8')
        report = inventory([p])
        result = compare(report, copy.deepcopy(report), [str(p), '不存在.md'])
        self.assertEqual(result['changed'], [])
        self.assertTrue(result['protected'][0]['unchanged'])
        self.assertFalse(result['protected'][1]['unchanged'])

    def test_links_distinguish_duplicate_missing_external_and_code(self):
        for name in ['a', 'b']: (self.root / name).mkdir()
        (self.root/'a'/'同名.md').write_text('内容', encoding='utf-8')
        (self.root/'b'/'同名.md').write_text('内容', encoding='utf-8')
        note = self.root / '正文.md'
        note.write_text('[[同名]]\n[[a/同名#标题]]\n[[丢失]]\n[外链](https://example.invalid)\n```text\n[[代码内不检查]]\n```', encoding='utf-8')
        statuses = {f['target']: f['status'] for f in check_links(self.root, [note])['findings']}
        self.assertEqual(statuses['同名'], 'ambiguous')
        self.assertEqual(statuses['a/同名#标题'], 'file_found_anchor_unverified')
        self.assertEqual(statuses['丢失'], 'missing_or_outside_root')
        self.assertEqual(statuses['https://example.invalid'], 'external_not_checked')
        self.assertNotIn('代码内不检查', statuses)

    def test_evidence_requires_image_attached_to_named_sheet(self):
        image = self.root/'source.png'; image.write_bytes(b'screenshot-fixture')
        book = self.root/'底稿.xlsx'; fixture_book(book, image.read_bytes())
        registry = self.root/'登记.json'
        record = {'evidence_id': 'E01', 'workbook': book.name, 'sheet': '模块',
                  'external_image': image.name, 'data_range': 'A1:B2'}
        registry.write_text(json.dumps({'records': [record]}), encoding='utf-8')
        self.assertEqual(check_evidence(registry)['records'][0]['status'], 'exact_embedded_image_found')
        image.write_bytes(b'other screenshot')
        self.assertEqual(check_evidence(registry)['records'][0]['status'], 'embedding_unconfirmed')
        record['sheet'] = '不存在'
        registry.write_text(json.dumps({'records': [record]}), encoding='utf-8')
        self.assertEqual(check_evidence(registry)['records'][0]['status'], 'sheet_missing')

    def test_page_ranges_and_invalid_crop(self):
        self.assertEqual(parse_pages('3,1-2,2'), [1, 2, 3])
        for spec in ['0', '3-1', '1;2', '../2']:
            with self.assertRaises(ValueError): parse_pages(spec)

    @unittest.skipUnless(shutil.which('pdftoppm'), 'Poppler unavailable; PDF integration not exercised')
    def test_pdf_capture_retains_full_crop_manifest_and_source(self):
        from reportlab.pdfgen import canvas
        from PIL import Image
        pdf = self.root/'演示来源.pdf'
        c = canvas.Canvas(str(pdf)); c.drawString(50, 750, 'SYNTHETIC RESEARCH SOURCE - NOT REAL DATA')
        c.drawString(50, 700, 'Year 2025 | Terminal units 100 | Share 10% | kg per unit 2')
        c.showPage(); c.drawString(50, 750, 'Synthetic second page'); c.save()
        original = sha256(pdf)
        output = self.root/'captures'
        result = capture(pdf, [2, 1], output, 'S01', dpi=90, crop=[0, 0, 1, 0.4])
        self.assertEqual(sha256(pdf), original)
        self.assertEqual([p['pdf_page'] for p in result['pages']], [1, 2])
        for page in result['pages']:
            full, crop = Image.open(output/page['full_image']), Image.open(output/page['crop_image'])
            self.assertGreater(full.height, crop.height)
            full.close(); crop.close()
        self.assertTrue((output/'capture-manifest.json').exists())
        with self.assertRaises(FileExistsError): capture(pdf, [1], output, 'S01')
        invalid = self.root/'invalid'
        with self.assertRaises(ValueError): capture(pdf, [3], invalid, 'S01')
        self.assertFalse(invalid.exists())
        with self.assertRaises(ValueError): capture(pdf, [1], invalid, 'S01', crop=[.8, 0, .2, 1])
        self.assertFalse(invalid.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
