import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getWeatherSettings, updateWeatherSettings, geocodeLocation } from "../../services/API";

function useDebounce(value, ms) {
  const [dv, setDv] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDv(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return dv;
}

export default function WeatherSettings() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["weatherSettings"],
    queryFn: getWeatherSettings,
  });

  const updateMut = useMutation({
    mutationFn: updateWeatherSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["weatherSettings"] });
      qc.invalidateQueries({ queryKey: ["weatherData"] });
    },
  });

  // ── Location search ────────────────────────────────────────────────────
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saved, setSaved] = useState(false);

  const debouncedQuery = useDebounce(query, 500);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    geocodeLocation(debouncedQuery)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setSearching(false));
  }, [debouncedQuery]);

  function selectLocation(loc) {
    updateMut.mutate({
      latitude: loc.latitude,
      longitude: loc.longitude,
      city_label: loc.short_name,
      use_ip_location: false,
    });
    setResults([]);
    setQuery("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  function toggleIPLocation(use) {
    updateMut.mutate({ use_ip_location: use });
    if (use) {
      setQuery("");
      setResults([]);
    }
  }

  function setUnits(units) {
    updateMut.mutate({ units });
  }

  const [cycleSecs, setCycleSecs] = useState(null);
  useEffect(() => {
    if (settings?.cycle_duration != null) setCycleSecs(settings.cycle_duration);
  }, [settings?.cycle_duration]);

  function saveCycleDuration() {
    const val = parseInt(cycleSecs, 10);
    if (!isNaN(val) && val >= 10 && val <= 3600) updateMut.mutate({ cycle_duration: val });
  }

  if (isLoading) {
    return (
      <div>
        <div className="m-section-title">Weather Settings</div>
        <div className="m-card" style={{ color: "#aaa" }}>
          Loading…
        </div>
      </div>
    );
  }

  const s = settings ?? {};
  const useIP = s.use_ip_location ?? true;

  return (
    <div>
      <div
        className="m-section-title"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        Weather Settings
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.8rem", padding: "2px 10px" }}
          onClick={() => navigate("/weather")}
        >
          ← Back
        </button>
      </div>

      {/* ── Cycle duration ─────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Screen Cycle Time</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <input
            type="number"
            className="m-input"
            min={10}
            max={3600}
            value={cycleSecs ?? ""}
            onChange={(e) => setCycleSecs(e.target.value)}
            onBlur={saveCycleDuration}
            style={{ width: 80 }}
          />
          <span style={{ color: "#5a7a9a", fontSize: "0.85rem" }}>seconds per screen</span>
        </div>
        <div className="m-form-desc" style={{ marginTop: 8 }}>
          How long each screen (current, hourly, forecast) stays visible on the display. 10–3600 s.
        </div>
      </div>

      {/* ── Units ──────────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Units</div>
        <div className="m-btn-row">
          <button
            className={`m-btn ${s.units === "fahrenheit" ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => setUnits("fahrenheit")}
          >
            °F (Fahrenheit)
          </button>
          <button
            className={`m-btn ${s.units === "celsius" ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => setUnits("celsius")}
          >
            °C (Celsius)
          </button>
        </div>
      </div>

      {/* ── Location ───────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Location</div>

        <div className="m-btn-row" style={{ marginBottom: "1rem" }}>
          <button
            className={`m-btn ${useIP ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => toggleIPLocation(true)}
          >
            Auto-detect
          </button>
          <button
            className={`m-btn ${!useIP ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => toggleIPLocation(false)}
          >
            Manual
          </button>
        </div>

        {useIP ? (
          <div style={{ color: "#aaa", fontSize: "0.85rem" }}>
            Location is detected automatically from your IP address.
            {s.city_label && <span style={{ color: "#5cb85c" }}> Currently: {s.city_label}</span>}
          </div>
        ) : (
          <>
            {s.city_label && (
              <div style={{ color: "#5cb85c", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                ✓ {s.city_label}
                {s.latitude != null && (
                  <span style={{ color: "#555", marginLeft: 6 }}>
                    ({s.latitude?.toFixed(2)}, {s.longitude?.toFixed(2)})
                  </span>
                )}
              </div>
            )}

            <label
              style={{
                display: "block",
                color: "#aaa",
                fontSize: "0.85rem",
                marginBottom: "0.3rem",
              }}
            >
              Search for a city
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. New York, London, Tokyo…"
              style={{
                width: "100%",
                padding: "0.5rem 0.6rem",
                background: "#1e1e1e",
                border: "1px solid #444",
                borderRadius: 6,
                color: "#fff",
                fontSize: "1rem",
                boxSizing: "border-box",
              }}
            />

            {searching && (
              <div style={{ color: "#aaa", fontSize: "0.8rem", marginTop: 4 }}>Searching…</div>
            )}

            {results.length > 0 && (
              <div style={{ marginTop: "0.5rem" }}>
                {results.map((r, i) => (
                  <button
                    key={i}
                    className="m-btn m-btn-neutral"
                    style={{
                      width: "100%",
                      textAlign: "left",
                      marginBottom: 4,
                      padding: "0.4rem 0.6rem",
                    }}
                    onClick={() => selectLocation(r)}
                  >
                    <div style={{ fontSize: "0.9rem" }}>{r.short_name}</div>
                    <div style={{ color: "#777", fontSize: "0.75rem" }}>{r.display_name}</div>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {saved && (
        <div className="m-card" style={{ background: "#1a2a1a", borderLeft: "3px solid #5cb85c" }}>
          <div style={{ color: "#5cb85c", fontSize: "0.9rem" }}>✓ Location saved</div>
        </div>
      )}

      {updateMut.isError && (
        <div className="m-card" style={{ borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontSize: "0.85rem" }}>
            {updateMut.error?.message ?? "Failed to save settings"}
          </div>
        </div>
      )}
    </div>
  );
}
