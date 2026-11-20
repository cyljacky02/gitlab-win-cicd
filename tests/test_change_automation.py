"""Validate the change-checklist automation talk and its actual PowerPoint exports."""
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import render_change_automation as talk
import render_poc_review as theme


def norm(value):
    return re.sub(r'\s+', '', value)


def luminance(value):
    channels = [int(value.lstrip('#')[i:i+2], 16)/255 for i in (0, 2, 4)]
    return sum((c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4)*w
               for c, w in zip(channels, (.2126, .7152, .0722)))


class ChangeAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = talk.load_source()
        cls.scenes = talk.make_scenes(cls.data)

    def test_six_short_slides_with_notes(self):
        self.assertEqual([s['kind'] for s in self.data['slides']], list(talk.KINDS))
        self.assertLessEqual(sum(s['minutes'] for s in self.data['slides']), 10)
        for d in self.data['slides']:
            self.assertGreater(len(d['notes']), 150)

    def test_story_covers_flow_pilot_and_invitation(self):
        text = '\n'.join(i['value'] for s in self.scenes for i in s.items if i['kind'] == 'text')
        for phrase in ('公槽', 'Excel Online', 'Power Automate', 'Office Scripts', 'Teams',
                       '完成', '失敗', '取消', '新工作表', '不影響現有工作表', '自動填 Y',
                       '試行', '主表新增變更', '來找我討論'):
            self.assertIn(phrase, text)
        # Only "完成" back-fills the main sheet; failure/cancel are recorded, not marked Y.
        outcomes = self.data['slides'][3]['outcomes']
        self.assertIn('Y', outcomes[0]['body'])
        self.assertFalse(any('Y' in o['body'] for o in outcomes[1:]))
        # Steps 1 and 4 are human actions; the result arrow returns to step 1.
        self.assertEqual([s['auto'] for s in self.data['slides'][2]['steps']],
                         [False, True, True, False])
        arrow = next(i for i in self.scenes[2].items if i.get('role') == 'result-return-arrow')
        self.assertTrue(arrow['arrow'])
        self.assertLess(arrow['points'][-1][0], 300)

    def test_geometry_and_body_type_size(self):
        for n, scene in enumerate(self.scenes, 1):
            for i in scene.items:
                if i['kind'] == 'path':
                    self.assertTrue(all(0 <= x <= theme.W and 0 <= y <= theme.H for x, y in i['points']))
                    continue
                self.assertTrue(0 <= i['x'] <= i['x']+i['w'] <= theme.W+.1, (n, i))
                self.assertTrue(0 <= i['y'] <= i['y']+i['h'] <= theme.H+.1, (n, i))
                if i['kind'] == 'text':
                    self.assertLessEqual(i['measured'], i['h']+.1, (n, i['value']))
                    for line in i['lines']:
                        self.assertLessEqual(theme.width(line, i['size'], i['bold']), i['w'])
                    if 180 < i['y'] < 578 and i['role'] != 'source':
                        self.assertGreaterEqual(i['size'], 14)

    def test_cover_art_stays_in_its_slot_and_is_grouped(self):
        art = [i for i in self.scenes[0].items if i.get('art') == 'cover-card']
        self.assertGreater(len(art), 20)
        self.assertFalse(any(i['kind'] == 'text' for i in art))
        for i in art:
            points = i['points'] if i['kind'] == 'path' else [
                (i['x'], i['y']), (i['x']+i['w'], i['y']+i['h'])]
            self.assertTrue(all(850 <= x <= 1164 and 75 <= y <= 420 for x, y in points), i)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'cover.pptx'
            talk.save_pptx(self.data, self.scenes, path)
            groups = [s for s in Presentation(path).slides[0].shapes
                      if s.shape_type == MSO_SHAPE_TYPE.GROUP]
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups[0].shapes), len(art))

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
                    if under['kind'] == 'box' and under['x'] <= x <= under['x']+under['w'] \
                            and under['y'] <= y <= under['y']+under['h']:
                        bg = under['fill']
                lo, hi = sorted([luminance(item['color']), luminance(bg)])
                minimum = 3 if item['size'] >= 24 or (item['bold'] and item['size'] >= 18.67) else 4.5
                self.assertGreaterEqual((hi+.05)/(lo+.05), minimum, (n, item['value']))

    def test_native_editable_pptx_with_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'talk.pptx'
            talk.save_pptx(self.data, self.scenes, path)
            prs = Presentation(path)
            self.assertEqual(len(prs.slides), 6)
            self.assertEqual(prs.core_properties.title, self.data['title'])
            for slide, data, scene in zip(prs.slides, self.data['slides'], self.scenes):
                self.assertFalse(any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in slide.shapes))
                self.assertIn(data['notes'], slide.notes_slide.notes_text_frame.text)
                text = norm(''.join(s.text for s in slide.shapes if s.has_text_frame))
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), text)

    def test_historical_paths_and_incompatible_modes_refused(self):
        for name in talk.PROTECTED:
            with self.assertRaisesRegex(ValueError, 'historical'):
                talk.build(output_dir=ROOT/'docs/presentations'/name/'nested', pptx_only=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'actual PowerPoint'):
                talk.build(output_dir=tmp, pptx_only=True, with_previews=True)
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_failed_export_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output/f'{talk.STEM}.pdf').write_bytes(b'old export')
            with patch.object(talk.subprocess, 'run', side_effect=RuntimeError('export failed')):
                with self.assertRaisesRegex(RuntimeError, 'export failed'):
                    talk.build(output_dir=output)
            self.assertEqual((output/f'{talk.STEM}.pdf').read_bytes(), b'old export')
            self.assertFalse((output/f'{talk.STEM}.pptx').exists())

    def test_published_pdf_matches_source(self):
        path = talk.SOURCE.parent/f'{talk.STEM}.pdf'
        if not path.exists():
            self.skipTest('Desktop PowerPoint export not present')
        import pymupdf
        with pymupdf.open(path) as pdf:
            self.assertEqual(len(pdf), 6)
            for page, scene in zip(pdf, self.scenes):
                visible = norm(page.get_text())
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), visible)
        self.assertEqual({p.name for p in path.parent.glob('preview-*.png')},
                         {f'preview-{n:02d}.png' for n in range(1, 7)})
        self.assertEqual((path.parent/'speaker-notes.md').read_text('utf-8'),
                         talk.speaker_notes(self.data))


if __name__ == '__main__':
    unittest.main()
