import sys
import io
import uharfbuzz as hb
import freetype
from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont

VARIANTS = [
    ("/tmp/hs_100.ttf", "HSCALE 1.00 (현재 - 세로만 늘림)"),
    ("/tmp/hs_1015.ttf", "HSCALE 1.015 (가로 +1.5%)"),
    ("/tmp/hs_1025.ttf", "HSCALE 1.025 (가로 +2.5%)"),
]
OUT = "/tmp/hscale_compare.png"

LINES = [
    "한글 Latin 혼용 The quick 명동 서울 정거장",
    "가나다라마바사 읽기 좋은 본문 ABCDEFG 0123",
    "국문 정렬 와글와글 문문문 동대문 永格門",
]
PX = 52
PAD = 40
UPM = 2048
LINE_H = int(PX * 1.7)
BLOCK_GAP = 30
LABEL_H = 38
CANVAS_W = 1700


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
for path, label in VARIANTS:
    data = open(path, "rb").read()
    ftface = freetype.Face(io.BytesIO(data))
    ftface.set_pixel_sizes(0, PX)
    blocks.append((label, data, ftface))

block_h = LABEL_H + LINE_H * len(LINES) + BLOCK_GAP
canvas_h = PAD * 2 + block_h * len(VARIANTS)
img = Image.new("L", (CANVAS_W, canvas_h), 255)
draw = ImageDraw.Draw(img)

y = PAD
for label, data, ftface in blocks:
    draw.rectangle([PAD, y, CANVAS_W - PAD, y + 26], fill=60)
    draw.text((PAD + 10, y + 7), label, fill=255)
    y += LABEL_H
    for line in LINES:
        render_line(img, ftface, data, line, PAD, y + PX)
        y += LINE_H
    y += BLOCK_GAP

img.convert("RGB").save(OUT)
print(f"saved {OUT} ({CANVAS_W}x{canvas_h})")
