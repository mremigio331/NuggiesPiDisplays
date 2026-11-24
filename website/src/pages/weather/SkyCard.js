import React from "react";

// Mirrors display/weather/sky.py + the sky screen in display/weather/renderer.py
// (64x32 matrix coordinates), so the website shows what the panel shows.

const DAY_MS = 86400000;
const SYNODIC_MONTH = 29.530588853;
const KNOWN_NEW_MOON = Date.UTC(2000, 0, 6, 18, 14);

const ARC_X0 = 5;
const ARC_X1 = 58;
const ARC_Y_HORIZON = 22; // over half the sun/moon shows at sunrise and sunset
const ARC_Y_PEAK = 11;
const BODY_R = 3.2;
const GROUND_TOP = 25;
const STARS = [
  [3, 11],
  [11, 9],
  [20, 12],
  [42, 9],
  [52, 14],
  [60, 9],
];

// Mount Rainier — mirrors _RAINIER and friends in display/weather/renderer.py.
const RAINIER = [
  [0, 25],
  [2, 25],
  [8, 23],
  [14, 21],
  [19, 19],
  [23, 17],
  [26, 16],
  [28, 15],
  [30, 14],
  [35, 14],
  [38, 15],
  [41, 17],
  [42, 18],
  [44, 17],
  [46, 19],
  [50, 21],
  [55, 23],
  [61, 25],
  [63, 25],
];
const SNOW_LINE = 20;
const GLACIERS = { 15: 22, 16: 23, 21: 22, 25: 21, 31: 21, 39: 22, 40: 23, 48: 22 };
const BARE_ROCK = new Set(["44,17", "43,18", "44,18", "45,18"]); // Little Tahoma
const SHADE_FROM_X = 33;
const TREELINE = 23;
const C = {
  snow: [210, 220, 235],
  shade: [150, 165, 195],
  rock: [75, 80, 105],
  forest: [25, 60, 40],
  ground: [15, 38, 28],
};

// Python's round() rounds halves to even; match it so both draw the same pixels.
const roundHalfEven = (v) => {
  const f = Math.floor(v);
  const d = v - f;
  if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
  return Math.round(v);
};

const rainierTop = (x) => {
  for (let i = 0; i < RAINIER.length - 1; i++) {
    const [x0, y0] = RAINIER[i];
    const [x1, y1] = RAINIER[i + 1];
    if (x0 <= x && x <= x1) return roundHalfEven(y0 + ((y1 - y0) * (x - x0)) / (x1 - x0));
  }
  return GROUND_TOP;
};

const rainierPixel = (x, y) => {
  if (y >= GROUND_TOP) return C.ground;
  const snowBottom = Math.max(SNOW_LINE, GLACIERS[x] ?? 0);
  if (y < snowBottom && !BARE_ROCK.has(`${x},${y}`)) return x >= SHADE_FROM_X ? C.shade : C.snow;
  if (y >= TREELINE) return C.forest;
  return C.rock;
};

// One rect per pixel run of the same colour, per column — a pixel-exact copy
// of the matrix. Built once; night only changes the brightness.
const MOUNTAIN_RUNS = (() => {
  const runs = [];
  for (let x = 0; x < 64; x++) {
    let start = rainierTop(x);
    let color = rainierPixel(x, start);
    for (let y = start + 1; y <= 32; y++) {
      const next = y < 32 ? rainierPixel(x, y) : null;
      if (next !== color) {
        runs.push({ x, y: start, h: y - start, color });
        start = y;
        color = next;
      }
    }
  }
  return runs;
})();

const rgb = ([r, g, b], dim) =>
  `rgb(${Math.floor(r * dim)},${Math.floor(g * dim)},${Math.floor(b * dim)})`;

function Rainier({ night }) {
  const dim = night ? 0.5 : 1;
  return (
    <g shapeRendering="crispEdges">
      {MOUNTAIN_RUNS.map((r) => (
        <rect
          key={`${r.x}-${r.y}`}
          x={r.x}
          y={r.y}
          width="1.02"
          height={r.h}
          fill={rgb(r.color, dim)}
        />
      ))}
    </g>
  );
}

