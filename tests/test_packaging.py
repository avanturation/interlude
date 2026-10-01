import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from subset_fonts import unicode_range_to_codepoints, codepoints_to_range_str, _subset_one
from release import verify_subsets
class SubsetTests(unittest.TestCase):
    def test_range_round_trip_and_wildcard(self):
        cps=unicode_range_to_codepoints('U+0041-005A, U+AC00, U+1F6??')
        self.assertEqual(cps,unicode_range_to_codepoints(codepoints_to_range_str(cps)))
        self.assertIn(0x1F6FF,cps);self.assertIn(0xAC00,cps)
    def test_failed_font_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory()as tmp:
            with self.assertRaisesRegex(RuntimeError,'Subset failed'):
                _subset_one((str(Path(tmp)/'missing.ttf'),{65},str(Path(tmp)/'x.woff2')))
    def test_declared_missing_subset_file_fails(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp);(p/'interlude-variable-dynamic-subset.css').write_text("@font-face {src:url('./missing.woff2');unicode-range:U+AC00;}")
            with self.assertRaises(FileNotFoundError):verify_subsets(p)
if __name__=='__main__':unittest.main()
