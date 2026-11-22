import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  getWeatherData,
  getWeatherSettings,
  lockWeatherView,
  showWeatherView,
} from "../../services/API";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { useNotify } from "../../hooks/useNotify";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";
import SkyCard from "./SkyCard";

const ICON_MAP = {
  0: "☀️",
  1: "🌤️",
  2: "⛅",
  3: "☁️",
  45: "🌫️",
  48: "🌫️",
  51: "🌦️",
  53: "🌦️",
  55: "🌧️",
  61: "🌧️",
  63: "🌧️",
  65: "🌧️",
  71: "❄️",
  73: "❄️",
  75: "❄️",
  77: "❄️",
  80: "🌧️",
  81: "🌧️",
  82: "🌧️",
  85: "❄️",
  86: "❄️",
  95: "⛈️",
  96: "⛈️",
  99: "⛈️",
};

const weatherIcon = (code) => ICON_MAP[code] ?? "🌡️";

const SIGNAL_COLOR = (temp, unit) => {
  const f = unit === "°F" ? temp : (temp * 9) / 5 + 32;
  if (f >= 90) return "#ff6b35";
  if (f >= 75) return "#f0a800";
  if (f >= 55) return "#5cb85c";
  if (f >= 35) return "#5b9bd5";
  return "#a0c4ff";
};

const ICON_BTN = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: "1.2rem",
  color: "#5a7a9a",
  padding: "4px 2px",
  lineHeight: 1,
};

// Card heading with the matrix controls for that screen:
//   Show now: jump the matrix to this screen once, then keep rotating.
//   Lock: keep the matrix on this screen until unlocked, or until a display
//   is picked by hand.
function CardHeading({ title, view, canControl, lockedView, onLockChange, lockPending }) {
  const { error: notifyError } = useNotify();
  const showMut = useMutation({
    mutationFn: () => showWeatherView(view),
    onSuccess: () => setTimeout(() => showMut.reset(), 3000),
    onError: (err) => notifyError(err),
  });
  const isLocked = lockedView === view;
  const anyLocked = !!lockedView;
  const btn = { fontSize: "0.75rem", padding: "4px 10px" };
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 6,
      }}
    >
      <div className="m-card-title" style={{ margin: 0 }}>
        {title}
      </div>
      {canControl && (
        <div style={{ display: "flex", gap: 6 }}>
          {!anyLocked && (
            <button
              className="m-btn m-btn-neutral"
              style={btn}
              disabled={showMut.isPending || showMut.isSuccess}
              onClick={() => showMut.mutate()}
              title="Jump the display to this screen now"
            >
              {showMut.isPending ? "…" : showMut.isSuccess ? "Sent ✓" : "Show now"}
            </button>
          )}
          <button
            className={`m-btn ${isLocked ? "m-btn-active" : "m-btn-neutral"}`}
            style={btn}
            disabled={lockPending}
            onClick={() => onLockChange(isLocked ? "" : view)}
            title={isLocked ? "Unlock and resume the rotation" : "Keep the display on this screen"}
          >
            {isLocked ? "🔒 Locked" : "Lock"}
          </button>
        </div>
      )}
    </div>
  );
}

function EmptyCard({ text }) {
  return (
    <div className="m-card" style={{ textAlign: "center", color: "#aaa" }}>
      {text}
    </div>
  );
}

// Weather page tabs, one per matrix screen (same keys as the display's views).
// The open tab lives in the URL (?tab=sky), like the System page.
const TABS = [
  { key: "current", label: "Now" },
  { key: "hourly", label: "Hourly" },
  { key: "forecast", label: "5-Day" },
  { key: "sky", label: "Sky" },
];

function TabBar({ tab, onChange, lockedView }) {
  return (
    <div className="m-tabs" role="tablist">
      {TABS.map(({ key, label }) => (
        <button
          key={key}
          role="tab"
          aria-selected={tab === key}
          className={`m-tab ${tab === key ? "m-tab-active" : ""}`}
          onClick={() => onChange(key)}
        >
          {lockedView === key ? `🔒 ${label}` : label}
        </button>
      ))}
    </div>
  );
}

