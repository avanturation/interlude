import io
import uharfbuzz as hb
import freetype
from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

FONT = "build/InterludeVariable.ttf"
OUT = "/tmp/ykK_proof.png"
TEXT = "Y k K Yk kK York"
WIDTHS = [100, 125, 150]
PX = 150
PAD = 50
UPM = 2048
LINE_H = int(PX * 1.5)
LABEL_H = 46
CANVAS_W = 1500


def instanced_bytes(width):
    f = TTFont(FONT)
    instantiateVariableFont(f, {"opsz": 14, "wght": 400, "wdth": width}, inplace=True)
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()


def shape(data, text):
    face = hb.Face(data)
    font = hb.Font(face)
    font.scale = (UPM, UPM)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True, "calt": True})
    return buf.glyph_infos, buf.glyph_positions


def render_line(canvas, ftface, data, text, x0, baseline):
    infos, pos = shape(data, text)
    pen = x0
    for inf, p in zip(infos, pos):
        ftface.load_glyph(inf.codepoint, freetype.FT_LOAD_RENDER)
        bm = ftface.glyph.bitmap
        w, h = bm.width, bm.rows
        left = ftface.glyph.bitmap_left
        top = ftface.glyph.bitmap_top
        px = int(round(pen + p.x_offset * PX / UPM)) + left
        py = baseline - top - int(round(p.y_offset * PX / UPM))
        if w > 0 and h > 0:
            glyph_img = Image.frombytes("L", (w, h), bytes(bm.buffer))
            black = Image.new("L", (w, h), 0)
            canvas.paste(black, (px, py), glyph_img)
        pen += p.x_advance * PX / UPM


blocks = []
for w in WIDTHS:
    data = instanced_bytes(w)
    ftface = freetype.Face(io.BytesIO(data))
    ftface.set_pixel_sizes(0, PX)
    blocks.append((w, data, ftface))

block_h = LABEL_H + LINE_H
canvas_h = PAD * 2 + block_h * len(WIDTHS)
img = Image.new("L", (CANVAS_W, canvas_h), 255)
draw = ImageDraw.Draw(img)

y = PAD
for w, data, ftface in blocks:
    draw.rectangle([PAD, y, CANVAS_W - PAD, y + 30], fill=60)
    draw.text((PAD + 10, y + 8), f"wdth = {w}", fill=255)
    y += LABEL_H
    render_line(img, ftface, data, TEXT, PAD, y + PX)
    y += LINE_H

img.convert("RGB").save(OUT)
print(f"saved {OUT} ({CANVAS_W}x{canvas_h})")
