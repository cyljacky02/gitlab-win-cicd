"""Validate the mid-term report deck: layout geometry, calendar data and native PPTX output."""
from datetime import date
from pathlib import Path
import re
import sys
import tempfile
import unittest

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import render_midterm_report as deck
import render_poc_review as theme


def norm(value):
    return re.sub(r'\s+', '', value)


def luminance(value):
    channels = [int(value.lstrip('#')[i:i+2], 16)/255 for i in (0, 2, 4)]
    return sum((c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4)*w
               for c, w in zip(channels, (.2126, .7152, .0722)))


class MidtermReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = deck.load_source()
        cls.scenes = deck.make_scenes(cls.data)

    def test_eleven_pages_in_agreed_order_with_notes(self):
        self.assertEqual(tuple(s['kind'] for s in self.data['slides']), deck.KINDS)
        self.assertEqual(len(self.scenes), 11)
        for d in self.data['slides']:
            self.assertGreater(len(d['notes']), 80, d['title'])

    def test_calendar_matches_agreed_timeline(self):
        cal = self.data['slides'][2]
        self.assertEqual(date.fromisoformat(cal['start']), date(2026, 9, 28))
        self.assertEqual(cal['weeks'], 8)
        flags = {f['date']: f['label'] for f in cal['flags']}
        self.assertEqual(flags['2026-09-29'], '入職')
        self.assertIn('2026-11-06', flags)
        self.assertNotIn('今天', ''.join(flags.values()))
        self.assertEqual(cal['maintenance']['start'], '2026-10-06')
        self.assertEqual(len(cal['events']), 6)
        texts = '\n'.join(i['value'] for i in self.scenes[2].items if i['kind'] == 'text')
        for word in ('OPWEB', '雷影', '精誠', 'ADO Server Express', '預計'):
            self.assertIn(word, texts)
        self.assertNotIn('MCP', texts)
        connectors = [i for i in self.scenes[2].items if i.get('role', '').startswith('connector-')]
        self.assertEqual(len(connectors), 6)
        self.assertTrue(all(i['arrow'] for i in connectors))
        dashed = [i for i in self.scenes[2].items if i['kind'] == 'box' and i['dashed']]
        self.assertGreaterEqual(len(dashed), 3)

    def test_goal_weights_and_no_mcp_sharing(self):
        goals = self.data['slides'][1]['goals']
        self.assertEqual([g['weight'] for g in goals], ['50%', '25%'])
        everything = norm(str(self.data))
        self.assertNotIn('MCP', everything)
        self.assertNotIn('心路歷程', everything)

    def test_geometry_text_fit_and_minimum_sizes(self):
        for n, scene in enumerate(self.scenes, 1):
            for i in scene.items:
                if i['kind'] == 'path':
                    self.assertTrue(all(0 <= x <= theme.W and 0 <= y <= theme.H for x, y in i['points']))
                    continue
                self.assertTrue(0 <= i['x'] <= i['x']+i['w'] <= theme.W+.1, (n, i))
                self.assertTrue(0 <= i['y'] <= i['y']+i['h'] <= theme.H+.1, (n, i))
                if i['kind'] == 'text':
                    self.assertLessEqual(i['measured'], i['h']+.3, (n, i['value']))
                    for line in i['lines']:
                        self.assertLessEqual(theme.width(line, i['size'], i['bold']), i['w'])
                    minimum = 9 if n == 3 else 11.5 if i['role'] == 'source' else 12
                    self.assertGreaterEqual(i['size'], minimum, (n, i['value']))

    def test_visible_text_lines_do_not_overlap(self):
        for n, scene in enumerate(self.scenes, 1):
            lines = []
            for i in scene.items:
                if i['kind'] != 'text':
                    continue
                for k, value in enumerate(i['lines']):
                    if not value.strip():
                        continue
                    w = theme.width(value, i['size'], i['bold'])
                    x = i['x']+((i['w']-w)/2 if i['align'] == 'center' else 0)
                    y = i['y']+k*i['size']*1.27
                    lines.append((value, x, y, x+w, y+i['size']*1.2))
            for index, a in enumerate(lines):
                for b in lines[index+1:]:
                    dx, dy = min(a[3], b[3])-max(a[1], b[1]), min(a[4], b[4])-max(a[2], b[2])
                    self.assertFalse(dx > 1 and dy > 1, f'page {n}: {a[0]} overlaps {b[0]}')

    def test_contrast_on_actual_surface(self):
        for n, scene in enumerate(self.scenes, 1):
            for index, item in enumerate(scene.items):
                if item['kind'] != 'text':
                    continue
                x, y = item['x']+item['w']/2, item['y']+item['measured']/2
                bg = theme.PAPER
                for under in scene.items[:index]:
                    if (under['kind'] == 'box' and under['x'] <= x <= under['x']+under['w']
                            and under['y'] <= y <= under['y']+under['h']):
                        bg = under['fill']
                lo, hi = sorted([luminance(item['color']), luminance(bg)])
                minimum = 3 if item['size'] >= 24 or (item['bold'] and item['size'] >= 18.67) else 4.5
                self.assertGreaterEqual((hi+.05)/(lo+.05), minimum, (n, item['value']))

    def test_native_editable_pptx_with_notes_and_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'deck.pptx'
            deck.save_pptx(self.data, self.scenes, path)
            prs = Presentation(path)
            self.assertEqual(len(prs.slides), 11)
            names = []
            for slide, d, scene in zip(prs.slides, self.data['slides'], self.scenes):
                self.assertFalse(any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in slide.shapes))
                self.assertEqual(slide.name, d['title'])
                self.assertIn(d['notes'], slide.notes_slide.notes_text_frame.text)
                names += [s.name for s in slide.shapes]
                text = norm(''.join(s.text for s in slide.shapes if s.has_text_frame))
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), text)
            self.assertEqual(sum(n.startswith('Screenshot placeholder') for n in names), 3)

    def test_historical_paths_refused(self):
        for name in deck.PROTECTED:
            with self.assertRaisesRegex(ValueError, 'historical'):
                deck.build(output_dir=ROOT/'docs/presentations'/name/'nested', pptx_only=True)

    def test_published_pdf_matches_source(self):
        path = deck.SOURCE.parent/f'{deck.STEM}.pdf'
        if not path.exists():
            self.skipTest('Desktop PowerPoint export not present')
        import pymupdf
        with pymupdf.open(path) as pdf:
            self.assertEqual(len(pdf), 11)
            for n, (page, scene) in enumerate(zip(pdf, self.scenes), 1):
                visible = norm(page.get_text())
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), visible)
                self.assertTrue((path.parent/f'preview-{n:02d}.png').exists())


if __name__ == '__main__':
    unittest.main()
