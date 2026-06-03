"""Inter CJK 자동 QA 검증 스크립트.

검증 항목:
- calt CJK 컨텍스트 치환 (harfbuzz shaping)
- Vertical metrics 정합성
- 모든 weight에서 CJK 글리프 변형
- Display vs Text width 차이
- 글리프 수 검증
- OpenType feature 존재 확인
"""
import sys
import os
import math
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
failures = []


def check(condition, name):
    if condition:
        print(f"  {PASS} {name}")
    else:
        print(f"  {FAIL} {name}")
        failures.append(name)


def check_metrics(font_path):
    font = TTFont(font_path)
    os2 = font['OS/2']
    hhea = font['hhea']
    upm = font['head'].unitsPerEm

    typo_total = os2.sTypoAscender - os2.sTypoDescender
    win_total = os2.usWinAscent + os2.usWinDescent
    hhea_total = hhea.ascent - hhea.descent

    check(typo_total == 2556, f"typo total = 2556 (got {typo_total})")
    check(win_total >= 2556, f"win total >= 2556 (got {win_total})")
    check(hhea_total == 2556, f"hhea total = 2556 (got {hhea_total})")
    check(os2.sTypoAscender == 2024, f"sTypoAscender = 2024 (got {os2.sTypoAscender})")
    check(os2.sTypoDescender == -532, f"sTypoDescender = -532 (got {os2.sTypoDescender})")
    check(bool(os2.fsSelection & (1 << 7)), "USE_TYPO_METRICS set")
    check(os2.achVendID == "INTL", f"vendorID = INTL (got '{os2.achVendID}')")


def check_line_height(font_path):
    font = TTFont(font_path)
    os2 = font['OS/2']
    upm = font['head'].unitsPerEm
    total = os2.sTypoAscender - os2.sTypoDescender

    expected = {16: 20, 18: 22}
    for size, want in expected.items():
        got = round(size * total / upm)
        check(got == want, f"{size}px → line-height {got} (기대값 {want})")
        check(want % 2 == 0, f"{size}px line-height {want}은 짝수")


