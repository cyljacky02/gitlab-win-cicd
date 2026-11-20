"""Six-page change-checklist automation talk using the existing POC native-object theme.

Content and speaker notes: docs/presentations/change-checklist-automation/deck.json.
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

import render_poc_review as theme

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/presentations/change-checklist-automation/deck.json'
STEM = 'change-checklist-automation'
KINDS = ('opening', 'compare', 'flow', 'card', 'pilot', 'closing')
PROTECTED = ('journey', 'poc-implementation-review', 'poc-direct-agent-concept',
             'ai-mcp-sharing', 'midterm-report')
HUMAN, AUTO = (theme.ORANGE, theme.SAND), (theme.TEAL, theme.MINT)
ART = '變更清單（Excel）自動產生 Teams 卡片，卡片上有完成、失敗、取消三個按鈕。'


def page(d, index, data, cover=False):
    s = theme.Scene()
    s.box(0, 0, theme.W, theme.H, theme.PAPER, form='rect')
    s.text('變更審核清單  /  M365 自動化', 36, 23, 850, 13, theme.TEAL, True, h=20)
    theme.pill(s, d['chapter'], 940, 17, 224, theme.INK, '#EEF0E9')
    if not cover:
        s.text(d['title'], 36, 66, 1128, 34, theme.INK, True, h=48, role='title')
        s.text(d['subtitle'], 36, 122, 1128, 20, theme.MUTED, h=54)
    s.path([(36, 640), (1164, 640)], theme.LINE, 1)
    s.text(d['source'], 36, 650, 1032, 11.5, theme.MUTED, h=19, role='source')
    s.text(f'{index+1:02d} / {len(data["slides"]):02d}', 1092, 649, 72, 13,
           theme.MUTED, True, h=22, align='center')
    return s


def mini_card(s, x, y, w, h):
    """A sheet-to-card illustration for the cover, drawn with editable shapes only."""
    start = len(s.items)
    # Excel sheet with a header row, grid and a filled "Y" result cell.
    s.box(x, y, 196, 150, theme.WHITE, theme.LINE, 10)
    s.box(x, y, 196, 32, theme.MINT, radius=10)
    s.box(x, y+20, 196, 12, theme.MINT, form='rect')
    for k in range(1, 4):
        s.path([(x+10, y+32+k*28), (x+186, y+32+k*28)], theme.LINE, 1.2, role='illustration')
    for c in (70, 140):
        s.path([(x+c, y+32), (x+c, y+142)], theme.LINE, 1.2, role='illustration')
    s.box(x+146, y+66, 36, 22, theme.TEAL, radius=5)
    s.path([(x+156, y+71), (x+164, y+79), (x+172, y+71)], theme.WHITE, 2, role='illustration')
    s.path([(x+164, y+79), (x+164, y+84)], theme.WHITE, 2, role='illustration')
    for k in range(3):
        s.box(x+14, y+40+k*28, 44, 10, theme.SKY, radius=4)
        s.box(x+82, y+40+k*28, 44, 10, '#EEF0E9', radius=4)
    # Curved hand-off arrow to the card.
    s.path(theme.rounded([(x+98, y+152), (x+98, y+196), (x+116, y+196)], 14),
           theme.TEAL, 2.5, arrow=True, role='illustration')
    # Teams-style card with three response buttons (no tiny labels).
    cx, cy = x+120, y+108
    s.box(cx, cy, w-120, h-108, theme.WHITE, theme.BLUE, 12)
    s.box(cx+1, cy+1, w-122, 40, theme.SKY, radius=11)
    s.box(cx+1, cy+26, w-122, 15, theme.SKY, form='rect')
    s.circle(cx+24, cy+21, 10, theme.BLUE)
    s.box(cx+42, cy+15, 110, 12, theme.BLUE, radius=6)
    for k, width in enumerate((150, 120)):
        s.box(cx+16, cy+58+k*22, width, 10, '#E3E9EA', radius=5)
    s.box(cx+16, cy+106, w-152, 26, theme.WHITE, theme.LINE, 6)
    bw = (w-120-32-16)/3
    for k, color in enumerate((theme.TEAL, theme.RED, theme.MUTED)):
        s.box(cx+16+k*(bw+8), cy+146, bw, 26, color, radius=13)
    # Orange "reported" badge.
    bx = cx+w-142
    s.circle(bx, cy+4, 18, theme.ORANGE)
    s.path([(bx-9, cy+4), (bx-2, cy+11), (bx+10, cy-3)], theme.WHITE, 3, role='illustration')
    for item in s.items[start:]:
        item['art'] = 'cover-card'


def opening(s, d):
    s.text(d['display_title'], 36, 80, 800, 42, theme.INK, True, h=166, role='title')
    s.text(d['subtitle'], 36, 264, 800, 21, theme.MUTED, h=32)
    s.text(d['hook'], 36, 322, 800, 23, theme.TEAL, True, h=62)
    mini_card(s, 864, 96, 300, 300)
    for j, card in enumerate(d['cards']):
        x = 36+j*380
        s.box(x, 432, 368, 128, theme.WHITE, theme.LINE)
        s.text(card['title'], x+18, 448, 332, 22, theme.ACCENTS[j], True, h=33)
        s.text(card['body'], x+18, 494, 332, 19, theme.INK, h=53)
    theme.ribbon(s, d['ribbon'])


def compare(s, d):
    for x, w, text in zip([54, 268, 718], [190, 400, 440], d['headers']):
        s.text(text, x, 184, w, 16, theme.MUTED, True, h=24)
    for j, row in enumerate(d['rows']):
        y = 216+j*118
        color = theme.ACCENTS[j]
        s.box(36, y, 1128, 104, theme.WHITE, theme.LINE)
        s.box(36, y, 6, 104, color, radius=3)
        s.text(row['title'], 56, y+36, 180, 23, color, True, h=34)
        s.box(250, y+14, 412, 76, theme.SAND, radius=12)
        s.text(row['before'], 268, y+52-18*1.27/2, 380, 18, theme.INK, h=28)
        s.path([(672, y+52), (694, y+52)], theme.TEAL, 2.5, arrow=True, role='before-after')
        s.box(704, y+14, 444, 76, theme.MINT, radius=12)
        lines = len(theme.wrap(row['after'], 410, 18.5, True))
        s.text(row['after'], 722, y+52-lines*18.5*1.27/2, 412, 18.5, theme.INK, True, h=52)
    theme.ribbon(s, d['ribbon'], y=583)


def flow(s, d):
    for j, step in enumerate(d['steps']):
        x = 36+j*290
        color, tint = AUTO if step['auto'] else HUMAN
        s.box(x, 196, 258, 252, tint)
        theme.node(s, x+38, 236, f'0{j+1}', color, 20)
        theme.pill(s, step['who'], x+70, 221, 172, color, theme.WHITE, 14)
        s.text(step['title'], x+20, 282, 220, 26, color, True, h=38)
        s.text(step['body'], x+20, 336, 222, 17.5, theme.INK, h=92)
        if j < 3:
            s.path([(x+262, 322), (x+286, 322)], theme.INK, 2.5, arrow=True, role='step')
    # Results return from the card response (step 4) into the same Excel (step 1).
    # Split around the label instead of masking the line with a shadowed box.
    s.path(theme.rounded([(1071, 450), (1071, 500), (858, 500)]), theme.TEAL, 2.5,
           role='result-return')
    s.path(theme.rounded([(342, 500), (165, 500), (165, 450)]), theme.TEAL, 2.5,
           arrow=True, role='result-return-arrow')
    s.text(d['return_label'], 262, 489, 676, 16.5, theme.TEAL, True, h=24, align='center')
    s.circle(48, 540, 6, theme.ORANGE)
    s.text('人要做的事', 62, 530, 150, 15, theme.INK, h=22)
    s.circle(196, 540, 6, theme.TEAL)
    s.text('自動化完成', 210, 530, 150, 15, theme.INK, h=22)
    theme.ribbon(s, d['ribbon'], y=583, color=theme.ORANGE, fill=theme.SAND)


def card(s, d):
    # Mock Teams card (illustrative only).
    s.box(36, 186, 548, 384, theme.WHITE, theme.LINE)
    s.box(37, 187, 546, 56, theme.SKY, radius=14)
    s.box(37, 220, 546, 23, theme.SKY, form='rect')
    s.circle(66, 215, 13, theme.BLUE)
    s.path([(60, 215), (65, 220), (73, 210)], theme.WHITE, 2.5, role='card-mark')
    s.text(d['card_title'], 90, 201, 300, 21, theme.BLUE, True, h=30)
    for k, (label, value) in enumerate(d['fields']):
        y = 258+k*36
        s.text(label, 58, y, 110, 16, theme.MUTED, True, h=24)
        s.text(value, 170, y, 390, 17, theme.INK, h=24)
    s.box(58, 372, 504, 52, theme.WHITE, theme.LINE, 8, dashed=True)
    s.text(d['input'], 74, 386, 470, 16, theme.MUTED, h=24)
    for k, (label, color) in enumerate(zip(d['buttons'], (theme.TEAL, theme.RED, theme.MUTED))):
        x = 58+k*172
        s.box(x, 442, 160, 42, color, radius=21)
        s.text(label, x, 451, 160, 18, theme.WHITE, True, h=26, align='center')
    s.text(d['caption'], 58, 516, 504, 14, theme.MUTED, h=22)
    for j, (row, color) in enumerate(zip(d['outcomes'], (theme.TEAL, theme.RED, theme.MUTED))):
        y = 186+j*130
        s.box(612, y, 552, 118, theme.WHITE, theme.LINE)
        s.box(612, y, 6, 118, color, radius=3)
        s.text(row['title'], 638, y+42, 90, 24, color, True, h=34)
        s.text(row['body'], 740, y+31, 404, 19, theme.INK, h=54)
    theme.ribbon(s, d['ribbon'], y=583)


def pilot(s, d):
    s.box(36, 186, 520, 384, theme.SAND)
    theme.pill(s, d['pilot_badge'], 58, 206, 180, theme.ORANGE, theme.WHITE, 15)
    s.text(d['pilot_title'], 58, 254, 470, 24, theme.ORANGE, True, h=36)
    for k, item in enumerate(d['pilot_items']):
        y = 316+k*76
        theme.node(s, 78, y+14, str(k+1), theme.ORANGE, 15)
        s.text(item, 108, y, 430, 18, theme.INK, h=50)
    s.path([(566, 378), (594, 378)], theme.TEAL, 3, arrow=True, role='pilot-to-future')
    s.box(604, 186, 560, 384, theme.MINT)
    theme.pill(s, d['future_badge'], 626, 206, 160, theme.TEAL, theme.WHITE, 15)
    s.text(d['future_title'], 626, 254, 500, 24, theme.TEAL, True, h=36)
    for k, lane in enumerate(d['lanes']):
        y = 310+k*126
        color, tint = HUMAN if k == 0 else AUTO
        s.box(626, y, 516, 110, theme.WHITE)
        theme.icon(s, lane['icon'], 646, y+30, 48, color, tint)
        s.text(lane['title'], 714, y+16, 410, 21, color, True, h=30)
        s.text(lane['body'], 714, y+50, 410, 18, theme.INK, h=50)
    theme.ribbon(s, d['ribbon'], y=583)


def closing(s, d):
    s.text(d['statement'], 36, 190, 1128, 37, theme.TEAL, True, h=105)
    for j, item in enumerate(d['cards']):
        x = 36+j*380
        s.box(x, 329, 368, 179, theme.WHITE, theme.LINE)
        theme.icon(s, item['icon'], x+18, 347, 41, theme.ACCENTS[j], theme.TINTS[j])
        s.text(item['title'], x+77, 349, 272, 24, theme.ACCENTS[j], True, h=36)
        s.text(item['body'], x+20, 413, 328, 20, theme.INK, h=77)
    s.text(d['cost_line'], 36, 536, 1128, 23, theme.ORANGE, True, h=35)
    theme.ribbon(s, d['ribbon'])


BUILDERS = dict(zip(KINDS, (opening, compare, flow, card, pilot, closing)))


def load_source(path=SOURCE):
    data = json.loads(Path(path).read_text('utf-8'))
    if tuple(s['kind'] for s in data['slides']) != KINDS:
        raise ValueError('Expected the six-page change automation narrative')
    for slide in data['slides']:
        if not slide.get('notes') or not slide.get('source'):
            raise ValueError('Every slide requires speaker notes and a source line')
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
    from pptx import Presentation
    prs = Presentation(path)
    prs.core_properties.subject = '變更審核清單：Excel Online、Power Automate、Office Scripts 與 Teams 自動通知追蹤'
    prs.core_properties.author = 'Change Checklist Automation'
    prs.core_properties.keywords = 'Excel Online, Power Automate, Office Scripts, Teams, 變更管理'
    for slide, d, scene in zip(prs.slides, data['slides'], scenes):
        artwork = [shape for shape, item in zip(slide.shapes, scene.items)
                   if item.get('art') == 'cover-card']
        if artwork:
            for shape in artwork:
                shape._element.spPr.append(theme.OxmlElement('a:effectLst'))
            group = slide.shapes.add_group_shape(artwork)
            group.name = 'Cover illustration: Excel to Teams card'
            group._element.nvGrpSpPr.cNvPr.set('descr', ART)
        slide.notes_slide.notes_text_frame.text = (
            f"{d['title']}\n資料基準：{data['baseline']}\n建議時間：{d['minutes']:g} 分鐘\n\n{d['notes']}")
    prs.save(path)


def speaker_notes(data):
    parts = [f"# {data['title']}｜講者講稿\n\n"
             f"{len(data['slides'])} 頁，約 {sum(s['minutes'] for s in data['slides']):g} 分鐘。"
             f"{data['baseline']}。\n"]
    for n, d in enumerate(data['slides'], 1):
        parts.append(f"## {n}｜{d['title']}\n\n建議 {d['minutes']:g} 分鐘。\n\n{d['notes']}\n")
    return '\n'.join(parts)


def build(source=SOURCE, output_dir=None, pptx_only=False, with_previews=False):
    source = Path(source).resolve()
    output = Path(output_dir or source.parent).resolve()
    for name in PROTECTED:
        protected = (ROOT / 'docs/presentations' / name).resolve()
        if output == protected or output.is_relative_to(protected):
            raise ValueError('Refusing to overwrite a historical presentation')
    if pptx_only and with_previews:
        raise ValueError('--previews requires actual PowerPoint PDF export')
    data = load_source(source)
    scenes = make_scenes(data)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='change-automation-') as tmp:
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
        for generated in stage.iterdir():
            temporary = output/(generated.name+'.publishing')
            try:
                shutil.copyfile(generated, temporary)
                temporary.replace(output/generated.name)
            finally:
                temporary.unlink(missing_ok=True)
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