const clamp01 = (v) => Math.min(1, Math.max(0, v));

// 0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter
export const moonPhase = (nowMs) =>
  (((((nowMs - KNOWN_NEW_MOON) / DAY_MS) % SYNODIC_MONTH) + SYNODIC_MONTH) % SYNODIC_MONTH) /
  SYNODIC_MONTH;

const PHASE_NAMES = [
  "New moon",
  "Waxing crescent",
  "First quarter",
  "Waxing gibbous",
  "Full moon",
  "Waning gibbous",
  "Last quarter",
  "Waning crescent",
];
const phaseName = (phase) => PHASE_NAMES[Math.round(phase * 8) % 8];

// Open-Meteo times are "YYYY-MM-DDTHH:MM" in the weather location's own time.
// They are parsed as UTC so the maths never depends on the viewer's timezone.
const parseLocal = (s) => {
  const m = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)/.exec(s || "");
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : null;
};

export function computeSky(sky, nowMs = Date.now()) {
  if (!sky) return null;
  const rises = (sky.sunrise || []).map(parseLocal);
  const sets = (sky.sunset || []).map(parseLocal);
  if (rises[0] == null || sets[0] == null) return null;

  const localNow = nowMs + (sky.utc_offset_seconds || 0) * 1000;
  const nextRise = rises[1] ?? rises[0] + DAY_MS;

  let body, start, end;
  if (localNow < rises[0]) {
    body = "moon";
    start = sets[0] - DAY_MS;
    end = rises[0];
  } else if (localNow <= sets[0]) {
    body = "sun";
    start = rises[0];
    end = sets[0];
  } else {
    body = "moon";
    start = sets[0];
    end = nextRise;
  }
  const progress = end > start ? clamp01((localNow - start) / (end - start)) : 0;
  return {
    body,
    progress,
    phase: moonPhase(nowMs),
    localNow,
    sunrise: rises[0],
    sunset: sets[0],
  };
}

