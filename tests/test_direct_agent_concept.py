"""Validate the standalone direct-agent architecture without editing the broker deck."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import render_direct_agent_concept as concept
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


class DirectAgentConceptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = concept.deck.load_source(concept.SOURCE)
        cls.scene = concept.make_scene(cls.data)

    def test_parallel_concept_and_governance_are_explicit(self):
        slide = self.data['slides'][0]
        self.assertEqual(self.data['status'], 'concept-not-implemented')
        self.assertIn('原 broker 架構與腳本完整保留', slide['subtitle'])
        self.assertIn('尚未實作', slide['subtitle'])
        self.assertIn('PR 審核', slide['repo_label'])
        self.assertIn('人工部署放行', slide['nodes'][5]['title'])
        self.assertIn('主機權限', slide['boundaries'][2])
        self.assertFalse(any('broker' in node['title'] for node in slide['nodes']))
        self.assertIn('退版', slide['nodes'][7]['title'])
        self.assertIn('再驗', slide['target_label'])
        self.assertIn('Windows Agent → ADO', slide['network'])
        self.assertIn('未審分支', slide['notes'])

    def test_geometry_and_nonoverlapping_text(self):
        deck = concept.deck
        lines = []
        for item in self.scene.items:
            if item['kind'] == 'path':
                for x, y in item['points']:
                    self.assertTrue(0 <= x <= deck.W and 0 <= y <= deck.H)
            else:
                self.assertTrue(0 <= item['x'] <= item['x'] + item['w'] <= deck.W + .1)
                self.assertTrue(0 <= item['y'] <= item['y'] + item['h'] <= deck.H + .1)
            if item['kind'] != 'text':
                continue
            self.assertLessEqual(item['measured'], item['h'] + .1)
            for n, value in enumerate(item['lines']):
                width = deck.width(value, item['size'], item['bold'])
                self.assertLessEqual(width, item['w'])
                x = item['x'] + ((item['w'] - width) / 2 if item['align'] == 'center' else 0)
                y = item['y'] + n * item['size'] * 1.27
                if value.strip():
                    lines.append((value, x, y, x + width, y + item['size'] * 1.2))
        for n, a in enumerate(lines):
            for b in lines[n + 1:]:
                overlap_x = min(a[3], b[3]) - max(a[1], b[1])
                overlap_y = min(a[4], b[4]) - max(a[2], b[2])
                self.assertFalse(overlap_x > 1 and overlap_y > 1, f'{a[0]} overlaps {b[0]}')

    def test_request_response_directions_and_direct_execution(self):
        links = {item['role']: item for item in self.scene.items if item['kind'] == 'path'}
        self.assertNotIn('broker-request', links)
        self.assertFalse(links['direct-script-call']['dashed'])
        outbound = links['agent-outbound']['points']
        self.assertGreater(outbound[0][0], outbound[-1][0])
        response = links['authorized-job-response']['points']
        self.assertLess(response[0][0], response[-1][0])

    def test_original_output_directories_are_protected(self):
        for name in ('journey', 'poc-implementation-review'):
            with self.assertRaisesRegex(ValueError, 'historical presentation'):
                concept.build(output_dir=ROOT / 'docs/presentations' / name)

    def test_single_editable_slide_with_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'concept.pptx'
            concept.deck.save_pptx(self.data, [self.scene], path)
            presentation = Presentation(path)
            self.assertEqual(len(presentation.slides), 1)
            slide = presentation.slides[0]
            self.assertFalse(any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes))
            self.assertIn(self.data['slides'][0]['notes'], slide.notes_slide.notes_text_frame.text)

    def test_export_matches_source_and_has_no_field_identifiers(self):
        import pymupdf
        from PIL import Image
        output = concept.SOURCE.parent
        with pymupdf.open(output / f'{concept.STEM}.pdf') as pdf:
            self.assertEqual(len(pdf), 1)
            normalize = lambda value: re.sub(r'\s+', '', value)
            text = normalize(pdf[0].get_text())
            for item in self.scene.items:
                if item['kind'] == 'text':
                    self.assertIn(normalize(item['value']), text)
        with Image.open(output / 'preview-02.png') as image:
            self.assertEqual(image.size, (1560, 878))
        source = concept.SOURCE.read_text('utf-8')
        self.assertNotRegex(source, r'020908\.xyz|WIN-[A-Z0-9]{6,}|(?:glpat-|glrt-)[A-Za-z0-9_-]{12,}')


if __name__ == '__main__':
    unittest.main()