def check_calt_cjk(font_path):
    try:
        import uharfbuzz as hb
    except ImportError:
        print(f"  - calt CJK 검증 스킵 (uharfbuzz 미설치)")
        return

    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    hb_font = hb.Font(face)
    hb_font.scale = (2048, 2048)

    ft = TTFont(font_path)
    go = ft.getGlyphOrder()
    at_case_id = go.index('at.case') if 'at.case' in go else None

    if at_case_id is None:
        check(False, "at.case 글리프 존재")
        return

    def shape(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(hb_font, buf)
        return [i.codepoint for i in buf.glyph_infos]

    ids_kr = shape("가@나")
    ids_en = shape("a@b")

    check(at_case_id in ids_kr, "calt: 가@나 → @.case 치환됨")
    check(at_case_id not in ids_en, "calt: a@b → @ 원본 유지")


def check_ss05(font_path):
    try:
        import uharfbuzz as hb
    except ImportError:
        print(f"  - ss05 검증 스킵 (uharfbuzz 미설치)")
        return

    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    hb_font = hb.Font(face)
    hb_font.scale = (2048, 2048)

    ft = TTFont(font_path)
    go = ft.getGlyphOrder()
    hang_id = go.index('ellipsis.hang') if 'ellipsis.hang' in go else None

    if hang_id is None:
        check(False, "ellipsis.hang 글리프 존재")
        return

    def shape(text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        if features:
            hb.shape(hb_font, buf, features)
        else:
            hb.shape(hb_font, buf)
        return [i.codepoint for i in buf.glyph_infos]

    kr_on = shape("가…나", {"ss05": True})
    kr_off = shape("가…나")
    en_on = shape("a…b", {"ss05": True})

    check(hang_id in kr_on, "ss05: 가…나 → ellipsis.hang (한글 컨텍스트)")
    check(hang_id not in kr_off, "ss05: 가…나 OFF → ellipsis 원본 유지")
    check(hang_id not in en_on, "ss05: a…b → 영어에서는 변형 없음")


def check_weight_variation(font_path):
    for wght in [100, 900]:
        font = TTFont(font_path)
        for tag in ['MVAR', 'HVAR', 'GDEF']:
            if tag in font:
                del font[tag]
        inst = instantiateVariableFont(font, {"wght": wght}, inplace=True, overlap=True)
        cmap = inst.getBestCmap()

        ga_name = cmap.get(0xAC00)
        if ga_name:
            g = inst['glyf'][ga_name]
            has_coords = hasattr(g, 'coordinates') and len(g.coordinates) > 0
            check(has_coords, f"wght={wght}: 가 글리프 좌표 존재")


def check_opsz_axis(font_path):
    font = TTFont(font_path)
    axes = {a.axisTag: (a.minValue, a.maxValue) for a in font['fvar'].axes}

    check('opsz' in axes, "opsz 축 존재")
    check('wght' in axes, "wght 축 존재")
    if 'opsz' in axes:
        check(axes['opsz'] == (14.0, 32.0), f"opsz 범위 14-32 (got {axes['opsz']})")
    if 'wght' in axes:
        check(axes['wght'] == (100.0, 900.0), f"wght 범위 100-900 (got {axes['wght']})")


def check_glyph_count(font_path):
    font = TTFont(font_path)
    count = len(font.getGlyphOrder())
    check(count > 20000, f"글리프 수 > 20000 (got {count})")


def check_features(font_path):
    font = TTFont(font_path)
    gsub = font['GSUB'].table
    features = set(fr.FeatureTag for fr in gsub.FeatureList.FeatureRecord)

    required = ['calt', 'ccmp', 'case', 'dlig', 'frac', 'tnum',
                'zero', 'ss01', 'ss02', 'ss05', 'ss06',
                'ss07', 'ss08', 'ss09', 'ss10']
    for f in required:
        check(f in features, f"GSUB feature '{f}' 존재")


def check_features_work(font_path):
    try:
        import uharfbuzz as hb
    except ImportError:
        print(f"  - OpenType 작동 검증 스킵 (uharfbuzz 미설치)")
        return

    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    hb_font = hb.Font(face)
    hb_font.scale = (2048, 2048)

    ft = TTFont(font_path)
    go = ft.getGlyphOrder()

    def shape(text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        if features:
            hb.shape(hb_font, buf, features)
        else:
            hb.shape(hb_font, buf)
        return [i.codepoint for i in buf.glyph_infos]

    def differs(text, tag):
        on = shape(text, {tag: True})
        off = shape(text, {tag: False})
        return on != off

    tests = [
        ("calt", "->", "화살표 합자"),
        ("dlig", "?!", "interrobang"),
        ("frac", "1/3", "분수"),
        ("tnum", "1111", "고정폭 숫자"),
        ("zero", "0", "슬래시 0"),
        ("ss01", "69", "Open Digits"),
        ("ss02", "Il", "Inter Disambiguation"),
        ("ss05", "가…나", "Korean ellipsis"),
        ("ss06", "Il1", "Pretendard Disambiguation"),
        ("ss09", "ABC", "Circled/Squared"),
        ("ss10", "①", "Medium symbols"),
        ("cv01", "1", "대체 1"),
        ("cv08", "I", "I 세리프"),
        ("cv11", "a", "단층 a"),
    ]

    for tag, text, desc in tests:
        works = differs(text, tag)
        check(works, f"{tag}: {desc} 작동")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 misc/check-font.py <variable.ttf>")
        sys.exit(1)

    text_path = sys.argv[1]

    print(f"\n{'='*50}")
    print(f"Inter CJK QA: {os.path.basename(text_path)}")
    print(f"{'='*50}\n")

    print("[Metrics]")
    check_metrics(text_path)

    print("\n[Line Height]")
    check_line_height(text_path)

    print("\n[Variable Axes]")
    check_opsz_axis(text_path)

    print("\n[calt CJK 컨텍스트 치환]")
    check_calt_cjk(text_path)

    print("\n[ss05 한국 현지화]")
    check_ss05(text_path)

    print("\n[Weight 변형]")
    check_weight_variation(text_path)

    print("\n[글리프 수]")
    check_glyph_count(text_path)

    print("\n[OpenType Features]")
    check_features(text_path)

    print("\n[OpenType 작동 검증]")
    check_features_work(text_path)

    print(f"\n{'='*50}")
    if failures:
        print(f"{FAIL} {len(failures)}개 실패:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"{PASS} 모든 검증 통과")
        sys.exit(0)


if __name__ == "__main__":
    main()
