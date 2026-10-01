import sys
import unittest
from pathlib import Path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check import check_variable_names


class VariableNamingTests(unittest.TestCase):
    def test_export_names(self):
        for extension in ('ttf', 'woff2'):
            with self.subTest(extension=extension), TTFont(ROOT / 'fonts' / f'InterludeVariable.{extension}') as font:
                check_variable_names(font)

    def test_static_name_collision_is_rejected(self):
        for name_id, wrong in ((1, 'Interlude'), (4, 'Interlude'),
                               (6, 'Interlude-Regular'), (16, 'Interlude'), (25, 'Interlude')):
            with self.subTest(name_id=name_id), TTFont(ROOT / 'fonts/InterludeVariable.ttf') as font:
                font['name'].setName(wrong, name_id, 3, 1, 0x409)
                with self.assertRaises(AssertionError):
                    check_variable_names(font)


if __name__ == '__main__':
    unittest.main()