// ms on the location's clock -> "3:45 PM"
const fmtClock = (ms) => {
  const d = new Date(ms);
  const h = d.getUTCHours();
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${h % 12 || 12}:${mm} ${h < 12 ? "AM" : "PM"}`;
};

function Moon({ cx, cy, phase }) {
  const c = Math.cos(2 * Math.PI * phase); // 1 new, 0 quarter, -1 full
  const waxing = phase < 0.5;
  const R = BODY_R;
  const lit = `M 0 ${-R} A ${R} ${R} 0 0 1 0 ${R} A ${Math.abs(c) * R} ${R} 0 0 ${c > 0 ? 0 : 1} 0 ${-R} Z`;
  return (
    <g transform={`translate(${cx} ${cy})`}>
      <circle r={R} fill="#2d3246" />
      <path d={lit} fill="#e1e6f5" transform={waxing ? undefined : "scale(-1 1)"} />
    </g>
  );
}

// ── Weather on the sky — mirrors condition()/scene() in display/weather/sky.py ──

export function skyCondition(code) {
  const c = Number(code);
  if (code == null || Number.isNaN(c)) return "clear";
  if (c === 0) return "clear";
  if (c === 1) return "mostly_clear";
  if (c === 2) return "partly";
  if (c === 3) return "overcast";
  if ([45, 48].includes(c)) return "fog";
  if ([51, 53, 55, 56, 57].includes(c)) return "drizzle";
  if ([65, 67, 82].includes(c)) return "heavy_rain";
  if ([61, 63, 66, 80, 81].includes(c)) return "rain";
  if ([75, 86].includes(c)) return "heavy_snow";
  if ([71, 73, 77, 85].includes(c)) return "snow";
  if ([95, 96, 99].includes(c)) return "storm";
  return "overcast";
}

// Always drawn (clouds go over it) so the position shows on cloudy days; fog dims it
const BODY_SHOW = { fog: "dim" };
const DIPPER = [
  [1, 8],
  [4, 9],
  [7, 10],
  [10, 11],
  [10, 14],
  [15, 14],
  [15, 10],
];
const ORION = [
  [51, 14],
  [53, 13],
  [55, 12],
  [57, 9],
  [49, 19],
];
const BETELGEUSE = [48, 8];
const RIGEL = [58, 18];
// A cartoon cloud, 14 x 6: "o" outline, "w" fill, "s" shaded underside.
const CLOUD = [
  ".....oooo.....",
  "..ooowwwwo....",
  ".owwwwwwwwooo.",
  "owwwwwwwwwwwwo",
  "osssssssssssso",
  ".oooooooooooo.",
];
const CLOUDS_AT = {
  mostly_clear: [[44, 9]],
  partly: [
    [2, 10],
    [44, 9],
  ],
};
const DECK_AT = [
  [-3, 9],
  [9, 8],
  [21, 9],
  [33, 8],
  [45, 9],
  [57, 8],
];
const cloudPixels = (ox, oy, line, fill, shade) => {
  const out = [];
  CLOUD.forEach((text, row) => {
    [...text].forEach((ch, col) => {
      if (ch !== ".") out.push([ox + col, oy + row, ch === "o" ? line : ch === "s" ? shade : fill]);
    });
  });
  return out;
};
const FALL = {
  drizzle: [6, 1, "rain"],
  rain: [4, 2, "rain"],
  heavy_rain: [3, 2, "rain"],
  storm: [3, 2, "rain"],
  snow: [5, 1, "snow"],
  heavy_snow: [3, 1, "snow"],
};
const BOLT = [
  [16, 14],
  [15, 15],
  [14, 16],
  [13, 17],
  [14, 17],
  [15, 17],
  [14, 18],
  [13, 19],
  [12, 20],
];
const FOG_ROWS = [16, 19, 22];
const DAY = {
  cloud_line: [70, 80, 105],
  cloud: [240, 245, 255],
  cloud_shade: [165, 175, 195],
  deck_line: [70, 75, 95],
  deck: [185, 190, 205],
  deck_shade: [125, 130, 150],
  storm_line: [35, 35, 50],
  storm: [105, 105, 125],
  storm_shade: [70, 70, 88],
  rain: [80, 140, 255],
  snow: [220, 230, 255],
  fog: [120, 125, 140],
};
const NIGHT = {
  cloud_line: [35, 38, 52],
  cloud: [120, 125, 145],
  cloud_shade: [80, 85, 105],
  deck_line: [30, 32, 44],
  deck: [85, 88, 105],
  deck_shade: [58, 60, 75],
  storm_line: [20, 20, 30],
  storm: [55, 55, 70],
  storm_shade: [40, 40, 52],
  rain: [50, 90, 170],
  snow: [150, 160, 185],
  fog: [60, 62, 72],
};
const STAR = [150, 155, 180];
const STAR_FAINT = [90, 95, 120];
const STAR_RED = [220, 120, 90];
const STAR_BLUE = [160, 185, 255];
const LIGHTNING = [255, 240, 0];

export function skyScene(code, night, minute, groundTop) {
  const cond = skyCondition(code);
  const pal = night ? NIGHT : DAY;
  const back = [];
  let front = [];
  const over = [];

  if (night && (cond === "clear" || cond === "mostly_clear")) {
    STARS.forEach(([x, y]) => back.push([x, y, STAR_FAINT]));
    [...DIPPER, ...ORION].forEach(([x, y]) => back.push([x, y, STAR]));
    back.push([...BETELGEUSE, STAR_RED]);
    back.push([...RIGEL, STAR_BLUE]);
  } else if (night && cond === "partly") {
    STARS.forEach(([x, y]) => back.push([x, y, STAR_FAINT]));
  }

  if (FALL[cond]) {
    const [step, length, key] = FALL[cond];
    for (let x = 1; x < 64; x += step) {
      for (let base = 15; base < 32; base += 6) {
        const y0 = base + ((x * 3 + minute) % 6);
        for (let y = y0; y < y0 + length; y++) {
          if (y < groundTop(x)) back.push([x, y, pal[key]]);
        }
      }
    }
  }
  // lightning: in front of the sun/moon, under the clouds
  if (cond === "storm") BOLT.forEach(([x, y]) => front.push([x, y, LIGHTNING]));

  (CLOUDS_AT[cond] || []).forEach(([ox, oy]) => {
    front = front.concat(cloudPixels(ox, oy, pal.cloud_line, pal.cloud, pal.cloud_shade));
  });

  let kind = null;
  if (["overcast", "drizzle", "rain", "heavy_rain", "snow", "heavy_snow"].includes(cond)) {
    kind = "deck";
  } else if (cond === "storm") {
    kind = "storm";
  }
  if (kind) {
    DECK_AT.forEach(([ox, oy]) => {
      front = front.concat(
        cloudPixels(ox, oy, pal[`${kind}_line`], pal[kind], pal[`${kind}_shade`])
      );
    });
  }

  if (cond === "fog") {
    FOG_ROWS.forEach((y) => {
      for (let x = 0; x < 64; x++) {
        if ((x + y * 3 + minute) % 9 < 6) over.push([x, y, pal.fog]);
      }
    });
  }

  return { body: BODY_SHOW[cond] || "show", back, front, over };
}

function Pixels({ pixels }) {
  return (
    <g shapeRendering="crispEdges">
      {pixels.map(([x, y, c], i) => (
        <rect key={i} x={x} y={y} width="1.02" height="1.02" fill={rgb(c, 1)} />
      ))}
    </g>
  );
}

export default function SkyCard({ sky, weatherCode, weatherDesc }) {
  // Re-evaluate every minute so the sun/moon creeps along without a data refetch.
  const [nowMs, setNowMs] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const pos = computeSky(sky, nowMs);
  if (!pos) return null;

  const { body, progress, phase, localNow } = pos;
  const cx = ARC_X0 + progress * (ARC_X1 - ARC_X0);
  const cy = ARC_Y_HORIZON - (ARC_Y_HORIZON - ARC_Y_PEAK) * Math.sin(Math.PI * progress);
  const isNight = body === "moon";
  const minute = new Date(localNow).getUTCMinutes(); // the location's own clock
  const layers = skyScene(weatherCode, isNight, minute, rainierTop);
  const bodyOpacity = layers.body === "dim" ? 0.35 : 1;

  const arc = Array.from({ length: 25 }, (_, i) => {
    const p = i / 24;
    const x = ARC_X0 + p * (ARC_X1 - ARC_X0);
    const y = ARC_Y_HORIZON - (ARC_Y_HORIZON - ARC_Y_PEAK) * Math.sin(Math.PI * p);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");

  return (
    <>
      <div style={{ textAlign: "center", color: "#fff", fontWeight: 600, marginBottom: 6 }}>
        {fmtClock(localNow)}
      </div>
      <svg
        viewBox="0 0 64 32"
        style={{ width: "100%", display: "block", borderRadius: 6 }}
        role="img"
        aria-label={`${isNight ? `Moon, ${phaseName(phase)}` : "Sun"}${weatherDesc ? `, ${weatherDesc}` : ""}`}
      >
        <rect width="64" height="32" fill={isNight ? "#05070d" : "#10223d"} />
        <Pixels pixels={layers.back} />
        <polyline
          points={arc}
          fill="none"
          stroke="#7090b0"
          strokeWidth="0.3"
          strokeDasharray="1 1.2"
          opacity="0.5"
        />
        {layers.body !== "hide" && (
          <g opacity={bodyOpacity}>
            {isNight ? (
              <Moon cx={cx} cy={cy} phase={phase} />
            ) : (
              <circle cx={cx} cy={cy} r={BODY_R} fill="#ffc800" />
            )}
          </g>
        )}
        {/* clouds pass in front of the sun/moon */}
        <Pixels pixels={layers.front} />
        {/* Mount Rainier last, so the sun/moon rises from and sets behind it */}
        <Rainier night={isNight} />
        {/* fog drifts over the mountain */}
        <Pixels pixels={layers.over} />
      </svg>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          color: "#aaa",
          fontSize: "0.8rem",
          marginTop: 6,
        }}
      >
        <span>↑ {fmtClock(pos.sunrise)}</span>
        <span>{[weatherDesc, isNight ? phaseName(phase) : null].filter(Boolean).join(" · ")}</span>
        <span>↓ {fmtClock(pos.sunset)}</span>
      </div>
    </>
  );
}
