import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { getSystemHealth } from "../../services/API";

// Pi 4 heat bands. It starts slowing itself down at 80°C (and a soft limit can
// kick in at 60°C on some boards), so 70°C is the "warm" line.
const TEMP_WARM = 70;
const TEMP_HOT = 80;
const RANGES = [
  { hours: 24, label: "24 hours" },
  { hours: 168, label: "7 days" },
];

// `vcgencmd get_throttled` flag -> plain label.
const THROTTLE_LABELS = {
  under_voltage: "Low power now",
  freq_capped: "Speed capped now",
  throttled: "Slowed now",
  soft_temp_limit: "Heat limit now",
  under_voltage_since_boot: "Low power since boot",
  freq_capped_since_boot: "Speed capped since boot",
  throttled_since_boot: "Slowed since boot",
  soft_temp_limit_since_boot: "Heat limit since boot",
};

function tempStatus(t) {
  if (t == null) return { label: "—", badge: "m-badge-gray" };
  if (t >= TEMP_HOT) return { label: "Hot", badge: "m-badge-red" };
  if (t >= TEMP_WARM) return { label: "Warm", badge: "m-badge-warm" };
  return { label: "OK", badge: "m-badge-green" };
}

function formatUptime(seconds) {
  if (seconds == null) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatTime(epoch, withDay) {
  const d = new Date(epoch * 1000);
  return d.toLocaleString([], {
    ...(withDay ? { weekday: "short" } : {}),
    hour: "numeric",
    minute: "2-digit",
  });
}

function Stat({ label, value, sub }) {
  return (
    <div
      style={{
        background: "#0b1726",
        border: "1px solid #1a2a40",
        borderRadius: 10,
        padding: "10px 12px",
        minWidth: 0,
      }}
    >
      <div style={{ color: "#5a7a9a", fontSize: "0.68rem", fontWeight: 700 }}>{label}</div>
      <div style={{ color: "#e6eef7", fontSize: "1.25rem", fontWeight: 700, marginTop: 2 }}>
        {value}
      </div>
      {sub && <div style={{ color: "#8a9ab0", fontSize: "0.68rem", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

// One-series line of logged CPU temps. Dashed guide lines mark the warm/hot
// bands; tap or drag across the chart to read a point.
function TempChart({ samples, withDay }) {
  const points = samples.filter((s) => s.temp != null);
  const [hover, setHover] = React.useState(null);
  const svgRef = React.useRef(null);

  if (points.length < 2) {
    return (
      <div style={{ color: "#8a9ab0", fontSize: "0.75rem", padding: "12px 0" }}>
        Not enough readings yet. The Pi saves one every 10 minutes.
      </div>
    );
  }

  const W = 320;
  const H = 150;
  const pad = { l: 30, r: 8, t: 8, b: 20 };
  const t0 = points[0].t;
  const t1 = points[points.length - 1].t;
  const temps = points.map((p) => p.temp);
  const yMin = Math.floor(Math.min(40, ...temps) / 10) * 10;
  const yMax = Math.ceil(Math.max(TEMP_HOT + 5, ...temps) / 10) * 10;
  const x = (t) => pad.l + ((t - t0) / Math.max(t1 - t0, 1)) * (W - pad.l - pad.r);
  const y = (v) => pad.t + (1 - (v - yMin) / (yMax - yMin)) * (H - pad.t - pad.b);
  const path = points
    .map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.temp).toFixed(1)}`)
    .join("");
  const ticks = [];
  for (let v = yMin; v <= yMax; v += 10) ticks.push(v);

  const pick = (clientX) => {
    const rect = svgRef.current.getBoundingClientRect();
    const sx = ((clientX - rect.left) / rect.width) * W;
    let best = points[0];
    for (const p of points) if (Math.abs(x(p.t) - sx) < Math.abs(x(best.t) - sx)) best = p;
    setHover(best);
  };

  return (
    <div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block", touchAction: "pan-y" }}
        onPointerMove={(e) => pick(e.clientX)}
        onPointerDown={(e) => pick(e.clientX)}
        onPointerLeave={() => setHover(null)}
        role="img"
        aria-label="CPU temperature over time"
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#1a2a40" strokeWidth="1" />
            <text x={pad.l - 6} y={y(v) + 3} fill="#5a7a9a" fontSize="9" textAnchor="end">
              {v}°
            </text>
          </g>
        ))}
        {[TEMP_WARM, TEMP_HOT].map((v) => (
          <g key={`g${v}`}>
            <line
              x1={pad.l}
              x2={W - pad.r}
              y1={y(v)}
              y2={y(v)}
              stroke="#8a9ab0"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <text x={W - pad.r} y={y(v) - 3} fill="#8a9ab0" fontSize="8" textAnchor="end">
              {v === TEMP_HOT ? "slows down" : "warm"}
            </text>
          </g>
        ))}
        <path d={path} fill="none" stroke="#4a9fe8" strokeWidth="2" strokeLinejoin="round" />
        <text x={pad.l} y={H - 5} fill="#5a7a9a" fontSize="9">
          {formatTime(t0, withDay)}
        </text>
        <text x={W - pad.r} y={H - 5} fill="#5a7a9a" fontSize="9" textAnchor="end">
          {formatTime(t1, withDay)}
        </text>
        {hover && (
          <g>
            <line
              x1={x(hover.t)}
              x2={x(hover.t)}
              y1={pad.t}
              y2={H - pad.b}
              stroke="#c0d0e0"
              strokeWidth="1"
            />
            <circle
              cx={x(hover.t)}
              cy={y(hover.temp)}
              r="4"
              fill="#4a9fe8"
              stroke="#0f1e30"
              strokeWidth="2"
            />
          </g>
        )}
      </svg>
      <div style={{ color: "#c0d0e0", fontSize: "0.75rem", minHeight: "1.2em", marginTop: 4 }}>
        {hover
          ? `${formatTime(hover.t, true)} · ${hover.temp}°C` +
            (hover.cpu != null ? ` · CPU ${hover.cpu}%` : "")
          : "Tap the chart to read a point."}
      </div>
    </div>
  );
}

export default function HealthSection() {
  const [hours, setHours] = React.useState(24);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["systemHealth", hours],
    queryFn: () => getSystemHealth(hours),
    refetchInterval: 15000,
  });

  const cur = data?.current ?? {};
  const history = data?.history ?? [];
  const status = tempStatus(cur.temp_c);
  const flags = cur.throttled?.flags ?? [];
  const peak = history.reduce((m, s) => (s.temp != null && s.temp > m ? s.temp : m), -Infinity);

  return (
    <>
      <div className="m-card">
        <div className="m-card-title">Right Now</div>
        {isError && (
          <div style={{ color: "#e05050", fontSize: "0.8rem", marginBottom: 8 }}>
            Couldn&apos;t load stats.
          </div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <Stat
            label="CPU Temp"
            value={cur.temp_c != null ? `${cur.temp_c}°C` : isLoading ? "…" : "—"}
            sub={<span className={`m-badge ${status.badge}`}>{status.label}</span>}
          />
          <Stat
            label="CPU Use"
            value={cur.cpu_percent != null ? `${cur.cpu_percent}%` : isLoading ? "…" : "—"}
            sub={cur.load ? `Load ${cur.load.join(" / ")}` : null}
          />
          <Stat
            label="Memory"
            value={cur.memory ? `${cur.memory.percent}%` : "—"}
            sub={cur.memory ? `${cur.memory.used_mb} / ${cur.memory.total_mb} MB` : null}
          />
          <Stat
            label="Storage"
            value={cur.disk ? `${cur.disk.percent}%` : "—"}
            sub={cur.disk ? `${cur.disk.used_gb} / ${cur.disk.total_gb} GB` : null}
          />
          <Stat label="Uptime" value={formatUptime(cur.uptime_seconds)} sub="Since last restart" />
          <Stat
            label="Power & Speed"
            value={cur.throttled ? (flags.length ? "Issue" : "Good") : "—"}
            sub={
              cur.throttled
                ? flags.length
                  ? flags.map((f) => THROTTLE_LABELS[f] ?? f).join(", ")
                  : "No slowdowns"
                : null
            }
          />
        </div>
      </div>

      <div className="m-card">
        <div className="m-card-title">CPU Temp History</div>
        <div className="m-btn-row" style={{ marginBottom: 10 }}>
          {RANGES.map((r) => (
            <button
              key={r.hours}
              className={`m-btn ${hours === r.hours ? "m-btn-active" : "m-btn-neutral"}`}
              style={{ height: 36, fontSize: "0.8rem" }}
              onClick={() => setHours(r.hours)}
            >
              {r.label}
            </button>
          ))}
        </div>
        <TempChart samples={history} withDay={hours > 24} />
        {history.length > 0 && Number.isFinite(peak) && (
          <div className="m-status-row" style={{ marginTop: 6 }}>
            <span className="m-label">Hottest</span>
            <span className={`m-badge ${tempStatus(peak).badge}`}>
              {peak}°C · {tempStatus(peak).label}
            </span>
          </div>
        )}
        <div className="m-form-desc" style={{ marginTop: 6 }}>
          Saved every 10 minutes, kept for 7 days. Under 70°C is fine. The Pi slows itself down at
          80°C.
        </div>
      </div>
    </>
  );
}
