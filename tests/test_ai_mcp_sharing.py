"""Validate the separate AI x MCP talk and its actual PowerPoint exports."""
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
import render_ai_mcp_sharing as talk
import render_poc_review as theme


def norm(value):
    return re.sub(r'\s+', '', value)


def luminance(value):
    channels = [int(value.lstrip('#')[i:i+2], 16)/255 for i in (0, 2, 4)]
    return sum((c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4)*w
               for c, w in zip(channels, (.2126, .7152, .0722)))


class SharingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = talk.load_source()
        cls.scenes = talk.make_scenes(cls.data)

    def test_six_slides_and_fifteen_minutes_with_demo(self):
        self.assertEqual(len(self.scenes), 6)
        self.assertEqual(sum(s['minutes'] for s in self.data['slides']), 15)
        self.assertEqual(self.data['slides'][4]['minutes'], 8)
        self.assertEqual([s['kind'] for s in self.data['slides']],
                         ['opening', 'architecture', 'capabilities', 'controls', 'demos', 'closing'])
        self.assertEqual(self.data['source_commit'], '280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6')
        for d in self.data['slides']:
            self.assertGreater(len(d['notes']), 200)
            self.assertTrue(d['references'])

    def test_cover_art_is_grouped_editable_and_within_its_slot(self):
        import illustrate_ai_helper
        scene = self.scenes[0]
        art = [i for i in scene.items if i.get('art') == 'cover-helper']
        self.assertGreater(len(art), 30)
        self.assertFalse(any(i['kind'] in ('text', 'image') for i in art))
        for i in art:
            points = i['points'] if i['kind'] == 'path' else [
                (i['x'], i['y']), (i['x']+i['w'], i['y']+i['h'])]
            self.assertTrue(all(804 <= x <= 1164 and 93 <= y <= 413 for x, y in points))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'illustration.pptx'
            talk.save_pptx(self.data, self.scenes, path)
            prs = Presentation(path)
            groups = [s for s in prs.slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.GROUP]
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].name, 'Cover illustration: AI helper')
            self.assertEqual(len(groups[0].shapes), len(art))
            self.assertIn(illustrate_ai_helper.ALT, groups[0]._element.xml)
            self.assertFalse(any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in groups[0].shapes))
            self.assertFalse(any(s.shape_type == MSO_SHAPE_TYPE.GROUP
                                 for page in list(prs.slides)[1:] for s in page.shapes))

    def test_geometry_and_body_type_size(self):
        for n, scene in enumerate(self.scenes, 1):
            for i in scene.items:
                if i['kind'] == 'path':
                    self.assertTrue(all(0 <= x <= theme.W and 0 <= y <= theme.H for x, y in i['points']))
                    continue
                self.assertTrue(0 <= i['x'] <= i['x']+i['w'] <= theme.W+.1)
                self.assertTrue(0 <= i['y'] <= i['y']+i['h'] <= theme.H+.1)
                if i['kind'] == 'text':
                    self.assertLessEqual(i['measured'], i['h']+.1, (n, i['value']))
                    for line in i['lines']:
                        self.assertLessEqual(theme.width(line, i['size'], i['bold']), i['w'])
                    if 180 < i['y'] < 578 and i['role'] != 'source':
                        self.assertGreaterEqual(i['size'], 14)

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
                    if under['kind'] == 'box' and under['x'] <= x <= under['x']+under['w'] and under['y'] <= y <= under['y']+under['h']:
                        bg = under['fill']
                lo, hi = sorted([luminance(item['color']), luminance(bg)])
                minimum = 3 if item['size'] >= 24 or (item['bold'] and item['size'] >= 18.67) else 4.5
                self.assertGreaterEqual((hi+.05)/(lo+.05), minimum, (n, item['value']))

    def test_native_editable_pptx_notes_and_correct_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'talk.pptx'
            talk.save_pptx(self.data, self.scenes, path)
            prs = Presentation(path)
            self.assertEqual(len(prs.slides), 6)
            self.assertEqual(prs.core_properties.title, self.data['title'])
            self.assertNotIn('Deployment', prs.core_properties.author)
            for slide, data, scene in zip(prs.slides, self.data['slides'], self.scenes):
                self.assertFalse(any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in slide.shapes))
                self.assertEqual(slide.name, data['title'])
                self.assertIn(data['notes'], slide.notes_slide.notes_text_frame.text)
                self.assertIn(self.data['source_commit'], slide.notes_slide.notes_text_frame.text)
                for reference in data['references']:
                    self.assertIn(reference, slide.notes_slide.notes_text_frame.text)
                text = norm(''.join(s.text for s in slide.shapes if s.has_text_frame))
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), text)

    def test_scope_and_evidence_caveats_are_not_omitted(self):
        text = talk.speaker_notes(self.data)
        for caveat in ('不是 ChatGPT Web 原生', '資料外送', '不是正式資安驗收',
                       '沒有節費', '尚未執行', '不是已量測'):
            self.assertIn(caveat, text)
        links = {i['role']: i for i in self.scenes[1].items if i['kind'] == 'path'}
        result = links['real-result-return']['points']
        self.assertGreater(result[0][0], result[-1][0])
        self.assertTrue(links['real-result-return']['arrow'])

    def test_historical_paths_and_incompatible_modes_refused(self):
        for name in ('journey', 'poc-implementation-review', 'poc-direct-agent-concept'):
            with self.assertRaisesRegex(ValueError, 'historical'):
                talk.build(output_dir=ROOT/'docs/presentations'/name/'nested', pptx_only=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'actual PowerPoint'):
                talk.build(output_dir=tmp, pptx_only=True, with_previews=True)
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_failed_export_does_not_publish_or_replace_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            path = output/f'{talk.STEM}.pdf'
            path.write_bytes(b'old export')
            with patch.object(talk.subprocess, 'run', side_effect=RuntimeError('export failed')):
                with self.assertRaisesRegex(RuntimeError, 'export failed'):
                    talk.build(output_dir=output)
            self.assertEqual(path.read_bytes(), b'old export')
            self.assertFalse((output/f'{talk.STEM}.pptx').exists())

    def test_published_pdf_and_previews_match_all_source_text(self):
        path = talk.SOURCE.parent/f'{talk.STEM}.pdf'
        if not path.exists():
            self.skipTest('Desktop PowerPoint export not present')
        import pymupdf
        with pymupdf.open(path) as pdf:
            self.assertEqual(len(pdf), 6)
            for n, (page, scene) in enumerate(zip(pdf, self.scenes), 1):
                visible = norm(page.get_text())
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), visible)
                for word in page.get_text('words'):
                    self.assertTrue(0 <= word[0] <= word[2] <= theme.W+.1)
                    self.assertTrue(0 <= word[1] <= word[3] <= theme.H+.1)
                self.assertTrue((path.parent/f'preview-{n:02d}.png').exists())
        self.assertTrue((path.parent/'overview.png').exists())
        self.assertEqual({p.name for p in path.parent.glob('preview-*.png')},
                         {f'preview-{n:02d}.png' for n in range(1, 7)})
        self.assertEqual((path.parent/'speaker-notes.md').read_text('utf-8'), talk.speaker_notes(self.data))

    def test_merged_pages_emphasize_bridge_and_keep_capabilities_brief(self):
        architecture = '\n'.join(i['value'] for i in self.scenes[1].items if i['kind'] == 'text')
        for label in ('ChatGPT Web 的腦', 'Playwright', 'Relay', 'Chrome', '實際結果'):
            self.assertIn(label, architecture)
        capabilities = '\n'.join(i['value'] for i in self.scenes[2].items if i['kind'] == 'text')
        for label in ('Web 自動化測試', 'Outlook', '固定工具', 'VS Code', '確認後套用'):
            self.assertIn(label, capabilities)
        self.assertNotIn('Diff', capabilities)
        self.assertLess(len(capabilities), 330)
        self.assertIn('【Demo B，約 5 分鐘】', self.data['slides'][4]['notes'])


if __name__ == '__main__':
    unittest.main()