export default function Weather() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = TABS.some((t) => t.key === searchParams.get("tab"))
    ? searchParams.get("tab")
    : "current";
  const setTab = (key) => setSearchParams({ tab: key }, { replace: true });
  const { data: systemStatus } = useSystemStatus({ refetchInterval: 10000 });
  const canControl = systemStatus?.active_display === "weather";

  const qc = useQueryClient();
  const { error: notifyError } = useNotify();
  const { data: weatherSettings } = useQuery({
    queryKey: ["weatherSettings"],
    queryFn: getWeatherSettings,
  });
  const lockedView = weatherSettings?.locked_view || "";
  // Switching the display by hand clears the lock on the device, so re-read it
  // whenever the active display changes.
  const activeDisplay = systemStatus?.active_display;
  React.useEffect(() => {
    if (activeDisplay) qc.invalidateQueries({ queryKey: ["weatherSettings"] });
  }, [activeDisplay, qc]);
  const lockMut = useMutation({
    mutationFn: (view) => lockWeatherView(view),
    onSuccess: (saved) => qc.setQueryData(["weatherSettings"], saved),
    onError: (err) => notifyError(err),
  });
  const headingProps = {
    canControl,
    lockedView,
    onLockChange: (view) => lockMut.mutate(view),
    lockPending: lockMut.isPending,
  };
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["weatherData"],
    queryFn: getWeatherData,
    staleTime: 10 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
  });

  const { current = {}, hourly = [], daily = [], location = {}, sky } = data ?? {};

  const header = (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 4,
      }}
    >
      <div className="m-section-title" style={{ margin: 0 }}>
        Weather
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <SwitchDisplayButton mode="weather" />
        <button
          style={ICON_BTN}
          aria-label="Weather settings"
          onClick={() => navigate("/weather/settings")}
        >
          ⚙️
        </button>
      </div>
    </div>
  );

  const subtitle = (
    <div className="m-section-sub">{location.city_label || "Current conditions & forecast"}</div>
  );

  if (isLoading) {
    return (
      <div>
        {header}
        {subtitle}
        <div className="m-card" style={{ textAlign: "center", color: "#aaa" }}>
          Loading weather…
        </div>
      </div>
    );
  }

  if (error || data?.error) {
    return (
      <div>
        {header}
        {subtitle}
        <div className="m-card" style={{ borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontWeight: 600, marginBottom: 4 }}>
            Could not load weather
          </div>
          <div style={{ color: "#aaa", fontSize: "0.85rem" }}>{data?.error ?? error?.message}</div>
          <button className="m-btn m-btn-neutral" style={{ marginTop: 12 }} onClick={refetch}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const tempColor = SIGNAL_COLOR(current.temperature, current.unit_symbol);

  return (
    <div>
      {header}
      {subtitle}

      <TabBar tab={tab} onChange={setTab} lockedView={lockedView} />

      {/* ── Current ──────────────────────────────────────────────── */}
      {tab === "current" && (
        <div className="m-card">
          <CardHeading title="Now" view="current" {...headingProps} />
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div style={{ fontSize: "3.5rem", lineHeight: 1 }}>
              {weatherIcon(current.weather_code)}
            </div>
            <div>
              <div style={{ fontSize: "2.2rem", fontWeight: 700, color: tempColor, lineHeight: 1 }}>
                {current.temperature}
                {current.unit_symbol}
              </div>
              <div style={{ color: "#aaa", fontSize: "0.85rem" }}>{current.weather_desc}</div>
              <div style={{ color: "#aaa", fontSize: "0.8rem", marginTop: 2 }}>
                Feels like {current.feels_like}
                {current.unit_symbol}
                {" · "}
                Wind {current.wind_speed} {current.wind_unit}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Hourly ───────────────────────────────────────────────── */}
      {tab === "hourly" &&
        (hourly.length > 0 ? (
          <div className="m-card">
            <CardHeading title="Next 6 Hours" view="hourly" {...headingProps} />
            <div style={{ display: "flex", justifyContent: "space-between", gap: 4 }}>
              {hourly.map((h, i) => (
                <div key={i} style={{ flex: 1, textAlign: "center" }}>
                  <div
                    style={{
                      color: i === 0 ? "#fff" : "#aaa",
                      fontSize: "0.75rem",
                      marginBottom: 2,
                    }}
                  >
                    {h.time_label}
                  </div>
                  <div style={{ fontSize: "1.2rem" }}>{weatherIcon(h.weather_code)}</div>
                  <div
                    style={{
                      fontSize: "0.8rem",
                      fontWeight: i === 0 ? 700 : 400,
                      color: SIGNAL_COLOR(h.temperature, current.unit_symbol),
                    }}
                  >
                    {h.temperature}°
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyCard text="No hourly forecast yet." />
        ))}

      {/* ── 5-Day ────────────────────────────────────────────────── */}
      {tab === "forecast" &&
        (daily.length > 0 ? (
          <div className="m-card">
            <CardHeading title="5-Day Forecast" view="forecast" {...headingProps} />
            {daily.map((d, i) => (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr 1fr",
                  alignItems: "center",
                  padding: "5px 0",
                  borderBottom: i < daily.length - 1 ? "1px solid #1a2a40" : "none",
                }}
              >
                <span style={{ color: "#aaa", fontSize: "0.85rem", fontWeight: 600 }}>
                  {d.day_label}
                </span>
                <span style={{ fontSize: "1.2rem", textAlign: "center" }}>
                  {weatherIcon(d.weather_code)}
                </span>
                <span
                  style={{
                    color: SIGNAL_COLOR(d.temp_max, current.unit_symbol),
                    fontWeight: 700,
                    fontSize: "0.9rem",
                    textAlign: "center",
                  }}
                >
                  {d.temp_max}°
                </span>
                <span style={{ color: "#7090b0", fontSize: "0.9rem", textAlign: "right" }}>
                  {d.temp_min}°
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyCard text="No daily forecast yet." />
        ))}

      {/* ── Sky (sun by day, moon by night) ──────────────────────── */}
      {tab === "sky" &&
        (sky?.sunrise?.length > 0 ? (
          <div className="m-card">
            <CardHeading title="Sky" view="sky" {...headingProps} />
            <SkyCard
              sky={sky}
              weatherCode={current.weather_code}
              weatherDesc={current.weather_desc}
            />
          </div>
        ) : (
          <EmptyCard text="Sunrise and sunset aren't available for this location." />
        ))}

      <div style={{ textAlign: "right", color: "#555", fontSize: "0.75rem", marginTop: 4 }}>
        Updated {data.last_updated?.slice(11, 16)}
        {" · "}
        <button
          style={{
            background: "none",
            border: "none",
            color: "#5b9bd5",
            cursor: "pointer",
            fontSize: "0.75rem",
          }}
          onClick={refetch}
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
