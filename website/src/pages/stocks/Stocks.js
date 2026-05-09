import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useStocksSettings } from "../../hooks/useStocksSettings";
import { useStockChart } from "../../hooks/useStockChart";
import { useStockInfo } from "../../hooks/useStockInfo";
import { useStockNow } from "../../hooks/useStockNow";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";

/* ── Sparkline ─────────────────────────────────────────────────── */
function formatTs(ts, intraday) {
  const d = new Date(ts);
  if (intraday)
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function Sparkline({ closes, timestamps = [], cycleKey, direction, height }) {
  const ref = React.useRef(null);
  const [width, setWidth] = React.useState(0);

  React.useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const intraday = cycleKey === "intraday";
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const pad = 3;

  const pts =
    width > 0
      ? closes.map((c, i) => {
          const x = (i / (closes.length - 1)) * width;
          const y = height - pad - ((c - min) / range) * (height - pad * 2);
          return [x, y];
        })
      : [];

  const linePts = pts.map(([x, y]) => `${x},${y}`).join(" ");
  const fillPts = pts.length
    ? [`0,${height}`, ...pts.map(([x, y]) => `${x},${y}`), `${width},${height}`].join(" ")
    : "";

  const color = direction === "up" ? "#1db954" : "#e05050";
  const gradId = `sg-${direction}`;
  const midIdx = Math.floor((timestamps.length - 1) / 2);
  const labels =
    timestamps.length >= 2
      ? [
          { text: formatTs(timestamps[0], intraday), align: "left" },
          { text: formatTs(timestamps[midIdx], intraday), align: "center" },
          { text: formatTs(timestamps[timestamps.length - 1], intraday), align: "right" },
        ]
      : [];

  return (
    <div ref={ref} style={{ width: "100%" }}>
      {width > 0 && closes.length >= 2 && (
        <svg width={width} height={height} style={{ display: "block" }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.25" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <polyline points={fillPts} fill={`url(#${gradId})`} stroke="none" />
          <polyline
            points={linePts}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      )}
      {labels.length > 0 && (
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
          {labels.map(({ text, align }) => (
            <span
              key={align}
              style={{ fontSize: "0.7rem", color: "#5a7a9a", textAlign: align, flex: 1 }}
            >
              {text}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Stock card ────────────────────────────────────────────────── */
function StockCard({ symbol, cycleKey, isOnDisplay }) {
  const { data: chart, isLoading, isError } = useStockChart(symbol, cycleKey);
  const { data: info } = useStockInfo(symbol);

  const name = info?.name || symbol;
  const price = chart?.current_price;
  const changePct = chart?.change_pct;
  const direction = chart?.direction ?? "up";
  const closes = chart?.closes ?? [];
  const timestamps = chart?.timestamps ?? [];
  const isUp = direction === "up";
  const changeColor = isUp ? "#1db954" : "#e05050";

  return (
    <div
      style={{
        background: isOnDisplay ? "#0a2010" : "#0d1922",
        border: `1px solid ${isOnDisplay ? "#1db954" : "#1e3048"}`,
        borderRadius: 12,
        padding: "14px 16px",
        marginBottom: 12,
        boxShadow: isOnDisplay ? "0 0 0 2px #1db95440" : "none",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 8,
        }}
      >
        <div>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#e8f0f8", lineHeight: 1.2 }}>
            {name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
            <span style={{ fontSize: "0.8rem", color: "#5a7a9a" }}>{symbol}</span>
            {isOnDisplay && (
              <span
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 700,
                  color: "#1db954",
                  background: "#0d2e1a",
                  borderRadius: 4,
                  padding: "1px 5px",
                  letterSpacing: "0.03em",
                }}
              >
                ON DISPLAY
              </span>
            )}
          </div>
        </div>
        {price != null && (
          <div style={{ textAlign: "right" }}>
            <div
              style={{
                fontWeight: 700,
                fontSize: "1.1rem",
                color: "#e8f0f8",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              ${price.toFixed(2)}
            </div>
            {changePct != null && (
              <div
                style={{ fontSize: "0.8rem", color: changeColor, fontWeight: 600, marginTop: 2 }}
              >
                {isUp ? "▲" : "▼"} {Math.abs(changePct).toFixed(2)}%
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ margin: "8px 0" }}>
        {isLoading ? (
          <div style={{ padding: "20px 0", display: "flex", justifyContent: "center" }}>
            <div className="m-spinner" />
          </div>
        ) : isError ? (
          <div style={{ color: "#e05050", fontSize: "0.8rem" }}>Failed to load data</div>
        ) : !closes.length ? (
          <div style={{ color: "#5a7a9a", fontSize: "0.8rem" }}>No data available</div>
        ) : (
          <Sparkline
            closes={closes}
            timestamps={timestamps}
            cycleKey={cycleKey}
            direction={direction}
            height={80}
          />
        )}
      </div>

      <a
        href={`https://finance.yahoo.com/quote/${symbol}`}
        target="_blank"
        rel="noopener noreferrer"
        style={{ fontSize: "0.75rem", color: "#5a7a9a", textDecoration: "none" }}
      >
        View on Yahoo Finance →
      </a>
    </div>
  );
}

/* ── Cycle selector ────────────────────────────────────────────── */
function CycleSelector({ cycles, selected, onSelect, displayCycle }) {
  const enabled = cycles.filter((c) => c.enabled);
  if (!enabled.length) return null;

  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
      {enabled.map((c) => (
        <button
          key={c.key}
          onClick={() => onSelect(c.key)}
          style={{
            padding: "6px 12px",
            borderRadius: 20,
            fontSize: "0.8rem",
            cursor: "pointer",
            border: "1px solid",
            borderColor: selected === c.key ? "#3b82f6" : "#2a3a4a",
            background: selected === c.key ? "#1a3a5a" : "#0d1922",
            color: selected === c.key ? "#7eb8f7" : "#8a9ab0",
            fontWeight: selected === c.key ? 600 : 400,
          }}
        >
          {c.label}
          {c.key === displayCycle && (
            <span
              style={{
                display: "inline-block",
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "#1db954",
                marginLeft: 5,
                verticalAlign: "middle",
              }}
              title="On display"
            />
          )}
        </button>
      ))}
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function Stocks() {
  const navigate = useNavigate();
  const { data: settings, isLoading } = useStocksSettings();
  const { data: now } = useStockNow();
  const { data: systemStatus } = useSystemStatus({ refetchInterval: 10000 });
  const stocksActive = systemStatus?.active_display === "stocks";

  const { stock_abbrs = [], stock_cycles = [] } = settings || {};
  const enabledCycles = stock_cycles.filter((c) => c.enabled);
  const [selectedCycle, setSelectedCycle] = React.useState(null);
  const hasUserSelected = React.useRef(false);

  React.useEffect(() => {
    if (hasUserSelected.current || !enabledCycles.length) return;
    const preferred =
      now?.cycle_key && enabledCycles.some((c) => c.key === now.cycle_key)
        ? now.cycle_key
        : enabledCycles[0].key;
    setSelectedCycle(preferred);
  }, [stock_cycles, now?.cycle_key]);

  const handleCycleSelect = (key) => {
    hasUserSelected.current = true;
    setSelectedCycle(key);
  };

  if (isLoading) return <div style={{ padding: 20, color: "#5a7a9a" }}>Loading…</div>;

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 14,
        }}
      >
        <div className="m-section-title" style={{ margin: 0 }}>
          Stocks
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <SwitchDisplayButton mode="stocks" />
          <button
            onClick={() => navigate("/stocks/settings")}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "1.2rem",
              color: "#5a7a9a",
            }}
            aria-label="Settings"
          >
            ⚙️
          </button>
        </div>
      </div>

      <CycleSelector
        cycles={stock_cycles}
        selected={selectedCycle}
        onSelect={handleCycleSelect}
        displayCycle={stocksActive ? now?.cycle_key : null}
      />

      {stock_abbrs.length === 0 ? (
        <div className="m-card" style={{ textAlign: "center", color: "#5a7a9a", padding: 24 }}>
          No stocks in watchlist.{" "}
          <button
            onClick={() => navigate("/stocks/settings")}
            style={{
              background: "none",
              border: "none",
              color: "#4a9fe8",
              cursor: "pointer",
              fontSize: "inherit",
              padding: 0,
              textDecoration: "underline",
            }}
          >
            Add some in settings.
          </button>
        </div>
      ) : (
        stock_abbrs.map((symbol) => (
          <StockCard
            key={`${symbol}-${selectedCycle}`}
            symbol={symbol}
            cycleKey={selectedCycle}
            isOnDisplay={stocksActive && now?.symbol === symbol}
          />
        ))
      )}
    </div>
  );
}
