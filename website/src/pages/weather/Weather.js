import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getWeatherData } from "../../services/API";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";

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

export default function Weather() {
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["weatherData"],
    queryFn: getWeatherData,
    staleTime: 10 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
  });

  const { current = {}, hourly = [], daily = [], location = {} } = data ?? {};

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

      {/* ── Current ──────────────────────────────────────────────── */}
      <div className="m-card">
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

      {/* ── Hourly ───────────────────────────────────────────────── */}
      {hourly.length > 0 && (
        <div className="m-card">
          <div className="m-card-title">Next 6 Hours</div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 4 }}>
            {hourly.map((h, i) => (
              <div key={i} style={{ flex: 1, textAlign: "center" }}>
                <div
                  style={{ color: i === 0 ? "#fff" : "#aaa", fontSize: "0.75rem", marginBottom: 2 }}
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
      )}

      {/* ── 5-Day ────────────────────────────────────────────────── */}
      {daily.length > 0 && (
        <div className="m-card">
          <div className="m-card-title">5-Day Forecast</div>
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
      )}

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
