import * as React from "react";
import ledFonts from "../../constants/ledFonts.json";

const LED_W = 64;
const LED_H = 32;
const DOT = 8; // canvas pixels per LED
const SCROLL_GAP = 16;
const RAINBOW_CYCLES = 1.5;
const FRAME_MS = 66;

// Must match LAYOUTS in display/text/renderer.py.
export const TEXT_LAYOUTS = {
  1: { font: "6x10", height: 10, charWidth: 6, tops: [11] },
  2: { font: "6x10", height: 10, charWidth: 6, tops: [4, 18] },
  3: { font: "5x8", height: 8, charWidth: 5, tops: [2, 12, 22] },
  4: { font: "4x6", height: 6, charWidth: 4, tops: [1, 9, 17, 25] },
  5: { font: "4x6", height: 6, charWidth: 4, tops: [1, 7, 13, 19, 25] },
};

// Lit pixels of a row as [x, y] relative to the row's top-left, plus its width.
function layoutText(text, fontName) {
  const font = ledFonts[fontName];
  const pixels = [];
  let pen = 0;
  for (const ch of text) {
    const glyph = font.glyphs[ch.codePointAt(0)];
    if (!glyph) continue;
    const [dwidth, bbw, bbh, bbxoff, bbyoff, rows] = glyph;
    const top = font.ascent - bbyoff - bbh;
    rows.forEach((bits, ry) => {
      for (let cx = 0; cx < bbw; cx++) {
        if (bits & (1 << (bbw - 1 - cx))) pixels.push([pen + bbxoff + cx, top + ry]);
      }
    });
    pen += dwidth;
  }
  return { pixels, width: pen };
}

function rgbCss(rgb) {
  return `rgb(${rgb.join(",")})`;
}

function rainbowCss(x, phase) {
  const hue = (((x / LED_W) * RAINBOW_CYCLES - phase) % 1) + 1;
  return `hsl(${(hue % 1) * 360}, 100%, 50%)`;
}

// Draws the real board: same fonts, row spacing, scroll speed and rainbow.
export default function LedPreview({ rowCount, rows, scrollSeconds = 2 }) {
  const canvasRef = React.useRef(null);

  const laidOut = React.useMemo(() => {
    const layout = TEXT_LAYOUTS[rowCount] ?? TEXT_LAYOUTS[1];
    return layout.tops.map((top, i) => {
      const row = rows[i] ?? {};
      return { top, row, charWidth: layout.charWidth, ...layoutText(row.text ?? "", layout.font) };
    });
  }, [rowCount, rows]);

  React.useEffect(() => {
    const ctx = canvasRef.current.getContext("2d");
    const start = performance.now();

    const draw = () => {
      const seconds = (performance.now() - start) / 1000;
      const phase = (seconds * 0.25) % 1;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, LED_W * DOT, LED_H * DOT);

      const plot = (x, y, row) => {
        if (x < 0 || x >= LED_W) return;
        ctx.fillStyle =
          row.color_mode === "rainbow"
            ? rainbowCss(x, phase)
            : rgbCss(row.color ?? [255, 255, 255]);
        ctx.fillRect(x * DOT + 1, y * DOT + 1, DOT - 2, DOT - 2);
      };

      laidOut.forEach(({ top, row, pixels, width, charWidth }) => {
        if (width > LED_W && row.scroll !== false) {
          const period = width + SCROLL_GAP;
          const offset = Math.floor((seconds * charWidth) / scrollSeconds) % period;
          pixels.forEach(([x, y]) => {
            plot(x - offset, top + y, row);
            plot(x - offset + period, top + y, row);
          });
        } else {
          let startX = 0;
          if (row.align === "center") startX = Math.floor((LED_W - width) / 2);
          if (row.align === "right") startX = LED_W - width;
          pixels.forEach(([x, y]) => plot(x + startX, top + y, row));
        }
      });
    };

    draw();
    const moving = laidOut.some(
      ({ row, width }) =>
        (width > LED_W && row.scroll !== false) || (width > 0 && row.color_mode === "rainbow")
    );
    if (!moving) return undefined;
    const id = setInterval(draw, FRAME_MS);
    return () => clearInterval(id);
  }, [laidOut, scrollSeconds]);

  return (
    <canvas
      ref={canvasRef}
      width={LED_W * DOT}
      height={LED_H * DOT}
      style={{ width: "100%", maxWidth: 512, borderRadius: 4, display: "block", margin: "0 auto" }}
      aria-label="Preview of the LED board"
    />
  );
}
