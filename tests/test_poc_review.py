"""Checks the new review edition without touching historical/manual PPTX files."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import render_poc_review as deck
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def norm(value):
    return re.sub(r'\s+', '', value)


def luminance(value):
    channels = [int(value.lstrip('#')[i:i+2], 16)/255 for i in (0, 2, 4)]
    channels = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
    return sum(c*w for c, w in zip(channels, (.2126, .7152, .0722)))


def contrast(a, b):
    lo, hi = sorted([luminance(a), luminance(b)])
    return (hi+.05)/(lo+.05)


class ReviewDeckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = deck.load_source()
        cls.scenes = deck.make_scenes(cls.data)

    def test_review_story_and_separate_baseline(self):
        self.assertEqual(len(self.data['slides']), 9)
        self.assertEqual([s['kind'] for s in self.data['slides']], list(deck.BUILDERS))
        self.assertEqual(self.data['baseline'], '2026-10-22')
        self.assertEqual(self.data['archive_sha256'], 'b273ba0f8d37430c6a9953cdccee51a6638763cc407278bc7d39e268c597bbf1')
        self.assertNotEqual(deck.STEM, 'windows-cd-journey')

    def test_all_text_boxes_paths_and_shapes_within_slide(self):
        for n, scene in enumerate(self.scenes):
            for i in scene.items:
                with self.subTest(page=n+1, kind=i['kind']):
                    if i['kind'] == 'path':
                        for x, y in i['points']:
                            self.assertTrue(0 <= x <= deck.W and 0 <= y <= deck.H)
                    else:
                        self.assertGreaterEqual(i['x'], 0)
                        self.assertGreaterEqual(i['y'], 0)
                        self.assertLessEqual(i['x']+i['w'], deck.W+.1)
                        self.assertLessEqual(i['y']+i['h'], deck.H+.1)
                        if i['kind'] == 'text':
                            self.assertLessEqual(i['measured'], i['h']+.1)
                            for line in i['lines']:
                                self.assertLessEqual(deck.width(line, i['size'], i['bold']), i['w'])

    def test_text_lines_do_not_overlap(self):
        for n, scene in enumerate(self.scenes):
            lines = []
            for i in scene.items:
                if i['kind'] != 'text':
                    continue
                for k, value in enumerate(i['lines']):
                    if not value.strip():
                        continue
                    w = deck.width(value, i['size'], i['bold'])
                    x = i['x'] + ((i['w']-w)/2 if i['align'] == 'center' else 0)
                    y = i['y']+k*i['size']*1.27
                    lines.append((value, x, y, x+w, y+i['size']*1.2))
            for index, a in enumerate(lines):
                for b in lines[index+1:]:
                    iw, ih = min(a[3], b[3])-max(a[1], b[1]), min(a[4], b[4])-max(a[2], b[2])
                    self.assertFalse(iw > 1 and ih > 1, f'page {n+1}: {a[0]} overlaps {b[0]}')

    def test_accessible_palette_and_text_on_actual_background(self):
        for n, scene in enumerate(self.scenes):
            for index, i in enumerate(scene.items):
                if i['kind'] != 'text':
                    continue
                # Find topmost containing fill underneath the text's centre.
                cx, cy = i['x']+i['w']/2, i['y']+min(i['measured'], i['h'])/2
                bg = deck.PAPER
                for under in scene.items[:index]:
                    if under['kind'] == 'box' and under['x'] <= cx <= under['x']+under['w'] and under['y'] <= cy <= under['y']+under['h']:
                        bg = under['fill']
                minimum = 3 if i['size'] >= 24 or (i['bold'] and i['size'] >= 18.67) else 4.5
                self.assertGreaterEqual(contrast(i['color'], bg), minimum, f'page {n+1}: {i["value"]}')

    def test_architecture_caller_and_response_directions(self):
        scene = self.scenes[1]
        links = {i['role']: i for i in scene.items if i['kind'] == 'path'}
        # Network request arrow starts at Windows, ends at ADO boundary, not an inbound target command.
        outbound = links['agent-outbound']
        self.assertGreater(outbound['points'][0][0], outbound['points'][-1][0])
        self.assertTrue(outbound['dashed'])
        response = links['authorized-job-response']
        self.assertGreater(response['points'][-1][0], response['points'][0][0])
        self.assertFalse(response['dashed'])
        self.assertIn('Windows Agent → ADO', self.data['slides'][1]['network'])
        self.assertIn('POC 經公網', (deck.SOURCE.parent/'review-notes.md').read_text('utf-8'))
        self.assertIn('不含 F5', self.data['slides'][1]['subtitle'])

    def test_credential_and_license_boundaries_not_flattened(self):
        d = self.data['slides']
        self.assertIn('System.AccessToken', d[3]['rollback'])
        self.assertIn('不是第三把長效 PAT', d[3]['rollback'])
        self.assertIn('2 組 Agent', d[3]['other_body'])
        self.assertIn('例外', ' '.join(d[4]['gates']))
        self.assertIn('書面確認', ' '.join(d[4]['gates']))
        self.assertIn('不是任意多人', d[4]['subtitle'])
        self.assertIn('Internal visibility', d[3]['notes'])

    def test_evidence_and_next_stage_are_not_claimed_as_remote_tests(self):
        d = self.data['slides']
        self.assertIn('#20 核准後成功退版', d[2]['notes'])
        self.assertIn('#21 是退版後再次往前部署成功', d[2]['notes'])
        self.assertIn('rollback 本身', d[2]['notes'])
        self.assertEqual(d[5]['lanes'][2]['badge'], '僅本機')
        self.assertIn('未接入現行 Pipeline', d[5]['lanes'][2]['detail'])
        self.assertIn('本次未重跑', d[0]['source'])
        self.assertIn('未量測', d[2]['limits'][2]['body'])

    def test_native_shapes_and_complete_speaker_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'native-check.pptx'
            deck.save_pptx(self.data, self.scenes, path)
            prs = Presentation(path)
            self.assertEqual(len(prs.slides), len(self.scenes))
            for slide, source, scene in zip(prs.slides, self.data['slides'], self.scenes):
                self.assertEqual(slide.name, source['title'])
                self.assertTrue(any(shape.name.startswith('title:') for shape in slide.shapes))
                self.assertFalse(any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes))
                self.assertIn(source['notes'], slide.notes_slide.notes_text_frame.text)
                text = norm(''.join(shape.text for shape in slide.shapes if shape.has_text_frame))
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), text)
            with zipfile.ZipFile(path) as z:
                self.assertFalse(any(p.startswith('ppt/media/') for p in z.namelist()))

    def test_historical_output_and_incompatible_modes_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'historical Journey'):
            deck.build(output_dir=ROOT/'docs/presentations/journey/inputs', pptx_only=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'actual PowerPoint'):
                deck.build(output_dir=tmp, pptx_only=True, with_previews=True)
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_new_delivery_has_no_field_hosts_private_ips_or_token_values(self):
        text = json.dumps(self.data, ensure_ascii=False)+(deck.SOURCE.parent/'review-notes.md').read_text('utf-8')
        self.assertNotRegex(text, r'020908\.xyz|WIN-[A-Z0-9]{6,}')
        self.assertNotRegex(text, r'\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b')
        self.assertNotRegex(text, r'(?:glpat-|glrt-)[A-Za-z0-9_-]{12,}')
        self.assertNotIn('IMG_444', text)

    def test_published_pdf_and_previews_if_present(self):
        output = deck.SOURCE.parent
        path = output/f'{deck.STEM}.pdf'
        if not path.exists():
            self.skipTest('PDF export requires desktop PowerPoint; not present')
        import pymupdf
        with pymupdf.open(path) as pdf:
            self.assertEqual(len(pdf), len(self.scenes))
            for n, (page, scene) in enumerate(zip(pdf, self.scenes)):
                text = norm(page.get_text())
                for i in scene.items:
                    if i['kind'] == 'text':
                        self.assertIn(norm(i['value']), text)
                self.assertGreater(len(text), 150)
                self.assertTrue((output/f'preview-{n+1:02d}.png').exists())
                for word in page.get_text('words'):
                    self.assertGreaterEqual(word[0], 0)
                    self.assertGreaterEqual(word[1], 0)
                    self.assertLessEqual(word[2], deck.W+.1)
                    self.assertLessEqual(word[3], deck.H+.1)
        self.assertTrue((output/'overview.png').exists())


if __name__ == '__main__':
    unittest.main()
