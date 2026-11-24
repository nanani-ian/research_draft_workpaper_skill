"""Capture explicit PDF pages with Poppler, retaining full pages beside optional crops."""
import argparse
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from workpaper_io import sha256, write_json


def parse_pages(spec):
    pages = []
    for token in spec.split(','):
        if not re.fullmatch(r'\d+(?:-\d+)?', token.strip()):
            raise ValueError('Pages use 1-based numbers, for example 2,5-7.')
        bounds = [int(x) for x in token.strip().split('-')]
        first, last = bounds[0], bounds[-1]
        if first < 1 or last < first:
            raise ValueError('Invalid page range.')
        pages.extend(range(first, last + 1))
    return sorted(set(pages))


def capture(pdf, pages, out, source_id, source_url='', dpi=140, crop=None, pdftoppm=None,
            printed_page_note=''):
    from pypdf import PdfReader
    source = Path(pdf).resolve(strict=True)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', source_id):
        raise ValueError('source-id must be a safe stable ID, e.g. S01.')
    pages = sorted(set(pages))
    total = len(PdfReader(str(source)).pages)
    if not pages or min(pages) < 1 or max(pages) > total:
        raise ValueError(f'PDF has {total} pages; requested page is out of range.')
    if not 72 <= dpi <= 300:
        raise ValueError('DPI must be between 72 and 300.')
    if crop is not None and not (len(crop) == 4 and 0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1):
        raise ValueError('Crop uses normalized x0,y0,x1,y1 within [0,1].')
    executable = pdftoppm or shutil.which('pdftoppm')
    if not executable:
        raise ValueError('pdftoppm is unavailable. Supply --pdftoppm; no automatic installation.')
    destination = Path(out).resolve()
    # Must be a new batch directory. Validation happens before creating it.
    if destination.exists():
        raise FileExistsError('Output directory already exists; choose a new version/batch.')
    destination.mkdir(parents=True)
    before = sha256(source)
    report = {'schema': 'research-capture-v1', 'source_id': source_id,
              'source_file': str(source), 'source_sha256': before, 'source_url': source_url,
              'created_at': datetime.now(timezone.utc).isoformat(), 'dpi': dpi,
              'printed_page_note': printed_page_note, 'page_numbering': '1-based PDF viewer pages',
              'status': 'incomplete', 'pages': []}
    try:
        for page in pages:
            prefix = destination / f'{source_id}-pdfp{page:04d}-full'
            subprocess.run([str(executable), '-f', str(page), '-l', str(page), '-r', str(dpi),
                            '-singlefile', '-png', str(source), str(prefix)], check=True,
                           capture_output=True, timeout=120)
            full = prefix.with_suffix('.png')
            if not full.is_file():
                raise RuntimeError('Renderer did not produce the expected image.')
            item = {'pdf_page': page, 'full_image': full.name, 'full_sha256': sha256(full)}
            if crop is not None:
                from PIL import Image
                with Image.open(full) as image:
                    box = (int(crop[0]*image.width), int(crop[1]*image.height),
                           int(crop[2]*image.width), int(crop[3]*image.height))
                    cropped = destination / f'{source_id}-pdfp{page:04d}-crop.png'
                    image.crop(box).save(cropped)
                item.update(crop_image=cropped.name, crop_sha256=sha256(cropped), crop_normalized=crop)
            report['pages'].append(item)
        report['source_unchanged'] = sha256(source) == before
        if not report['source_unchanged']:
            raise RuntimeError('Source changed during capture; do not adopt these images.')
        report['status'] = 'captured; visual and evidence review required'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        write_json(report, destination / 'capture-manifest.json')
        raise
    write_json(report, destination / 'capture-manifest.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--pages', required=True, help='PDF viewer pages: 2,5-7; not printed page labels.')
    parser.add_argument('--out', required=True, help='New output directory; never reuse a prior batch.')
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--source-url', default='')
    parser.add_argument('--printed-page-note', default='')
    parser.add_argument('--dpi', type=int, default=140)
    parser.add_argument('--crop', help='Optional normalized rectangle x0,y0,x1,y1; full pages retained.')
    parser.add_argument('--pdftoppm', help='Executable path if not on PATH.')
    args = parser.parse_args()
    try:
        result = capture(args.pdf, parse_pages(args.pages), args.out, args.source_id,
                         args.source_url, args.dpi,
                         [float(x) for x in args.crop.split(',')] if args.crop else None,
                         args.pdftoppm, args.printed_page_note)
        print(f"Captured {len(result['pages'])} pages. Manifest: {Path(args.out)/'capture-manifest.json'}")
    except Exception as error:
        parser.exit(2, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
