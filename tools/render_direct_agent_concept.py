"""Render the standalone slide-02 direct-agent concept; preserve the broker edition."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import render_poc_review as deck

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/presentations/poc-direct-agent-concept/architecture.json'
STEM = 'direct-agent-architecture'


def make_scene(data):
    if data.get('status') != 'concept-not-implemented' or len(data['slides']) != 1:
        raise ValueError('Expected one explicitly unimplemented concept slide')
    slide = data['slides'][0]
    if slide['kind'] != 'architecture':
        raise ValueError('Expected architecture layout')
    scene = deck.page(slide, 1, 9, data['baseline'])
    # This is an alternate slide 02, not a regenerated nine-page presentation.
    scene.items[-1].update(value='02', lines=['02'])
    deck.architecture(scene, slide)
    for item in scene.items:
        if item.get('role') == 'broker-request':
            item.update(role='direct-script-call', dashed=False)
    return scene


def build(source=SOURCE, output_dir=None):
    source = Path(source).resolve()
    output = Path(output_dir or source.parent).resolve()
    for name in ('poc-implementation-review', 'journey'):
        protected = (ROOT / 'docs/presentations' / name).resolve()
        if output == protected or protected in output.parents:
            raise ValueError('Refusing to overwrite a historical presentation')
    data = deck.load_source(source)
    scene = make_scene(data)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='direct-agent-concept-') as tmp:
        stage = Path(tmp)
        pptx, pdf = stage / f'{STEM}.pptx', stage / f'{STEM}.pdf'
        deck.save_pptx(data, [scene], pptx)
        subprocess.run([
            'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', str(ROOT / 'tools/export_presentation_pdf.ps1'),
            '-InputPath', str(pptx), '-OutputPath', str(pdf),
        ], check=True)
        import pymupdf
        normalize = lambda value: re.sub(r'\s+', '', value)
        with pymupdf.open(pdf) as document:
            if len(document) != 1:
                raise ValueError('Expected exactly one exported page')
            page = document[0]
            text = normalize(page.get_text())
            for item in scene.items:
                if item['kind'] == 'text' and normalize(item['value']) not in text:
                    raise ValueError(f'PDF missing text: {item["value"]}')
            page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False).save(
                stage / 'preview-02.png')
        # Publish only after all outputs have been rendered and checked.
        for generated in stage.iterdir():
            temporary = output / (generated.name + '.publishing')
            try:
                shutil.copyfile(generated, temporary)
                temporary.replace(output / generated.name)
            finally:
                temporary.unlink(missing_ok=True)
    print(f'Built concept preview: {output / "preview-02.png"}')
    print(f'Source SHA-256: {hashlib.sha256(source.read_bytes()).hexdigest()}')
    return scene


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    build(args.source, args.output_dir)
