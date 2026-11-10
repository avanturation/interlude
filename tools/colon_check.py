"""Check numeric colon alignment independently of optional contextual alternates."""
import itertools
import uharfbuzz as hb


def check_numeric_colons(font_data, glyph_order):
    font = hb.Font(hb.Face(font_data))

    def shape(text, features, script):
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        buffer.script = script
        hb.shape(font, buffer, features)
        return [glyph_order[g.codepoint] for g in buffer.glyph_infos]

    options = (
        {},
        {'calt': False},
        {'calt': False, 'tnum': True},
        {'calt': False, 'cv01': True, 'cv09': True, 'zero': True},
        {'calt': False, 'ss07': True},
        {'calt': False, 'tnum': True, 'ss07': True},
    )
    scripts = ('Zyyy', 'Latn', 'Hang', 'Hani', 'Kana', 'Cyrl', 'Grek')
    count = 0
    for weight, size, width in itertools.product(range(100, 901, 100), (14, 32), (75, 100, 125)):
        font.set_variations({'wght': weight, 'opsz': size, 'wdth': width})
        for script, features in itertools.product(scripts, options):
            for text in ('1:29', '00:00', '12:34:56', '16:9'):
                glyphs = shape(text, features, script)
                colons = [g for g in glyphs if g.startswith('colon')]
                assert len(colons) == text.count(':'), (text, glyphs)
                assert all('.case' in g for g in colons), (
                    'Numeric colon must be centered', text, features, script,
                    weight, size, width, colons)
                count += 1
            # Ordinary punctuation and raised/lowered figures keep their forms.
            for text in ('a:b', 'abc:def', 'A:B', '1:word', 'word:29'):
                glyphs = shape(text, {'calt': False}, script)
                assert [g for g in glyphs if g.startswith('colon')] == ['colon'], (
                    'Non-numeric colon changed', text, script, glyphs)
                count += 1
            # Greek/Cyrillic fonts historically expose only their own feature set.
            if script not in ('Cyrl', 'Grek'):
                for feature in ('sups', 'subs', 'numr', 'dnom'):
                    glyphs = shape('1:29', {'calt': False, feature: True}, script)
                    assert 'colon' in glyphs, (feature, script, glyphs)
                    count += 1
    return count
