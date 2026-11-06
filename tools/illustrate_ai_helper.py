"""Original editable cover art: a friendly helper bringing Web AI into local work.

Reference lock: existing deck's warm canvas, blue browser, teal assistant and
orange permission badge. No external image-generation service or product screenshot.
All coordinates are local to a 360 x 320 artboard, deliberately without tiny labels.
"""
from __future__ import annotations

import math

import render_poc_review as theme

ALT = '友善 AI 小助手從瀏覽器探出身，連接程式工具並提著工具箱，旁有橙色人工核准勾勾。'


def draw(s, x=804, y=93):
    start = len(s.items)
    blue, teal, orange = theme.BLUE, theme.TEAL, theme.ORANGE
    ink, white = theme.INK, theme.WHITE
    pale_blue, mint, sand = theme.SKY, theme.MINT, theme.SAND

    def box(a, b, w, h, fill=white, stroke=None, radius=12):
        s.box(x+a, y+b, w, h, fill, stroke, radius)

    def dot(a, b, r, fill, stroke=None):
        s.circle(x+a, y+b, r, fill, stroke)

    def line(points, color=ink, weight=2.2, role='illustration-detail'):
        s.path([(x+a, y+b) for a, b in points], color, weight, role=role)

    def curve(points, color=ink, weight=2.2, role='illustration-detail'):
        line(theme.rounded(points, 15), color, weight, role)

    def arc(cx, cy, rx, ry, begin, end, color=ink, weight=2.2):
        line([(cx+rx*math.cos(math.radians(a)), cy+ry*math.sin(math.radians(a)))
              for a in [begin+(end-begin)*k/24 for k in range(25)]], color, weight)

    # Light cut-paper backdrop, not a new slide background or a decorative gradient.
    dot(192, 161, 126, '#EEF4F2')
    dot(95, 205, 65, pale_blue)
    dot(298, 104, 24, sand)
    s.box(x+81, y+290, 231, 13, '#E1E9E6', form='ellipse')

    # Browser window: the assistant lives at the bridge between chat and tools.
    box(67, 73, 244, 210, '#D5E4EC', radius=20)
    box(61, 65, 244, 210, white, blue, 19)
    box(64, 68, 238, 29, pale_blue, radius=14)
    line([(63, 99), (303, 99)], blue, 1.4)
    for a, fill in [(78, blue), (90, teal), (102, orange)]:
        dot(a, 83, 2.7, fill)
    box(122, 78, 122, 10, white, radius=5)
    line([(277, 79), (284, 79)], blue, 1.5)
    line([(277, 86), (284, 86)], blue, 1.5)

    # Chat bubble with a friendly tail; readable as conversation without any label.
    box(10, 17, 93, 58, '#DDE9EE', radius=17)
    box(6, 12, 93, 58, white, blue, 17)
    curve([(77, 69), (77, 82), (61, 70)], blue, 2)
    for a in (30, 51, 72):
        dot(a, 40, 4, teal if a == 51 else blue)
    curve([(98, 44), (129, 44), (129, 64)], blue, 2)

    # Antenna and rounded ears give the character an alert, curious posture.
    curve([(192, 121), (192, 104), (204, 93)], teal, 3)
    dot(206, 91, 6, sand, orange)
    box(105, 144, 15, 29, mint, teal, 7)
    box(252, 144, 15, 29, mint, teal, 7)

    # A little torso and spring feet perch on the browser sill.
    box(172, 199, 29, 18, mint, teal, 6)
    box(140, 213, 94, 52, white, teal, 18)
    box(174, 222, 26, 22, mint, radius=8)
    line([(180, 232), (185, 237), (194, 227)], teal, 2.6)
    curve([(158, 262), (151, 282), (135, 282)], teal, 7)
    curve([(216, 262), (225, 282), (242, 282)], teal, 7)
    box(126, 279, 32, 12, pale_blue, blue, 6)
    box(222, 279, 32, 12, pale_blue, blue, 6)

    # Arms: one reaches to the code tile; the other carries a practical toolkit.
    curve([(143, 231), (116, 231), (102, 215), (84, 215)], teal, 12)
    curve([(143, 229), (116, 229), (102, 213), (84, 213)], mint, 7)
    curve([(232, 231), (251, 231), (266, 214), (282, 214)], teal, 12)
    curve([(232, 229), (251, 229), (266, 212), (282, 212)], mint, 7)

    # Head: broad white shell, deep faceplate, curious eyes and a little smile.
    box(115, 125, 143, 85, '#D8E7E5', radius=27)
    box(112, 119, 143, 85, white, teal, 27)
    box(124, 132, 119, 59, ink, radius=20)
    box(145, 147, 12, 18, '#56D8C3', radius=6)
    box(207, 144, 12, 18, '#56D8C3', radius=6)
    dot(149, 151, 2, white)
    dot(211, 148, 2, white)
    arc(183, 165, 14, 10, 17, 163, '#88E2D1', 2.7)
    line([(130, 175), (135, 175)], '#438B96', 2)
    line([(229, 172), (234, 172)], '#438B96', 2)

    # A detached local code tile, visually connected by the helper's left arm.
    box(8, 183, 83, 65, '#DBE7EE', radius=13)
    box(3, 178, 83, 65, white, blue, 13)
    box(6, 181, 77, 15, pale_blue, radius=7)
    for a in (15, 22, 29):
        dot(a, 188, 1.5, blue)
    line([(29, 207), (20, 215), (29, 223)], blue, 2.8)
    line([(60, 207), (69, 215), (60, 223)], blue, 2.8)
    line([(49, 204), (41, 226)], teal, 2.8)

    # Toolkit: blue/teal tools, not an orange permission-colored execution box.
    curve([(279, 220), (279, 207), (301, 207), (301, 220)], blue, 3.5)
    box(259, 220, 66, 53, pale_blue, blue, 10)
    box(259, 220, 66, 18, blue, radius=8)
    line([(260, 239), (324, 239)], blue, 1.3)
    box(287, 233, 10, 12, white, blue, 3)
    line([(275, 255), (283, 255)], teal, 2)
    line([(301, 255), (309, 255)], teal, 2)

    # Orange means permission, not a blanket success/security certification.
    dot(293, 44, 29, '#E9DFCC')
    dot(289, 39, 29, sand, orange)
    line([(275, 39), (285, 49), (303, 29)], orange, 4)
    # Tiny motion marks add personality while staying inside the artboard.
    line([(333, 129), (333, 141)], teal, 2)
    line([(327, 135), (339, 135)], teal, 2)
    line([(33, 129), (33, 139)], blue, 2)
    line([(28, 134), (38, 134)], blue, 2)
    dot(316, 176, 3, orange)
    dot(72, 294, 3, teal)

    for item in s.items[start:]:
        item['art'] = 'cover-helper'
