"""Six-page AI x MCP talk using the existing POC native-object theme/exporter.

Content and speaker notes: docs/presentations/ai-mcp-sharing/deck.json.
Historical decks and shared renderers are never modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import illustrate_ai_helper
import render_poc_review as theme

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/presentations/ai-mcp-sharing/deck.json'
STEM = 'ai-mcp-sharing'
KINDS = ('opening', 'architecture', 'capabilities', 'controls', 'demos', 'closing')


def page(d, index, data, cover=False):
    s = theme.Scene()
    s.box(0, 0, theme.W, theme.H, theme.PAPER, form='rect')
    s.text('AI × MCP  /  FROM CHAT TO CONTROLLED ACTION', 36, 23, 850, 13, theme.TEAL, True, h=20)
    theme.pill(s, d['chapter'], 940, 17, 224, theme.INK, '#EEF0E9')
    if not cover:
        s.text(d['title'], 36, 66, 1128, 34, theme.INK, True, h=48, role='title')
        s.text(d['subtitle'], 36, 122, 1128, 20, theme.MUTED, h=54)
    s.path([(36, 640), (1164, 640)], theme.LINE, 1)
    s.text(d['source'], 36, 650, 1032, 11.5, theme.MUTED, h=19, role='source')
    s.text(f'{index+1:02d} / {len(data["slides"]):02d}', 1092, 649, 72, 13,
           theme.MUTED, True, h=22, align='center')
    return s


def opening(s, d):
    s.text(d['display_title'], 36, 80, 800, 42, theme.INK, True, h=166, role='title')
    s.text(d['subtitle'], 36, 264, 820, 23, theme.MUTED, h=64)
    s.text(d['hook'], 36, 339, 820, 23, theme.TEAL, True, h=62)
    illustrate_ai_helper.draw(s)
    for j, card in enumerate(d['cards']):
        x = 36+j*380
        s.box(x, 432, 368, 128, theme.WHITE, theme.LINE)
        s.text(card['title'], x+18, 448, 332, 22, theme.ACCENTS[j], True, h=33)
        s.text(card['body'], x+18, 494, 332, 19, theme.INK, h=53)
    theme.ribbon(s, d['ribbon'])


def architecture(s, d):
    # One overview: Web AI's reasoning, the local browser/Relay bridge, and execution.
    specs = [(36, 328, theme.SKY, theme.BLUE),
             (398, 368, theme.SAND, theme.ORANGE),
             (800, 364, theme.MINT, theme.TEAL)]
    for actor, (x, w, tint, color) in zip(d['actors'], specs):
        s.box(x, 200, w, 303, tint)
        s.text(actor['environment'], x+20, 216, w-40, 16, color, True, h=26)
        s.text(actor['title'], x+20, 256, w-40, 26, color, True, h=39)
    theme.icon(s, 'code', 58, 313, 55, theme.BLUE, theme.SKY)
    s.text(d['actors'][0]['body'], 58, 387, 284, 24, theme.INK, h=94)
    s.box(416, 311, 332, 73, theme.WHITE)
    s.text(d['bridge_title'], 432, 322, 300, 22, theme.ORANGE, True, h=32)
    s.text(d['bridge_body'], 432, 355, 300, 17, theme.INK, h=26)
    s.path([(582, 385), (582, 405)], theme.ORANGE, 2, arrow=True)
    s.box(416, 407, 332, 74, theme.WHITE)
    s.text(d['relay_title'], 432, 417, 300, 22, theme.ORANGE, True, h=32)
    s.text(d['relay_body'], 432, 451, 300, 17, theme.INK, h=26)
    theme.icon(s, 'server', 822, 313, 55, theme.TEAL, theme.MINT)
    s.text(d['actors'][2]['body'], 822, 387, 320, 24, theme.INK, h=94)
    s.path([(365, 347), (397, 347)], theme.BLUE, 2.5, arrow=True, role='web-request')
    s.path([(767, 444), (799, 444)], theme.TEAL, 2.5, arrow=True, role='tool-request')
    s.path(theme.rounded([(982, 505), (982, 548), (200, 548), (200, 505)]),
           theme.TEAL, 2.5, arrow=True, role='real-result-return')
    s.text(d['result_label'], 338, 514, 524, 21, theme.TEAL, True, h=30, align='center')
    theme.ribbon(s, d['ribbon'])


def capabilities(s, d):
    for j, card in enumerate(d['cards']):
        x = 36+j*380
        color, tint = theme.ACCENTS[j], theme.TINTS[j]
        s.box(x, 213, 368, 319, tint)
        theme.icon(s, card['icon'], x+22, 237, 59, color, tint)
        s.text(card['title'], x+22, 320, 324, 27, color, True, h=40)
        s.text(card['body'], x+22, 383, 324, 24, theme.INK, h=103)
    theme.ribbon(s, d['ribbon'])


def controls(s, d):
    for j, row in enumerate(d['rows']):
        y = 190+j*85
        color = [theme.BLUE, theme.ORANGE, theme.ORANGE, theme.TEAL][j]
        s.box(36, y, 1128, 75, theme.WHITE, theme.LINE)
        s.box(36, y, 6, 75, color, radius=3)
        s.text(row['title'], 56, y+22, 217, 23, color, True, h=34)
        s.text(row['body'], 291, y+13, 679, 20, theme.INK, h=55)
        theme.pill(s, row['badge'], 992, y+22, 153, color,
                   theme.SAND if j in (1, 2) else theme.MINT, 16)
    s.text(d['caveat'], 36, 546, 1128, 18.5, theme.ORANGE, True, h=28)
    theme.ribbon(s, d['ribbon'])


def demos(s, d):
    for j, demo in enumerate(d['demos']):
        y = 190+j*195
        color, tint = [(theme.BLUE, theme.SKY), (theme.ORANGE, theme.SAND)][j]
        s.box(36, y, 1128, 180, tint)
        s.text(demo['title'], 55, y+13, 1088, 25, color, True, h=36)
        s.text(demo['prompt'], 55, y+61, 1088, 21, theme.INK, h=58)
        for k, step in enumerate(demo['steps']):
            x = 55+k*278
            s.box(x, y+127, 253, 37, theme.WHITE)
            s.text(step, x+9, y+133, 235, 18, color, True, h=28, align='center')
            if k < 3:
                s.path([(x+255, y+146), (x+274, y+146)], color, 2, arrow=True)
    theme.ribbon(s, d['ribbon'])


def closing(s, d):
    s.text(d['statement'], 36, 190, 1128, 37, theme.TEAL, True, h=105)
    for j, card in enumerate(d['cards']):
        x = 36+j*380
        s.box(x, 329, 368, 179, theme.WHITE, theme.LINE)
        theme.icon(s, card['icon'], x+18, 347, 41, theme.ACCENTS[j], theme.TINTS[j])
        s.text(card['title'], x+77, 349, 272, 24, theme.ACCENTS[j], True, h=36)
        s.text(card['body'], x+20, 413, 328, 22, theme.INK, h=77)
    s.text(d['cost_line'], 36, 539, 1128, 23, theme.INK, True, h=35)
    theme.ribbon(s, d['ribbon'])


BUILDERS = dict(zip(KINDS, (opening, architecture, capabilities, controls, demos, closing)))


def load_source(path=SOURCE):
    data = json.loads(Path(path).read_text('utf-8'))
    if tuple(s['kind'] for s in data['slides']) != KINDS:
        raise ValueError('Expected the six-page AI x MCP narrative')
    if not re.fullmatch(r'[a-f0-9]{40}', data['source_commit']):
        raise ValueError('A pinned source commit is required')
    for slide in data['slides']:
        if not slide.get('notes') or not slide.get('source') or not slide.get('references'):
            raise ValueError('Every slide requires speaker notes, source and references')
    return data


def make_scenes(data):
    scenes = []
    for index, d in enumerate(data['slides']):
        s = page(d, index, data, cover=index == 0)
        BUILDERS[d['kind']](s, d)
        scenes.append(s)
    return scenes


def save_pptx(data, scenes, path):
    theme.save_pptx(data, scenes, path)
    # Reuse the tested native-object writer, not its deployment-specific metadata.
    from pptx import Presentation
    prs = Presentation(path)
    prs.core_properties.subject = 'Web AI 與地端工具的受控執行；內部分享與 Demo'
    prs.core_properties.author = 'AI × MCP Sharing'
    prs.core_properties.keywords = 'AI, MCP, Relay, ChatGPT Web, VS Code, 人工核准'
    for slide, d, scene in zip(prs.slides, data['slides'], scenes):
        artwork = [shape for shape, item in zip(slide.shapes, scene.items)
                   if item.get('art') == 'cover-helper']
        if artwork:
            # Suppress stock Office shadows on each small part; group for one-step editing.
            for shape in artwork:
                shape._element.spPr.append(theme.OxmlElement('a:effectLst'))
            group = slide.shapes.add_group_shape(artwork)
            group.name = 'Cover illustration: AI helper'
            group._element.nvGrpSpPr.cNvPr.set('descr', illustrate_ai_helper.ALT)
        slide.notes_slide.notes_text_frame.text = (
            f"{d['title']}\n資料基準：{data['baseline']} / {data['source_commit']}\n"
            f"建議時間：{d['minutes']} 分鐘\n\n{d['notes']}\n\n原始碼依據：\n" + '\n'.join(d['references']))
    prs.save(path)


def speaker_notes(data):
    parts = [f"# {data['title']}｜講者講稿\n\n"
             f"{len(data['slides'])} 頁，約 {sum(s['minutes'] for s in data['slides']):g} 分鐘（含 Demo）。\n\n"
             f"原始碼基準：`{data['source_commit']}`；{data['baseline']}。\n\n"
             '這是口語講稿，不是 Demo 已執行的紀錄；資料外送與系統操作須先獲公司允許。\n']
    for n, d in enumerate(data['slides'], 1):
        parts.append(f"## {n}｜{d['title']}\n\n建議 {d['minutes']:g} 分鐘。\n\n{d['notes']}\n\n"
                     '來源：\n' + '\n'.join(f'- {r}' for r in d['references']) + '\n')
    return '\n'.join(parts)


def build(source=SOURCE, output_dir=None, pptx_only=False, with_previews=False):
    source = Path(source).resolve()
    output = Path(output_dir or source.parent).resolve()
    for name in ('journey', 'poc-implementation-review', 'poc-direct-agent-concept'):
        protected = (ROOT / 'docs/presentations' / name).resolve()
        if output == protected or output.is_relative_to(protected):
            raise ValueError('Refusing to overwrite a historical presentation')
    if pptx_only and with_previews:
        raise ValueError('--previews requires actual PowerPoint PDF export')
    data = load_source(source)
    scenes = make_scenes(data)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ai-mcp-sharing-') as tmp:
        stage = Path(tmp)
        pptx, pdf = stage/f'{STEM}.pptx', stage/f'{STEM}.pdf'
        save_pptx(data, scenes, pptx)
        (stage/'speaker-notes.md').write_text(speaker_notes(data), encoding='utf-8')
        if not pptx_only:
            subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                            '-File', str(ROOT/'tools/export_presentation_pdf.ps1'),
                            '-InputPath', str(pptx), '-OutputPath', str(pdf)], check=True)
            import pymupdf
            norm = lambda value: re.sub(r'\s+', '', value)
            with pymupdf.open(pdf) as document:
                if len(document) != len(scenes):
                    raise ValueError('PowerPoint export page count mismatch')
                for n, (page_, scene) in enumerate(zip(document, scenes)):
                    visible = norm(page_.get_text())
                    for item in scene.items:
                        if item['kind'] == 'text' and norm(item['value']) not in visible:
                            raise ValueError(f'PDF missing text on page {n+1}: {item["value"]}')
            if with_previews:
                theme.previews(pdf, stage)
                with pymupdf.open(pdf) as document:
                    document[0].get_pixmap(
                        matrix=pymupdf.Matrix(3, 3),
                        clip=pymupdf.Rect(804, 93, 1164, 413), alpha=False,
                    ).save(stage/'cover-ai-helper.png')
        for generated in stage.iterdir():
            temporary = output/(generated.name+'.publishing')
            try:
                shutil.copyfile(generated, temporary)
                temporary.replace(output/generated.name)
            finally:
                temporary.unlink(missing_ok=True)
        if with_previews:
            # Remove only obsolete numbered previews owned by this deck after a full build.
            for preview in output.glob('preview-*.png'):
                match = re.fullmatch(r'preview-(\d+)\.png', preview.name)
                if match and int(match[1]) > len(scenes):
                    preview.unlink()
    print(f'Built {len(scenes)} slides: {output / (STEM + ".pptx")}')
    return scenes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--font-dir', type=Path, default=theme.FONT_DIR)
    parser.add_argument('--pptx-only', action='store_true')
    parser.add_argument('--previews', action='store_true')
    args = parser.parse_args()
    theme.FONT_DIR = args.font_dir
    build(args.source, args.output_dir, args.pptx_only, args.previews)
