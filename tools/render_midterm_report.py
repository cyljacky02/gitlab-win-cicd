"""Mid-term work report (11 pages) using the existing POC native-object theme/exporter.

Content and speaker notes: docs/presentations/midterm-report/deck.json.
Every shape is a native, editable PowerPoint object; screenshots are dashed placeholders.
Historical decks and shared renderers are never modified.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import render_poc_review as theme
from render_poc_review import (W, H, INK, MUTED, LINE, WHITE, PAPER, BLUE, TEAL, ORANGE, RED,
                               SKY, MINT, SAND, ROSE)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/presentations/midterm-report/deck.json'
STEM = 'midterm-report'
KINDS = ('cover', 'goals', 'calendar', 'scope', 'options', 'poc', 'progress',
         'wincd', 'features', 'learning', 'plan')
STONE = '#F0F3EB'
SLATE = '#5B6F7A'
PLACEHOLDER = '#F4F4EF'
PROTECTED = ('journey', 'poc-implementation-review', 'poc-direct-agent-concept', 'ai-mcp-sharing')


def page(d, index, data, cover=False):
    s = theme.Scene()
    s.box(0, 0, W, H, PAPER, form='rect')
    s.text(data['eyebrow'], 36, 23, 850, 13, TEAL, True, h=20)
    theme.pill(s, d['chapter'], 940, 17, 224, INK, '#EEF0E9')
    if not cover:
        s.text(d['title'], 36, 66, 1128, 34, INK, True, h=48, role='title')
        if d.get('subtitle'):
            s.text(d['subtitle'], 36, 122, 1128, 18.5, MUTED, h=26)
    s.path([(36, 640), (1164, 640)], LINE, 1)
    if d.get('source'):
        s.text(d['source'], 36, 650, 1032, 11.5, MUTED, h=19, role='source')
    s.text(f'{index+1:02d} / {len(data["slides"]):02d}', 1092, 649, 72, 13,
           MUTED, True, h=22, align='center')
    return s


def right_text(s, value, right, y, size, color=INK, bold=False, h=None):
    w = theme.width(value, size, bold) + 4
    s.text(value, right - w, y, w, size, color, bold, h=h)


def check_mark(s, x, y, size=10, color=WHITE, weight=2.2):
    s.path([(x - size*.45, y), (x - size*.1, y + size*.35), (x + size*.5, y - size*.35)],
           color, weight, role='icon')


def status_dot(s, state, x, y, r=13):
    if state == 'done':
        s.circle(x, y, r, TEAL)
        check_mark(s, x, y, r*.95)
    elif state == 'doing':
        s.circle(x, y, r, WHITE, ORANGE)
        s.circle(x, y, r*.45, ORANGE)
    else:
        s.circle(x, y, r, WHITE, '#9AA9B0')


# ---------------------------------------------------------------- 01 cover
def cover(s, d):
    s.text(d['title'], 36, 118, 720, 54, INK, True, h=72, role='title')
    s.text(d['subtitle'], 36, 210, 740, 26, TEAL, True, h=36)
    s.text(d['period'], 36, 262, 740, 20, MUTED, h=28)
    s.path([(36, 316), (120, 316)], ORANGE, 3)
    s.text(d['presenter'], 36, 334, 740, 20, INK, True, h=28, role='presenter')
    # Decorative mini calendar: a teaser of the calendar page, not data.
    x0, y0 = 806, 112
    s.box(x0, y0, 358, 300, WHITE, LINE, radius=14)
    s.box(x0, y0, 358, 42, SKY, radius=14)
    s.box(x0, y0+28, 358, 14, SKY, form='rect')
    s.text('9/29  →  12/28', x0+18, y0+11, 322, 15, BLUE, True, h=21)
    for r in range(4):
        for c in range(5):
            s.box(x0+18+c*64, y0+56+r*58, 64, 58, WHITE, LINE, form='rect')
    bars = [(0, 1, 5, '#5B6F7A', False), (1, 0, 3, '#2A72B2', False), (1, 3, 5, TEAL, False),
            (2, 0, 5, '#0E558F', False), (3, 0, 2, '#0A3D6B', False), (3, 2, 5, '#0A3D6B', True)]
    for r, a, b, color, dashed in bars:
        x, y = x0+18+a*64+4, y0+56+r*58+24
        s.box(x, y, (b-a)*64-8, 16, WHITE if dashed else color, color if dashed else None,
              radius=8, dashed=dashed)
    theme.ribbon(s, d['ribbon'])


# ---------------------------------------------------------------- 02 goals
def goals(s, d):
    specs = [(36, 660, BLUE, SKY), (712, 452, SLATE, STONE)]
    for goal, (x, w, color, tint) in zip(d['goals'], specs):
        y = 176
        s.box(x, y, w, 236, WHITE, LINE)
        s.box(x, y, w, 8, color, radius=4)
        theme.icon(s, goal['icon'], x+22, y+30, 48, color, tint)
        s.text(goal['title'], x+86, y+38, w-214, 25, INK, True, h=34)
        s.text(goal['weight'], x+w-124, y+26, 110, 40, color, True, h=54, align='center')
        s.text(goal['body'], x+24, y+104, w-48, 17, INK, h=46)
        pw = theme.width(goal['status'], 15, True) + 42
        s.box(x+24, y+176, pw, 36, tint, radius=18)
        s.text(goal['status'], x+42, y+183, pw-34, 15, color, True, h=22)
    # Three-month axis 9/29 -> 12/28; solid until mid-term, dashed after.
    start, end = date(2026, 9, 29), date(2026, 12, 28)
    x1, x2, y = 92, 1108, 506
    pos = lambda m, dd: x1 + (date(2026, m, dd) - start).days / (end - start).days * (x2 - x1)
    mid = pos(11, 13)
    s.path([(x1, y), (mid, y)], BLUE, 6, role='axis-done')
    s.path([(mid, y), (x2, y)], '#C9D2D6', 6, role='axis-plan')
    for k, point in enumerate(d['axis']):
        m, dd = (int(v) for v in re.findall(r'\d+', point['date'])[:2])
        x = pos(m, dd)
        color = BLUE if point['done'] else ORANGE
        s.circle(x, y, 10, WHITE, color)
        s.circle(x, y, 5, color)
        above = k % 2 == 1
        ty = y-60 if above else y+18
        s.text(point['date'], x-75, ty, 150, 15, color, True, h=21, align='center')
        s.text(point['label'], x-75, ty+22, 150, 14, INK, h=20, align='center')
    theme.ribbon(s, d['ribbon'])


# ---------------------------------------------------------------- 03 calendar
CAL_X, CAL_TOP, ROW_TOP, ROW_H = 36, 124, 148, 57
COL_W = [128]*5 + [56]*2
COL_X = [CAL_X + sum(COL_W[:i]) for i in range(7)]
CAL_RIGHT = COL_X[-1] + COL_W[-1]
LANES = {0: (15, 18, 10.5), 1: (35, 13, 9.5), 2: (50, 4, 0)}
CARD_X, CARD_W, GUTTER = 830, 334, 806


def parse(value):
    return date.fromisoformat(value)


def segments(start, first, last, weeks):
    """Split [first, last] into one segment per calendar week row."""
    for r in range(weeks):
        row_start = start + timedelta(days=7*r)
        a, b = max(first, row_start), min(last, row_start + timedelta(days=6))
        if a <= b:
            yield r, (a - row_start).days, (b - row_start).days


def calendar(s, d):
    start, weeks, planned = parse(d['start']), d['weeks'], parse(d['planned_from'])
    if start.weekday() != 0:
        raise ValueError('Calendar must start on a Monday')
    for c, label in enumerate('一二三四五六日'):
        s.text(label, COL_X[c], CAL_TOP, COL_W[c], 13, MUTED, True, h=20, align='center')
    flags = {parse(f['date']): f['label'] for f in d['flags']}
    for r in range(weeks):
        for c in range(7):
            day = start + timedelta(days=7*r + c)
            x, y = COL_X[c], ROW_TOP + r*ROW_H
            s.box(x, y, COL_W[c], ROW_H, '#F2F3EE' if c >= 5 else WHITE, LINE, form='rect')
            label = f'{day.month}/{day.day}' if (day.day == 1 or (r == 0 and c == 0)) else str(day.day)
            s.text(label, x+4, y+1, 34, 10, MUTED, day.day == 1, h=14, role='date')
            if day in flags:
                fx = x+40
                s.path([(fx, y+13), (fx, y+2)], ORANGE, 1.5, role='flag')
                s.path([(fx, y+2), (fx+8, y+5), (fx, y+8)], ORANGE, 1.5, role='flag')
                s.text(flags[day], fx+11, y+1, COL_W[c]-55, 9.5, ORANGE, True, h=14, role='flag')
    # Thin maintenance lane underneath everything.
    m = d['maintenance']
    for r, a, b in segments(start, parse(m['start']), parse(m['end']), weeks):
        y = ROW_TOP + r*ROW_H + LANES[2][0]
        s.box(COL_X[a]+3, y, COL_X[b]+COL_W[b]-COL_X[a]-6, LANES[2][1], m['color'], radius=2)
    anchors = []
    for ev in d['events']:
        dy, bh, size = LANES[ev['lane']]
        segs = list(segments(start, parse(ev['start']), parse(ev['end']), weeks))
        for k, (r, a, b) in enumerate(segs):
            x1, x2 = COL_X[a]+3, COL_X[b]+COL_W[b]-3
            y = ROW_TOP + r*ROW_H + dy
            dashed = start + timedelta(days=7*r) >= planned
            s.box(x1, y, x2-x1, bh, WHITE if dashed else ev['color'],
                  ev['color'] if dashed else None, radius=bh/2, dashed=dashed)
            label = ev['labels'][k] if k < len(ev['labels']) else ''
            if label:
                if theme.width(label, size, True) > x2-x1-14:
                    raise ValueError(f'Calendar label too long: {label}')
                s.text(label, x1+7, y+(bh-size*1.27)/2, x2-x1-10, size,
                       ev['color'] if dashed else WHITE, True, h=size*1.27+.2, role='bar')
            if r == ev['anchor']:
                anchors.append((ev, x2, y+bh/2))
        if ev['anchor'] not in [r for r, _, _ in segs]:
            raise ValueError(f'Anchor row outside event {ev["id"]}')
    # Cards, ordered top-to-bottom; one elbow connector each, sharing a gutter.
    previous = 0
    for i, (ev, ax, ay) in enumerate(anchors):
        y = CAL_TOP + i*86
        cy = y + 38
        if ay < previous:
            raise ValueError('Connector anchors must be monotonic to avoid crossings')
        previous = max(ay, cy)
        s.box(CARD_X, y, CARD_W, 76, WHITE, LINE, radius=10)
        s.box(CARD_X, y, 6, 76, ev['color'], radius=3)
        s.circle(CARD_X+26, y+20, 11, ev['color'])
        s.text(str(ev['id']), CARD_X+15, y+12, 22, 12, WHITE, True, h=16, align='center')
        s.text(ev['title'], CARD_X+44, y+10, 180, 14, INK, True, h=20)
        right_text(s, ev['dates'], CARD_X+CARD_W-12, y+12, 11.5, MUTED, True, h=17)
        s.text(ev['body'], CARD_X+18, y+36, CARD_W-30, 11.5, INK, h=30)
        points = [(ax+2, ay), (GUTTER, ay), (GUTTER, cy), (CARD_X-3, cy)]
        if abs(ay - cy) < 1:
            points = [(ax+2, ay), (CARD_X-3, cy)]
        s.path(theme.rounded(points, 7), ev['color'], 1.6, arrow=True, role=f'connector-{ev["id"]}')
    # Legend under the grid.
    x, y = CAL_X, ROW_TOP + weeks*ROW_H + 9
    for item in d['legend']:
        if item['swatch'] == 'dashed':
            s.box(x, y+3, 22, 11, WHITE, MUTED, radius=5, dashed=True)
        else:
            s.box(x, y+3, 22, 11, item['swatch'], radius=5)
        s.text(item['label'], x+28, y, 260, 11.5, MUTED, h=17, role='legend')
        x += 28 + theme.width(item['label'], 11.5) + 26


# ---------------------------------------------------------------- 04 scope
def scope(s, d):
    s.box(36, 180, 330, 330, STONE)
    s.text(d['before_title'], 58, 200, 290, 22, MUTED, True, h=30)
    for k, item in enumerate(d['before']):
        y = 262 + k*58
        s.circle(66, y+12, 5, MUTED)
        s.text(item, 82, y, 270, 18, INK, h=26)
    s.text(d['change'], 372, 254, 196, 14.5, ORANGE, True, h=58, align='center')
    s.path([(380, 338), (556, 338)], ORANGE, 4, arrow=True, role='scope-change')
    s.box(572, 180, 592, 330, SKY)
    s.text(d['after_title'], 594, 200, 540, 22, BLUE, True, h=30)
    for k, item in enumerate(d['after']):
        col, row = k % 2, k // 2
        x, y = 592 + col*282, 250 + row*62
        s.box(x, y, 270, 50, WHITE, radius=12)
        s.text(item, x+10, y+13, 250, 17, INK, True, h=24, align='center')
    theme.ribbon(s, d['ribbon'], color=ORANGE, fill=SAND)


# ---------------------------------------------------------------- 05 options
TONES = {'red': (RED, ROSE), 'muted': (MUTED, '#EEF0E9'), 'blue': (BLUE, SKY), 'teal': (TEAL, MINT)}


def options(s, d):
    for j, opt in enumerate(d['options']):
        x, y, w = 36 + j*380, 176, 368
        color, tint = TONES[opt['tone']]
        adopted = opt['tone'] == 'teal'
        s.box(x, y, w, 392, MINT if adopted else WHITE, TEAL if adopted else LINE)
        pw = theme.width(opt['badge'], 14, True) + 38
        s.box(x+18, y+16, pw, 30, tint if not adopted else WHITE, radius=15)
        s.text(opt['badge'], x+34, y+21, pw-30, 14, color, True, h=20)
        s.text(opt['title'], x+18, y+60, w-36, 21, INK, True, h=55)
        for k, step in enumerate(opt['flow']):
            by = y + 134 + k*56
            s.box(x+20, by, w-40, 38, WHITE if adopted else tint, None if not adopted else TEAL, radius=10)
            s.text(step, x+28, by+9, w-56, 15, color, True, h=21, align='center')
            if k < 2:
                s.path([(x+w/2, by+40), (x+w/2, by+54)], color, 2, arrow=True)
        if opt['tone'] == 'red':
            s.path([(x+w/2-13, y+226), (x+w/2+13, y+252)], RED, 3.5, role='rejected')
            s.path([(x+w/2+13, y+226), (x+w/2-13, y+252)], RED, 3.5, role='rejected')
        s.text(opt['body'], x+20, y+310, w-40, 15, INK, h=40)
    theme.ribbon(s, d['ribbon'])


# ---------------------------------------------------------------- 06 poc
def poc(s, d):
    specs = [(BLUE, SKY, 'code'), (ORANGE, STONE, 'shield'), (TEAL, MINT, 'server')]
    for j, (zone, (color, tint, icon)) in enumerate(zip(d['zones'], specs)):
        x = 36 + j*384
        s.box(x, 172, 360, 194, tint)
        theme.icon(s, icon, x+16, 182, 32, color, tint)
        s.text(zone['title'], x+58, 186, 290, 20, color, True, h=28)
        for k, step in enumerate(zone['steps']):
            y = 230 + k*66
            s.box(x+20, y, 320, 44, WHITE, color if (j == 1 and k == 1) else None, radius=10)
            s.text(step, x+30, y+11, 300, 16.5, INK, True, h=23, align='center')
            if k == 0:
                s.path([(x+180, y+46), (x+180, y+64)], color, 2, arrow=True)
        if j < 2:
            s.path([(x+362, 274), (x+382, 274)], INK, 2.5, arrow=True, role='zone-flow')
    s.box(36, 384, 744, 244, WHITE, LINE)
    s.text(d['verified_title'], 58, 398, 300, 19, TEAL, True, h=27)
    for k, item in enumerate(d['verified']):
        y = 438 + k*37
        s.circle(70, y+11, 10, TEAL)
        check_mark(s, 70, y+11, 10)
        s.text(item, 90, y, 670, 16, INK, h=23)
    s.box(796, 384, 368, 244, SAND)
    s.text(d['pending_title'], 818, 398, 330, 19, ORANGE, True, h=27)
    for k, item in enumerate(d['pending']):
        y = 438 + k*44
        s.circle(830, y+11, 9, WHITE, ORANGE)
        s.text(item, 850, y, 290, 16, INK, h=23)


# ---------------------------------------------------------------- 07 progress
def progress(s, d):
    n = len(d['steps'])
    top, gap = 172, 65
    s.path([(60, top+25), (60, top+25+(n-1)*gap)], LINE, 3, role='progress-rail')
    for k, step in enumerate(d['steps']):
        y = top + k*gap
        status_dot(s, step['status'], 60, y+25)
        fill = SAND if step['status'] == 'doing' else WHITE
        s.box(88, y, 468, 50, fill, ORANGE if step['status'] == 'doing' else LINE, radius=12)
        color = MUTED if step['status'] == 'todo' else INK
        s.text(step['title'], 104, y+13, 330, 17, color, True, h=24)
        right_text(s, step['note'], 542, y+15, 14,
                   ORANGE if step['status'] == 'doing' else MUTED, True, h=20)
    for (y, h), label in zip([(172, 262), (448, 180)], d['placeholders']):
        s.box(584, y, 580, h, PLACEHOLDER, MUTED, radius=12, dashed=True)
        s.text(label, 604, y+h/2-12, 540, 16, MUTED, True, h=24, align='center', role='placeholder')


# ---------------------------------------------------------------- 08 wincd
def wincd(s, d):
    entry_colors = [ORANGE, BLUE, BLUE]
    for k, (label, color) in enumerate(zip(d['entries'], entry_colors)):
        y = 182 + k*68
        s.box(36, y, 206, 52, WHITE, color, radius=12)
        s.text(label, 46, y+14, 186, 16.5, color, True, h=23, align='center')
        s.path(theme.rounded([(244, y+26), (266, y+26), (266, 284), (290, 284)], 8),
               color, 2, arrow=True, role='entry')
    s.box(292, 196, 180, 176, MINT, TEAL, radius=14)
    theme.icon(s, 'code', 358, 210, 48, TEAL, MINT)
    s.text(d['engine'], 302, 268, 160, 18, TEAL, True, h=26, align='center')
    s.text(d['engine_body'], 302, 302, 160, 14, INK, h=40, align='center')
    s.path([(474, 284), (496, 284)], TEAL, 2.5, arrow=True, role='engine-host')
    s.box(498, 214, 152, 140, SKY, radius=14)
    theme.icon(s, 'server', 550, 224, 46, BLUE, SKY)
    s.text(d['host'], 506, 276, 136, 16, BLUE, True, h=24, align='center')
    s.text(d['host_body'], 506, 304, 136, 13, INK, h=38, align='center')
    s.box(674, 176, 490, 236, PLACEHOLDER, MUTED, radius=12, dashed=True)
    s.text(d['placeholder'], 694, 282, 450, 16, MUTED, True, h=24, align='center', role='placeholder')
    n = len(d['flow'])
    cw, gap = 146, 17
    for k, step in enumerate(d['flow']):
        x = 36 + k*(cw+gap)
        f5 = 'F5' in step
        s.box(x, 446, cw, 50, SAND if f5 else WHITE, ORANGE if f5 else LINE, radius=12)
        s.text(step, x+6, 460, cw-12, 15, ORANGE if f5 else INK, True, h=22, align='center')
        if k < n-1:
            s.path([(x+cw+2, 471), (x+cw+gap-2, 471)], INK, 2, arrow=True)
    last = 36 + (n-2)*(cw+gap) + cw/2
    s.path(theme.rounded([(last, 498), (last, 524), (36+cw/2, 524), (36+cw/2, 498)], 8),
           RED, 2, dashed=True, arrow=True, role='restore')
    s.text(d['failure'], 236, 536, 728, 16, RED, True, h=24, align='center')


# ---------------------------------------------------------------- 09 features
STATE = {'done': ('完成', TEAL), 'doing': ('進行中', ORANGE), 'todo': ('待辦', MUTED)}


def features(s, d):
    for j, f in enumerate(d['features']):
        col, row = j % 3, j // 3
        x, y = 36 + col*380, 172 + row*148
        color, tint = theme.ACCENTS[j % 3], theme.TINTS[j % 3]
        s.box(x, y, 368, 136, WHITE, LINE)
        theme.icon(s, f['icon'], x+18, y+18, 40, color, tint)
        s.text(f['title'], x+72, y+24, 280, 20, color, True, h=28)
        s.text(f['body'], x+20, y+74, 330, 15, INK, h=40)
    s.box(36, 476, 1128, 152, STONE)
    s.text(d['status_title'], 56, 490, 400, 19, INK, True, h=27)
    for k, item in enumerate(d['status']):
        label, color = STATE[item['state']]
        x = 56 + k*218
        s.box(x, 532, 208, 76, WHITE, color if item['state'] == 'doing' else None, radius=12)
        status_dot(s, item['state'], x+22, 556, 9)
        s.text(label, x+38, 547, 150, 13, color, True, h=19)
        s.text(item['label'], x+14, 576, 184, 14, INK, True, h=20)


# ---------------------------------------------------------------- 10 learning
def learning(s, d):
    for j, col in enumerate(d['columns']):
        x = 36 + j*285
        color = [ORANGE, BLUE, TEAL, BLUE][j]
        tint = [SAND, SKY, MINT, SKY][j]
        s.box(x, 172, 273, 396, tint)
        theme.icon(s, col['icon'], x+20, 190, 48, color, tint)
        s.text(col['title'], x+20, 254, 233, 22, color, True, h=31)
        for k, item in enumerate(col['items']):
            y = 310 + k*60
            s.box(x+16, y, 241, 48, WHITE, radius=10)
            s.text(item, x+26, y+13, 221, 16, INK, True, h=23)
    theme.ribbon(s, d['ribbon'])


# ---------------------------------------------------------------- 11 plan
def plan(s, d):
    """Ordered next steps per track; deliberately no estimated dates."""
    tints = {BLUE: SKY, TEAL: MINT}
    deadline_x, sx1, sx2 = 1108, 262, 1066
    for k, g in enumerate(d['groups']):
        y = 172 + k*144
        dashed = g.get('dashed', False)
        s.box(36, y, 1050, 132, tints.get(g['color'], STONE), g['color'] if dashed else None,
              radius=14, dashed=dashed)
        s.box(36, y, 6, 132, g['color'], radius=3)
        s.text(g['caption'], 58, y+36, 190, 22, g['color'], True, h=30)
        s.text(g['title'], 58, y+74, 190, 14, MUTED, True, h=20)
        n = len(g['steps'])
        gap = 30
        w = (sx2 - sx1 - (n-1)*gap) / n
        for j, step in enumerate(g['steps']):
            x = sx1 + j*(w+gap)
            doing = step['state'] == 'doing'
            if doing:
                s.text('進行中', x+4, y+12, 80, 12, ORANGE, True, h=17)
            s.box(x, y+34, w, 66, SAND if doing else WHITE, ORANGE if doing else LINE,
                  radius=12, dashed=dashed)
            color = MUTED if dashed else INK
            lines = step['label'].count('\n') + 1
            s.text(step['label'], x+8, y+67-lines*15.5*1.27/2, w-16, 15.5, color, True,
                   h=lines*15.5*1.27+.2, align='center')
            if j < n-1:
                s.path([(x+w+4, y+67), (x+w+gap-4, y+67)], g['color'], 2, arrow=True)
    s.path([(deadline_x, 170), (deadline_x, 600)], ORANGE, 3, role='deadline')
    s.text(d['deadline'], deadline_x-50, 604, 100, 15, ORANGE, True, h=22, align='center')


BUILDERS = dict(zip(KINDS, (cover, goals, calendar, scope, options, poc, progress,
                            wincd, features, learning, plan)))


def load_source(path=SOURCE):
    data = json.loads(Path(path).read_text('utf-8'))
    if tuple(s['kind'] for s in data['slides']) != KINDS:
        raise ValueError('Expected the eleven-page mid-term narrative')
    for slide in data['slides']:
        if not slide.get('notes'):
            raise ValueError('Every slide requires speaker notes')
    return data


def make_scenes(data):
    scenes = []
    for index, d in enumerate(data['slides']):
        s = page(d, index, data, cover=d['kind'] == 'cover')
        BUILDERS[d['kind']](s, d)
        scenes.append(s)
    return scenes


def save_pptx(data, scenes, path):
    theme.save_pptx(dict(data, baseline=data['period']), scenes, path)
    from pptx import Presentation
    prs = Presentation(path)
    prs.core_properties.subject = '期中工作報告：換版自動化部署與 WinCD 換版工具'
    prs.core_properties.author = 'Mid-term Report'
    prs.core_properties.keywords = 'Azure DevOps Server, GitLab CE, WinCD, 期中報告'
    for slide, d, scene in zip(prs.slides, data['slides'], scenes):
        for shape, item in zip(slide.shapes, scene.items):
            if item.get('role') == 'placeholder':
                shape.name = f"Screenshot placeholder: {item['value']}"
        notes = f"{d['title']}\n\n{d['notes']}"
        if d.get('source'):
            notes += f"\n\n{d['source']}"
        slide.notes_slide.notes_text_frame.text = notes
    prs.save(path)


def speaker_notes(data):
    parts = [f"# {data['title']}｜講者講稿\n\n{len(data['slides'])} 頁；報告期間 {data['period']}。\n"]
    for n, d in enumerate(data['slides'], 1):
        parts.append(f"## {n}｜{d['title']}\n\n{d['notes']}\n")
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
    with tempfile.TemporaryDirectory(prefix='midterm-report-') as tmp:
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
