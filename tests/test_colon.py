import sys
import unittest
from pathlib import Path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from colon_check import check_numeric_colons


class NumericColonTests(unittest.TestCase):
    def test_default_alignment_and_punctuation_controls(self):
        path = ROOT / 'fonts/InterludeVariable.ttf'
        with TTFont(path) as font:
            self.assertGreater(check_numeric_colons(path.read_bytes(), font.getGlyphOrder()), 0)

    def test_woff2_uses_the_same_substitutions(self):
        with TTFont(ROOT / 'fonts/InterludeVariable.ttf') as ttf, \
             TTFont(ROOT / 'fonts/InterludeVariable.woff2') as web:
            self.assertEqual(ttf.getGlyphOrder(), web.getGlyphOrder())
            self.assertEqual(ttf.getTableData('GSUB'), web.getTableData('GSUB'))


if __name__ == '__main__':
    unittest.main()
