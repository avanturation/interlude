import sys, io, math
sys.path.insert(0, 'misc')
import importlib
import wdth_displace as DP
import wdth_stems as ST
import wdth_multipliers as MU
import wdth_offset as OF
import freetype
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.varLib.instancer import instantiateVariableFont

_BASE = None
_CACHE = {}


def base():
    global _BASE
    if _BASE is None:
        f = TTFont('build/InterludeVariable-base.ttf')
        instantiateVariableFont(f, {'opsz': 14, 'wght': 400}, inplace=True)
        glyf = f['glyf']
        cmap = f.getBestCmap()
        ST.set_fallback_stem(ST.compute_fallback_stem(glyf, cmap))
        _BASE = (f, glyf, cmap)
    return _BASE


def glyph_coords(ch, s, wght=400, allow_diag=False):
    importlib.reload(DP)
    f, glyf, cmap = base()
    if wght != 400:
        f2 = TTFont('build/InterludeVariable-base.ttf')
        instantiateVariableFont(f2, {'opsz': 14, 'wght': wght}, inplace=True)
        glyf = f2['glyf']
        cmap = f2.getBestCmap()
        ST.set_fallback_stem(ST.compute_fallback_stem(glyf, cmap))
    gn = cmap.get(ord(ch))
    Wg = ST.measure_stem(glyf, gn)
    mult = MU.latin_stem_multiplier(s)
    res = DP.displace_v2(glyf, gn, s, Wg, mult, allow_diag=allow_diag)
    coords, ends, flags, bpts, se = res
    return coords, ends, flags


def render_char(ch, s, wght=400, px=420, allow_diag=False):
    coords, ends, flags = glyph_coords(ch, s, wght, allow_diag)
    fc = TTFont('build/InterludeVariable-base.ttf')
    instantiateVariableFont(fc, {'opsz': 14, 'wght': wght}, inplace=True)
    gl = fc['glyf']
    cm = fc.getBestCmap()
    gn = cm.get(ord(ch))
    g = gl[gn]
    g.coordinates = GlyphCoordinates([(round(x), round(y)) for x, y in coords])
    g.endPtsOfContours = list(ends)
    g.flags = bytearray(flags)
    g.recalcBounds(gl)
    b = io.BytesIO()
    fc.save(b)
    data = b.getvalue()
    ft = freetype.Face(io.BytesIO(data))
    ft.set_pixel_sizes(0, px)
    ft.load_char(ch, freetype.FT_LOAD_RENDER)
    bm = ft.glyph.bitmap
    im = Image.new("L", (bm.width + 40, bm.rows + 40), 255)
    if bm.width > 0:
        gi = Image.frombytes("L", (bm.width, bm.rows), bytes(bm.buffer))
        im.paste(Image.new("L", (bm.width, bm.rows), 0), (20, 20), gi)
    return im


def grid(specs, out, px=420):
    rows = []
    for label, items in specs:
        imgs = [render_char(ch, s, w, px) for (ch, s, w) in items]
        W = sum(i.width for i in imgs) + 20 * len(imgs)
        H = max(i.height for i in imgs)
        row = Image.new("L", (W, H), 200)
        x = 0
        for i in imgs:
            row.paste(i, (x, 0))
            x += i.width + 20
        rows.append(row)
    W = max(r.width for r in rows)
    H = sum(r.height for r in rows) + 10 * len(rows)
    big = Image.new("L", (W, H), 230)
    y = 0
    for r in rows:
        big.paste(r, (0, y))
        y += r.height + 10
    big.save(out)
    return out, big.size


def self_x(ch, s, wght=400):
    coords, ends, flags = glyph_coords(ch, s, wght)
    pts = [(round(x), round(y)) for x, y in coords]
    return DP._count_self_x(pts, ends, flags)


def edge_straightness(ch, s, wght=400):
    coords, ends, flags = glyph_coords(ch, s, wght)
    conts = []
    start = 0
    for e in ends:
        conts.append([(coords[k], flags[k] & 1) for k in range(start, e + 1)])
        start = e + 1
    worst = 0.0
    report = []
    for ci, cont in enumerate(conts):
        n = len(cont)
        for i in range(n):
            (ax, ay), aon = cont[i]
            (bx, by), bon = cont[(i + 1) % n]
            if not (aon and bon):
                continue
            L = math.hypot(bx - ax, by - ay)
            if L < 200:
                continue
            ang = abs(math.degrees(math.atan2(abs(by - ay), abs(bx - ax))))
            if ang < 20 or ang > 70:
                continue
            report.append((ci, i, round(ax), round(ay), round(bx), round(by), round(ang, 1)))
    return report
