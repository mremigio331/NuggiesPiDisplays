"""Minimal BDF bitmap-font renderer.

Just enough of the BDF format to draw text into a PIL image using the exact
same glyphs as the LED matrix library's `graphics.DrawText`. This lets the
rainbow ("Caitlyn Mode") path recolor pixels while keeping the bitmap font
identical to the solid-color path (Pillow's FreeType can't load all three of
our BDF files, so we parse them ourselves).

Placement matches `graphics.DrawText(canvas, font, x, y, ...)` where `y` is the
baseline: for each glyph the bitmap's top-left is drawn at
    (pen_x + bbxoff, baseline_y - bbyoff - bbh)
and the pen advances by the glyph's DWIDTH.
"""

from pathlib import Path
from PIL import Image, ImageDraw


class _Glyph:
    __slots__ = ("dwidth", "bbw", "bbh", "bbxoff", "bbyoff", "rows")

    def __init__(self, dwidth, bbw, bbh, bbxoff, bbyoff, rows):
        self.dwidth = dwidth
        self.bbw = bbw
        self.bbh = bbh
        self.bbxoff = bbxoff
        self.bbyoff = bbyoff
        self.rows = rows  # list of ints, one per bitmap row (MSB = leftmost px)


class BDFFont:
    def __init__(self, path: Path):
        self.glyphs: dict[int, _Glyph] = {}
        self.default_dwidth = 0
        self._parse(path)

    def _parse(self, path: Path) -> None:
        enc = dwidth = None
        bbw = bbh = bbxoff = bbyoff = 0
        rows: list[int] = []
        in_bitmap = False
        with open(path, "r", encoding="latin-1") as f:
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                key = parts[0]
                if key == "ENCODING":
                    enc = int(parts[1])
                elif key == "DWIDTH":
                    dwidth = int(parts[1])
                elif key == "BBX":
                    bbw, bbh, bbxoff, bbyoff = (int(p) for p in parts[1:5])
                elif key == "BITMAP":
                    in_bitmap = True
                    rows = []
                elif key == "ENDCHAR":
                    in_bitmap = False
                    if enc is not None and enc >= 0:
                        self.glyphs[enc] = _Glyph(
                            dwidth if dwidth is not None else bbw,
                            bbw,
                            bbh,
                            bbxoff,
                            bbyoff,
                            rows,
                        )
                    enc = dwidth = None
                    rows = []
                elif in_bitmap:
                    # Each row is hex; the bitmap is left-aligned within
                    # ceil(bbw/8)*8 bits, so shift down to bbw significant bits.
                    hexbits = len(key) * 4
                    val = int(key, 16)
                    rows.append(val >> (hexbits - bbw) if hexbits > bbw else val)
        if self.glyphs:
            self.default_dwidth = max(g.dwidth for g in self.glyphs.values())

    def draw(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        baseline_y: int,
        text: str,
        fill=(255, 255, 255),
    ) -> int:
        """Draw `text` with its baseline at `baseline_y`. Returns the end pen x."""
        pen = x
        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is None:
                pen += self.default_dwidth
                continue
            top = baseline_y - g.bbyoff - g.bbh
            for ry, bits in enumerate(g.rows):
                for cx in range(g.bbw):
                    if bits & (1 << (g.bbw - 1 - cx)):
                        draw.point((pen + g.bbxoff + cx, top + ry), fill=fill)
            pen += g.dwidth
        return pen


_cache: dict[str, BDFFont] = {}


def load(path) -> BDFFont:
    key = str(path)
    if key not in _cache:
        _cache[key] = BDFFont(Path(path))
    return _cache[key]
