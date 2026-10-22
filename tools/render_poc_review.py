"""Native-object POC review deck, independent of every historical Journey deck.

Source: docs/presentations/poc-implementation-review/deck.json
PDF is exported from the actual PPTX by desktop PowerPoint, never redrawn.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/presentations/poc-implementation-review/deck.json'
STEM = 'gitlab-ado-poc-review'
W, H = 1200, 675
FONT = 'Microsoft JhengHei'
FONT_DIR = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
PAPER, WHITE = '#FCFBF7', '#FFFFFF'
INK, MUTED, LINE = '#18394B', '#506B77', '#DCE4E4'
BLUE, TEAL, ORANGE, RED = '#126DB5', '#00786F', '#AC4E16', '#A83C3C'
SKY, MINT, SAND, ROSE = '#EAF3FC', '#E6F4ED', '#FFF0DB', '#FAECE7'
ACCENTS = [BLUE, TEAL, ORANGE, BLUE, TEAL]
TINTS = [SKY, MINT, SAND, SKY, MINT]


@lru_cache(maxsize=100)
def font(size: float, bold: bool = False):
    return ImageFont.truetype(str(FONT_DIR / ('msjhbd.ttc' if bold else 'msjh.ttc')), round(size * 4))


def width(value, size, bold=False):
    return font(size, bold).getlength(value) / 4


def wrap(value, max_width, size, bold=False):
    """Wrap CJK freely, but keep API paths and Latin words intact when possible."""
    lines = []
    for paragraph in value.split('\n'):
        tokens = re.findall(r'[A-Za-z0-9_./:{}?=+&@#%()\-]+|[^\x00-\x7f]|\s+|.', paragraph)
        line = ''
        for token in tokens:
            if width(line + token, size, bold) <= max_width:
                line += token
                continue
            if line.strip():
                lines.append(line.rstrip())
                line = ''
            if width(token, size, bold) <= max_width:
                line = token.lstrip()
            else:
                for ch in token:
                    if line and width(line + ch, size, bold) > max_width:
                        lines.append(line)
                        line = ''
                    line += ch
        lines.append(line.rstrip())
    return lines


class Scene:
    def __init__(self):
        self.items = []

    def box(self, x, y, w, h, fill=WHITE, stroke=None, radius=15, form='round', dashed=False):
        self.items.append(dict(kind='box', x=x, y=y, w=w, h=h, fill=fill,
                               stroke=stroke, radius=radius, form=form, dashed=dashed))

    def text(self, value, x, y, w, size=18, color=INK, bold=False, h=None, align='left', role='body'):
        lines = wrap(value, w - 2, size, bold)
        measured = len(lines) * size * 1.27
        if h is not None and measured > h + .1:
            raise ValueError(f'Text overflow ({measured:.1f} > {h}): {value}')
        height = h if h is not None else measured + 3
        if x < 0 or y < 0 or x+w > W+.1 or y+height > H+.1:
            raise ValueError(f'Text outside slide: {value}')
        self.items.append(dict(kind='text', value=value, lines=lines, x=x, y=y, w=w, h=height,
                               size=size, color=color, bold=bold, align=align, role=role,
                               measured=measured))
        return measured

    def path(self, points, color=INK, thickness=2, dashed=False, arrow=False, role='connection'):
        self.items.append(dict(kind='path', points=points, color=color, thickness=thickness,
                               dashed=dashed, arrow=arrow, role=role))

    def circle(self, x, y, radius, fill=WHITE, stroke=None):
        self.box(x-radius, y-radius, radius*2, radius*2, fill, stroke, form='ellipse')


def rounded(points, r=12):
    """Sample rounded orthogonal corners as one editable native freeform."""
    if len(points) < 3:
        return points
    result = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        dab, dbc = math.dist(a, b), math.dist(b, c)
        rad = min(r, dab/2, dbc/2)
        start = (b[0]+(a[0]-b[0])*rad/dab, b[1]+(a[1]-b[1])*rad/dab)
        end = (b[0]+(c[0]-b[0])*rad/dbc, b[1]+(c[1]-b[1])*rad/dbc)
        result.append(start)
        for step in range(1, 9):
            t = step/8
            result.append(((1-t)**2*start[0]+2*(1-t)*t*b[0]+t*t*end[0],
                           (1-t)**2*start[1]+2*(1-t)*t*b[1]+t*t*end[1]))
    return result + [points[-1]]


def route(s, stops, color=BLUE, thickness=10, track=True, dashed=False):
    pts = []
    for a, d in zip(stops, stops[1:]):
        b = (a[0]+(d[0]-a[0])*.45, a[1])
        c = (d[0]-(d[0]-a[0])*.45, d[1])
        for step in range(33):
            t = step/32
            pts.append(((1-t)**3*a[0]+3*(1-t)**2*t*b[0]+3*(1-t)*t*t*c[0]+t**3*d[0],
                        (1-t)**3*a[1]+3*(1-t)**2*t*b[1]+3*(1-t)*t*t*c[1]+t**3*d[1]))
    s.path(pts, color, thickness, dashed)
    if track and not dashed:
        s.path(pts, WHITE, 1.3)


def node(s, x, y, label, color=BLUE, radius=20):
    s.circle(x, y+3, radius+2, '#E0E5E0')
    s.circle(x, y, radius+2, WHITE, color)
    s.circle(x, y, radius-3, color)
    s.text(label, x-radius, y-10, radius*2, 14, WHITE, True, align='center', h=22)


def icon(s, name, x, y, size=48, color=BLUE, fill=SKY):
    """Original line icons; never embeds reference photographs or bitmaps."""
    k = size/48
    def line(points, weight=2):
        s.path([(x+a*k, y+b*k) for a, b in points], color, weight*k, role='icon')
    def box(a, b, w, h):
        s.box(x+a*k, y+b*k, w*k, h*k, fill, color, 4*k)
    def dot(a, b, r=2):
        s.circle(x+a*k, y+b*k, r*k, color)
    if name == 'pipeline':
        for a in (2, 19, 36):
            box(a, 17, 10, 16)
        line([(12, 25), (19, 25)])
        line([(29, 25), (36, 25)])
        line([(15, 22), (18, 25), (15, 28)])
        line([(32, 22), (35, 25), (32, 28)])
        line([(7, 11), (7, 6), (41, 6), (41, 11)], 1.5)
    elif name == 'shield':
        line([(24, 4), (42, 11), (39, 30), (33, 39), (24, 45), (15, 39), (9, 30), (6, 11), (24, 4)])
        line([(15, 24), (22, 31), (34, 17)], 3)
    elif name == 'flag':
        line([(10, 43), (10, 5)], 2.5)
        line([(10, 6), (26, 6), (26, 12), (40, 12), (34, 22), (22, 22), (22, 16), (10, 16)])
        line([(4, 43), (18, 43)])
    elif name == 'server':
        for b in (5, 18, 31):
            box(8, b, 32, 10)
            dot(13, b+5, 1.5)
            line([(26, b+5), (35, b+5)], 1.5)
    elif name == 'people':
        for a, b in ((15, 14), (33, 14), (24, 8)):
            s.circle(x+a*k, y+b*k, 5*k, fill, color)
        for a, b in ((5, 27), (28, 27), (14, 23)):
            box(a, b, 15, 17)
    elif name == 'check':
        box(10, 8, 30, 35)
        box(17, 4, 15, 8)
        line([(16, 21), (20, 25), (28, 17)], 2.5)
        line([(16, 33), (20, 37), (28, 29)], 2.5)
        line([(31, 23), (35, 23)], 1.5)
        line([(31, 35), (35, 35)], 1.5)
    elif name == 'code':
        box(3, 6, 42, 32)
        line([(3, 14), (45, 14)])
        for a in (8, 13, 18):
            dot(a, 10, 1)
        line([(18, 20), (12, 25), (18, 30)])
        line([(30, 20), (36, 25), (30, 30)])
        line([(26, 18), (22, 33)])
        line([(17, 43), (31, 43)])
    elif name == 'key':
        s.circle(x+15*k, y+16*k, 10*k, fill, color)
        s.circle(x+15*k, y+16*k, 3*k, WHITE, color)
        line([(22, 23), (42, 43), (45, 40), (40, 35), (36, 39), (32, 35), (35, 31)], 2.5)
    elif name == 'restore':
        line([(10, 17), (16, 9), (31, 8), (40, 18), (40, 31), (31, 40), (18, 40), (9, 32)], 2.5)
        line([(10, 5), (10, 17), (22, 17)], 2.5)
        line([(24, 18), (24, 27), (31, 31)])
    else:
        raise ValueError(f'Unknown icon {name}')


def pill(s, value, x, y, w, color=TEAL, fill=MINT, size=14):
    s.box(x, y, w, 30, fill, radius=15)
    s.text(value, x+8, y+5, w-16, size, color, True, h=22, align='center')


def ribbon(s, text, y=583, color=TEAL, fill=MINT):
    s.box(36, y, 1128, 42, fill, radius=18)
    s.circle(54, y+21, 4, color)
    s.text(text, 68, y+10, 1080, 16.5, color, True, h=26)


def page(data, index, total, baseline):
    s = Scene()
    s.box(0, 0, W, H, PAPER, form='rect')
    s.text(f"WINDOWS  /  POC TO PILOT  ·  {baseline}", 36, 23, 690, 13, TEAL, True, h=20)
    pill(s, data['chapter'], 940, 17, 224, INK, '#EEF0E9')
    s.text(data['title'], 36, 66, 1130, 34, INK, True, h=48, role='title')
    s.text(data['subtitle'], 36, 122, 1128, 18.5, MUTED, h=48)
    s.path([(36, 640), (1164, 640)], LINE, 1)
    s.text(data['source'], 36, 650, 992, 11.5, MUTED, h=19, role='source')
    s.text(f'{index+1:02d} / {total:02d}', 1092, 649, 72, 13, MUTED, True, h=22, align='center')
    return s


def outcome(s, d):
    s.text(d['eyebrow'], 36, 185, 1050, 21, TEAL, True, h=30)
    stops = [(100, 267), (548, 267), (1012, 267)]
    route(s, stops[:2], BLUE, 12)
    route(s, stops[1:], TEAL, 12)
    for j, (x, y) in enumerate(stops):
        node(s, x, y, f'0{j+1}', ACCENTS[j])
        s.box(x-5, y-50, 260 if j < 2 else 160, 31, PAPER)
        s.text(d['route'][j], x-3, y-47, 250 if j < 2 else 150, 18, ACCENTS[j], True, h=26)
    for j, card in enumerate(d['cards']):
        x = 36+j*380
        s.box(x, 325, 368, 222, WHITE, LINE)
        icon(s, card['icon'], x+20, 343, 48, ACCENTS[j], TINTS[j])
        s.text(card['title'], x+20, 408, 328, 25, INK, True, h=36)
        s.text(card['body'], x+20, 459, 328, 17.3, MUTED, h=72)
    ribbon(s, d['ribbon'])


def architecture(s, d):
    zones = [(36, 246, SKY, BLUE), (308, 514, '#F0F3EB', INK), (848, 316, MINT, TEAL)]
    for j, (x, w, tint, color) in enumerate(zones):
        s.box(x, 180, w, 394, tint)
        icon(s, ['code', 'shield', 'server'][j], x+14, 190, 30, [BLUE, ORANGE, TEAL][j], tint)
        s.text(d['zones'][j], x+52, 192, w-62, [19, 21, 20][j], color, True, h=30)
        s.text(d['boundaries'][j], x+12, 552, w-24, 13, color, True, h=20, align='center')
    # Logical control/data direction. Target's physical caller arrow points LEFT to ADO.
    links = [
        ([(262, 266), (330, 266)], BLUE, 2, True, 'notification'),
        ([(520, 266), (552, 266)], BLUE, 2, True, 'fetch-start'),
        ([(598, 329), (598, 352), (294, 352), (294, 438), (262, 438)], BLUE, 2, True, 'gitlab-get'),
        ([(262, 470), (306, 470), (306, 379), (650, 379), (650, 329)], BLUE, 4, False, 'artifact-response'),
        ([(744, 329), (744, 400), (425, 400), (425, 420)], BLUE, 3, False, 'verified-artifact'),
        ([(520, 453), (552, 453)], ORANGE, 3, False, 'authorization'),
        ([(870, 252), (822, 252)], TEAL, 2.5, True, 'agent-outbound'),
        ([(800, 460), (834, 460), (834, 303), (870, 303)], BLUE, 4, False, 'authorized-job-response'),
        ([(1006, 329), (1006, 420)], TEAL, 2.5, True, 'broker-request'),
        ([(1006, 484), (1006, 518)], TEAL, 2.5, False, 'iis-switch')
    ]
    for pts, color, weight, dash, role in links:
        s.path(rounded(pts), color, weight, dash, True, role)
    # Numbered boxes: CI / GitLab artifact / notification / Fetch / ADO artifact / approval / agent / broker.
    coords = [(56, 235, 206, 94), (56, 420, 206, 64), (330, 235, 190, 94),
              (552, 235, 248, 94), (330, 420, 190, 64), (552, 420, 248, 84),
              (870, 235, 272, 94), (870, 420, 272, 64)]
    for j, (card, (x, y, w, h)) in enumerate(zip(d['nodes'], coords)):
        color = ORANGE if j == 5 else TEAL if j >= 6 else BLUE
        s.box(x, y, w, h, SAND if j == 5 else WHITE, color if j in (5, 7) else None)
        s.text(card['title'], x+12, y+10, w-24, 17 if j in (1, 4) else 18, color, True, h=26)
        s.text(card['body'], x+12, y+40, w-24, 14 if j in (1, 4, 7) else 15, INK, h=h-42)
    s.text(d['fetch_label'], 330, 334, 254, 13, BLUE, h=18)
    s.text(d['download_label'], 350, 360, 290, 13, BLUE, h=18)
    s.text(d['store_label'], 540, 402, 190, 12, BLUE, h=18)
    s.text(d['repo_label'], 330, 522, 470, 14.5, INK, True, h=24)
    s.box(870, 518, 272, 30, WHITE)
    s.text(d['target_label'], 878, 524, 256, 13.5, TEAL, True, h=21, align='center')
    s.text(d['legend'], 36, 583, 1128, 13, MUTED, h=20)
    s.text(d['network'], 36, 609, 1128, 14.5, INK, True, h=23)


def evidence(s, d):
    for x, w, text in zip([52, 355, 931], [280, 550, 215], d['headers']):
        s.text(text, x, 183, w, 15, MUTED, True, h=24)
    for j, row in enumerate(d['rows']):
        y = 216+j*67
        s.box(36, y, 1128, 59, WHITE, LINE, radius=12)
        s.box(36, y, 6, 59, ACCENTS[j], radius=3)
        s.text(row[0], 53, y+17, 285, 20, INK, True, h=29)
        s.text(row[1], 355, y+17, 553, 17.5, INK, h=29)
        s.text(row[2], 931, y+10, 214, 14, MUTED, h=40)
    for j, card in enumerate(d['limits']):
        x = 36+j*380
        tint, color = [(SAND, ORANGE), (ROSE, RED), (MINT, TEAL)][j]
        s.box(x, 509, 368, 113, tint)
        s.text(card['title'], x+18, 521, 332, 20, color, True, h=28)
        s.text(card['body'], x+18, 559, 332, 16, INK, h=54)


def credentials(s, d):
    for j, card in enumerate(d['cards']):
        x = 36+j*574
        color, tint = [(BLUE, SKY), (TEAL, MINT)][j]
        s.box(x, 180, 554, 353, WHITE, LINE)
        s.box(x, 180, 554, 63, tint)
        icon(s, 'key', x+18, 192, 38, color, tint)
        s.text(card['title'], x+72, 195, 462, 24 if j == 0 else 22, color, True, h=36)
        s.text(card['direction'], x+20, 261, 514, 20, color, True, h=30)
        s.text(card['api'], x+20, 304, 514, 16, INK, h=69)
        s.text(card['scope'], x+20, 386, 514, 19, color, True, h=28)
        s.text(card['acl'], x+20, 424, 514, 17, INK, h=47)
        s.text(card['storage'], x+20, 485, 514, 15, MUTED, h=43)
    s.text(d['other_title'], 36, 549, 1128, 19, ORANGE, True, h=28)
    s.text(d['other_body'], 36, 581, 1128, 16, INK, h=24)
    s.text(d['rollback'], 36, 610, 1128, 14.5, MUTED, h=22)


def licensing(s, d):
    s.box(36, 180, 1128, 75, SKY)
    icon(s, 'people', 52, 192, 48, BLUE, SKY)
    s.text(d['gitlab_title'], 120, 191, 375, 24, BLUE, True, h=35)
    s.text(d['gitlab_body'], 526, 194, 613, 17.5, INK, h=48)
    for j, (title, body) in enumerate(d['roles']):
        x = 36+j*228
        s.box(x, 280, 216, 85, WHITE, LINE)
        s.circle(x+22, 302, 11, ACCENTS[j])
        s.text(str(j+1), x+12, 293, 20, 12, WHITE, True, h=18, align='center')
        s.text(title, x+43, 290, 159, 20, INK, True, h=28)
        s.text(body, x+13, 332, 190, 15.5, MUTED, h=23, align='center')
    s.text(d['why_title'], 36, 390, 210, 22, TEAL, True, h=30)
    s.text(d['why'], 254, 389, 910, 18, INK, h=47)
    s.box(36, 451, 1128, 127, SAND)
    s.text(d['gate_title'], 54, 464, 1092, 21, ORANGE, True, h=30)
    for j, text in enumerate(d['gates']):
        s.circle(59, 509+j*24, 3, ORANGE)
        s.text(text, 73, 499+j*24, 1069, 16, INK, h=24)
    s.text(d['fallback'], 36, 599, 1128, 17, RED, True, h=27)


def recovery(s, d):
    for j, lane in enumerate(d['lanes']):
        y = 181+j*128
        color, tint = [(BLUE, SKY), (TEAL, MINT), (ORANGE, SAND)][j]
        s.box(36, y, 1128, 116, tint, color if j == 2 else None, dashed=(j == 2))
        pill(s, lane['badge'], 52, y+12, 108, color, WHITE, 14)
        s.text(lane['title'], 52, y+56, 270, 21, color, True, h=33)
        for k, step in enumerate(lane['steps']):
            x = 362+k*262
            s.box(x, y+15, 238, 42, WHITE)
            s.text(step, x+10, y+24, 218, 17.5, INK, True, h=27, align='center')
            if k < 2:
                s.path([(x+240, y+36), (x+260, y+36)], color, 2, j == 2, True)
        s.text(lane['detail'], 362, y+76, 770, 15.5, INK, h=30)
    ribbon(s, d['ribbon'], y=583, color=ORANGE, fill=SAND)


def security(s, d):
    for x, w, text in zip([54, 265, 504], [190, 210, 636], d['headers']):
        s.text(text, x, 183, w, 15, MUTED, True, h=24)
    for j, row in enumerate(d['rows']):
        y = 216+j*67
        s.box(36, y, 1128, 59, WHITE, LINE, radius=12)
        s.text(row[0], 54, y+15, 190, 19, ACCENTS[j], True, h=30)
        s.text(row[1], 265, y+17, 221, 17, INK, h=28)
        s.text(row[2], 504, y+10, 636, 16, INK, h=45)
    ribbon(s, d['ribbon'], y=583, color=ORANGE, fill=SAND)


def roadmap(s, d):
    stops = [(90, 405), (342, 312), (590, 378), (830, 286), (1090, 360)]
    for j in range(4):
        route(s, stops[j:j+2], ACCENTS[j], 12)
    positions = [(36, 452), (230, 189), (478, 425), (718, 171), (952, 409)]
    for j, (stage, (x, y), (lx, ly)) in enumerate(zip(d['stages'], stops, positions)):
        color = ACCENTS[j]
        node(s, x, y, f'0{j+1}', color, 20)
        # Place illustrations opposite to text, preserving the rise/fall journey.
        iy = y-80 if j % 2 == 0 else y+32
        icon(s, stage['icon'], x-25, iy, 50, color, TINTS[j])
        w = 214 if j < 4 else 212
        s.text(stage['title'], lx, ly, w, 23, color, True, h=33)
        s.text(stage['body'], lx, ly+43, w, 16.5, INK, h=48)
        owner_y = y+99 if j % 2 else ly+96
        s.text(stage['owner'], lx, owner_y, w, 13.5, MUTED, h=42)
    ribbon(s, d['ribbon'], y=589)


def decisions(s, d):
    for j, card in enumerate(d['cards']):
        col, row = j % 2, j // 2
        x, y = 36+col*574, 183+row*189
        color, tint = [(BLUE, SKY), (ORANGE, SAND), (TEAL, MINT), (BLUE, SKY)][j]
        s.box(x, y, 554, 174, WHITE, LINE)
        icon(s, card['icon'], x+18, y+18, 42, color, tint)
        s.text(card['title'], x+78, y+17, 458, 24, color, True, h=35)
        s.text(card['owner'], x+78, y+60, 458, 15, MUTED, h=24)
        s.text(card['body'], x+20, y+104, 514, 18, INK, h=56)
    ribbon(s, d['ribbon'], y=583)


BUILDERS = dict(outcome=outcome, architecture=architecture, evidence=evidence,
                credentials=credentials, licensing=licensing, recovery=recovery,
                security=security, roadmap=roadmap, decisions=decisions)


def load_source(path=SOURCE):
    data = json.loads(Path(path).read_text('utf-8'))
    if not data.get('slides'):
        raise ValueError('No slides')
    for slide in data['slides']:
        if slide['kind'] not in BUILDERS or not slide.get('notes') or not slide.get('source'):
            raise ValueError('Missing layout, speaker notes or evidence source')
    return data


def make_scenes(data):
    scenes = []
    for index, slide in enumerate(data['slides']):
        s = page(slide, index, len(data['slides']), data['baseline'])
        BUILDERS[slide['kind']](s, slide)
        scenes.append(s)
    return scenes


def rgb(value):
    return RGBColor.from_string(value.removeprefix('#'))


def save_pptx(data, scenes, path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Pt(W), Pt(H)
    prs.core_properties.title = data['title']
    prs.core_properties.subject = 'POC evidence review and implementation decisions; not production approval'
    prs.core_properties.author = 'Deployment Governance'
    prs.core_properties.keywords = 'GitLab CE, Azure DevOps Server, Windows, POC, review'
    for d, scene in zip(data['slides'], scenes):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.name = d['title']
        for index, i in enumerate(scene.items):
            kind = i['kind']
            if kind == 'text':
                box = slide.shapes.add_textbox(Pt(i['x']), Pt(i['y']), Pt(i['w']), Pt(i['h']))
                box.name = f"{i['role']}:{index}"
                tf = box.text_frame
                tf.clear()
                tf.word_wrap = False
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = MSO_ANCHOR.TOP
                for n, line in enumerate(i['lines']):
                    p = tf.paragraphs[0] if n == 0 else tf.add_paragraph()
                    p.text = line
                    p.space_before = p.space_after = Pt(0)
                    p.line_spacing = Pt(i['size']*1.27)
                    p.alignment = PP_ALIGN.CENTER if i['align'] == 'center' else PP_ALIGN.LEFT
                    p.font.name, p.font.size = FONT, Pt(i['size'])
                    p.font.bold = i['bold']
                    p.font.color.rgb = rgb(i['color'])
                    for run in p.runs:
                        run.font.name, run.font.size = FONT, Pt(i['size'])
                        run.font.bold = i['bold']
                        run.font.color.rgb = rgb(i['color'])
                        rp = run._r.get_or_add_rPr()
                        ea = OxmlElement('a:ea')
                        ea.set('typeface', FONT)
                        rp.append(ea)
            elif kind == 'box':
                form = {'round': MSO_SHAPE.ROUNDED_RECTANGLE, 'ellipse': MSO_SHAPE.OVAL,
                        'rect': MSO_SHAPE.RECTANGLE}[i['form']]
                shape = slide.shapes.add_shape(form, Pt(i['x']), Pt(i['y']), Pt(i['w']), Pt(i['h']))
                if i['form'] == 'round':
                    shape.adjustments[0] = min(.5, i['radius']/min(i['w'], i['h']))
                shape.fill.solid()
                shape.fill.fore_color.rgb = rgb(i['fill'])
                if i['stroke']:
                    shape.line.color.rgb = rgb(i['stroke'])
                    shape.line.width = Pt(1.2)
                    if i['dashed']:
                        shape.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                else:
                    shape.line.fill.background()
            elif kind == 'path':
                points = [(round(x*100), round(y*100)) for x, y in i['points']]
                builder = slide.shapes.build_freeform(*points[0], scale=127)
                builder.add_line_segments(points[1:], close=False)
                shape = builder.convert_to_shape()
                shape.name = i['role']
                shape.fill.background()
                shape.line.color.rgb = rgb(i['color'])
                shape.line.width = Pt(i['thickness'])
                ln = shape.line._get_or_add_ln()
                ln.set('cap', 'rnd')
                ln.append(OxmlElement('a:round'))
                if i['dashed']:
                    shape.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                if i['arrow']:
                    end = OxmlElement('a:tailEnd')
                    end.set('type', 'triangle')
                    ln.append(end)
        slide.notes_slide.notes_text_frame.text = f"{d['title']}\n資料基準：{data['baseline']}\n\n{d['notes']}\n\n{d['source']}"
    prs.save(path)


def previews(pdf, destination):
    import pymupdf
    doc = pymupdf.open(pdf)
    images = []
    for n, page_ in enumerate(doc):
        pix = page_.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False)
        path = destination / f'preview-{n+1:02d}.png'
        pix.save(path)
        image = Image.open(path).convert('RGB')
        image.thumbnail((576, 324), Image.Resampling.LANCZOS)
        images.append(image)
    doc.close()
    cols, rows = 3, math.ceil(len(images)/3)
    sheet = Image.new('RGB', (cols*600+24, rows*362+24), PAPER)
    draw = ImageDraw.Draw(sheet)
    for n, image in enumerate(images):
        x, y = 24+(n % cols)*600, 24+(n//cols)*362
        sheet.paste(image, (x, y))
        draw.text((x, y+328), f'{n+1:02d}', font=ImageFont.truetype(str(FONT_DIR/'msjhbd.ttc'), 16), fill=INK)
    sheet.save(destination/'overview.png')


def build(source=SOURCE, output_dir=None, pptx_only=False, with_previews=False):
    source = Path(source).resolve()
    output_dir = Path(output_dir or source.parent).resolve()
    # An independent output name AND path guard protect every historical hand-edited deck.
    protected = (ROOT/'docs/presentations/journey').resolve()
    if output_dir == protected or output_dir.is_relative_to(protected):
        raise ValueError('Refusing to write into historical Journey directory')
    if with_previews and pptx_only:
        raise ValueError('--previews requires actual PowerPoint PDF export')
    data = load_source(source)
    scenes = make_scenes(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='poc-review-build-') as tmp:
        stage = Path(tmp)
        pptx = stage/f'{STEM}.pptx'
        save_pptx(data, scenes, pptx)
        if not pptx_only:
            subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                            '-File', str(ROOT/'tools/export_presentation_pdf.ps1'),
                            '-InputPath', str(pptx), '-OutputPath', str(stage/f'{STEM}.pdf')], check=True)
            import pymupdf
            with pymupdf.open(stage/f'{STEM}.pdf') as pdf:
                if len(pdf) != len(scenes):
                    raise ValueError('PowerPoint export page count mismatch')
                normalize = lambda value: re.sub(r'\s+', '', value)
                for index, page_ in enumerate(pdf):
                    page_text = normalize(page_.get_text())
                    for item in scenes[index].items:
                        if item['kind'] == 'text' and normalize(item['value']) not in page_text:
                            raise ValueError(f"PDF missing text on page {index+1}: {item['value']}")
            if with_previews:
                previews(stage/f'{STEM}.pdf', stage)
        # Stage all files before touching any existing delivery; each publish is atomic.
        for generated in stage.iterdir():
            target = output_dir/generated.name
            temporary = output_dir/(generated.name+'.publishing')
            try:
                shutil.copyfile(generated, temporary)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    print(f'Built {len(scenes)} slides in {output_dir}')
    print(f'Source SHA-256: {hashlib.sha256(source.read_bytes()).hexdigest()}')
    return scenes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--pptx-only', action='store_true')
    parser.add_argument('--previews', action='store_true')
    parser.add_argument('--font-dir', type=Path, default=FONT_DIR)
    args = parser.parse_args()
    FONT_DIR = args.font_dir
    build(args.source, args.output_dir, args.pptx_only, args.previews)
