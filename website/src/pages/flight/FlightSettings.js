import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useDebounce } from "../../hooks/useDebounce";
import {
  geocodeLocation,
  getFlightSettings,
  getGeolocation,
  updateFlightSettings,
} from "../../services/API";
import LocationPickerMap from "../../components/flight/LocationPickerMap";

const RADIUS_MIN = 1;
const RADIUS_MAX = 150;
const RADIUS_PRESETS = { mi: [5, 10, 25, 50, 100], km: [10, 25, 50, 100, 150] };
const KM_PER_MI = 1.609344;

const METHODS = [
  { key: "address", label: "Address" },
  { key: "coords", label: "Lat / Lon" },
  { key: "map", label: "Map" },
];

const INPUT = {
  width: "100%",
  padding: "0.5rem 0.6rem",
  background: "#1e1e1e",
  border: "1px solid #444",
  borderRadius: 6,
  color: "#fff",
  fontSize: "1rem",
  boxSizing: "border-box",
};

const LABEL = { display: "block", color: "#aaa", fontSize: "0.85rem", marginBottom: "0.3rem" };

// "1600 Pennsylvania Avenue NW, Washington, District of Columbia, 20500, United
// States" -> "1600 Pennsylvania Avenue NW, Washington"
const shortLabel = (displayName) => displayName.split(",").slice(0, 2).join(",").trim();

function parseCoord(text, low, high) {
  const v = Number(String(text).trim());
  return String(text).trim() !== "" && Number.isFinite(v) && v >= low && v <= high ? v : null;
}

function AddressSearch({ onSave }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const debounced = useDebounce(query, 600);

  useEffect(() => {
    if (debounced.trim().length < 3) {
      setResults([]);
      setSearchError(null);
      return;
    }
    let live = true;
    setSearching(true);
    geocodeLocation(debounced)
      .then((r) => {
        if (!live) return;
        setResults(r);
        setSearchError(r.length ? null : "No matches. Try adding the city.");
      })
      .catch(() => live && setSearchError("Search isn't working right now."))
      .finally(() => live && setSearching(false));
    return () => {
      live = false;
    };
  }, [debounced]);

  return (
    <>
      <label style={LABEL}>Address, place or city</label>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g. 400 Broad St, Seattle"
        style={INPUT}
      />
      {searching && (
        <div style={{ color: "#aaa", fontSize: "0.8rem", marginTop: 4 }}>Searching…</div>
      )}
      {searchError && !searching && (
        <div style={{ color: "#d9534f", fontSize: "0.8rem", marginTop: 4 }}>{searchError}</div>
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
              onClick={() => {
                onSave({
                  latitude: r.latitude,
                  longitude: r.longitude,
                  location_label: shortLabel(r.display_name),
                });
                setQuery("");
                setResults([]);
              }}
            >
              <div style={{ fontSize: "0.9rem" }}>{shortLabel(r.display_name)}</div>
              <div style={{ color: "#777", fontSize: "0.75rem" }}>{r.display_name}</div>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function CoordsForm({ settings, onSave }) {
  const [lat, setLat] = useState(settings.latitude ?? "");
  const [lon, setLon] = useState(settings.longitude ?? "");
  const latV = parseCoord(lat, -90, 90);
  const lonV = parseCoord(lon, -180, 180);
  const touched = String(lat).trim() !== "" || String(lon).trim() !== "";
  return (
    <>
      <div style={{ display: "flex", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <label style={LABEL}>Latitude (-90 to 90)</label>
          <input
            type="text"
            inputMode="decimal"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            placeholder="47.6062"
            style={INPUT}
          />
        </div>
        <div style={{ flex: 1 }}>
          <label style={LABEL}>Longitude (-180 to 180)</label>
          <input
            type="text"
            inputMode="decimal"
            value={lon}
            onChange={(e) => setLon(e.target.value)}
            placeholder="-122.3321"
            style={INPUT}
          />
        </div>
      </div>
      {touched && (latV === null || lonV === null) && (
        <div style={{ color: "#d9534f", fontSize: "0.8rem", marginTop: 4 }}>
          Enter a latitude from -90 to 90 and a longitude from -180 to 180.
        </div>
      )}
      <button
        className="m-btn m-btn-primary"
        style={{ marginTop: 10 }}
        disabled={latV === null || lonV === null}
        onClick={() => onSave({ latitude: latV, longitude: lonV, location_label: "" })}
      >
        Save spot
      </button>
    </>
  );
}

function MapPicker({ settings, onSave }) {
  const [picked, setPicked] = useState(null);
  return (
    <>
      <div className="m-form-desc" style={{ marginBottom: 8 }}>
        Tap the map to drop a pin on your spot, then save it.
      </div>
      <LocationPickerMap
        latitude={settings.latitude}
        longitude={settings.longitude}
        picked={picked}
        onPick={setPicked}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
        <button
          className="m-btn m-btn-primary"
          disabled={!picked}
          onClick={() => {
            onSave({ ...picked, location_label: "" });
            setPicked(null);
          }}
        >
          Save this spot
        </button>
        {picked && (
          <span style={{ color: "#aaa", fontSize: "0.8rem" }}>
            {picked.latitude.toFixed(4)}, {picked.longitude.toFixed(4)}
          </span>
        )}
      </div>
    </>
  );
}

export default function FlightSettings() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [method, setMethod] = useState("address");
  const [saved, setSaved] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["flightSettings"],
    queryFn: getFlightSettings,
  });

  const updateMut = useMutation({
    mutationFn: updateFlightSettings,
    onSuccess: (s) => {
      qc.setQueryData(["flightSettings"], s);
      qc.invalidateQueries({ queryKey: ["flightNearby"] });
    },
  });

  function saveSpot(spot) {
    updateMut.mutate(spot, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2500);
      },
    });
  }

  const [detecting, setDetecting] = useState(false);
  const [detectError, setDetectError] = useState(null);
  async function detectLocation() {
    setDetecting(true);
    setDetectError(null);
    try {
      const loc = await getGeolocation();
      if (loc?.latitude != null && loc?.longitude != null) {
        saveSpot({
          latitude: loc.latitude,
          longitude: loc.longitude,
          location_label: loc.city_label || "",
        });
      } else {
        setDetectError("Couldn't detect a location from your network");
      }
    } catch {
      setDetectError("Couldn't detect a location from your network");
    } finally {
      setDetecting(false);
    }
  }

  const [radiusText, setRadiusText] = useState("");
  useEffect(() => {
    if (settings?.radius != null) setRadiusText(String(settings.radius));
  }, [settings?.radius]);

  function saveRadius(value) {
    const r = parseInt(value, 10);
    if (Number.isFinite(r) && r >= RADIUS_MIN && r <= RADIUS_MAX && r !== settings.radius) {
      updateMut.mutate({ radius: r });
    } else {
      setRadiusText(String(settings.radius));
    }
  }

  function setUnits(units) {
    if (units === settings.units) return;
    // Keep the same distance on the ground, in the new unit.
    const converted = units === "km" ? settings.radius * KM_PER_MI : settings.radius / KM_PER_MI;
    const radius = Math.max(RADIUS_MIN, Math.min(RADIUS_MAX, Math.round(converted)));
    updateMut.mutate({ units, radius });
  }

  if (isLoading || !settings) {
    return (
      <div>
        <div className="m-section-title">Flight Settings</div>
        <div className="m-card" style={{ color: "#aaa" }}>
          Loading…
        </div>
      </div>
    );
  }

  const hasSpot = settings.latitude != null && settings.longitude != null;
  const units = settings.units;

  return (
    <div>
      <div
        className="m-section-title"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        Flight Settings
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.8rem", padding: "2px 10px" }}
          onClick={() => navigate("/flight")}
        >
          ← Back
        </button>
      </div>

      {/* ── Current spot ─────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Your Spot</div>
        {hasSpot ? (
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <div style={{ color: "#5cb85c", fontSize: "0.9rem" }}>
              ✓ {settings.location_label || "Saved spot"}
              <span style={{ color: "#555", marginLeft: 6 }}>
                ({settings.latitude.toFixed(4)}, {settings.longitude.toFixed(4)})
              </span>
            </div>
            <button
              className="m-btn m-btn-neutral"
              style={{ fontSize: "0.75rem", padding: "2px 10px" }}
              disabled={updateMut.isPending}
              onClick={() => updateMut.mutate({ clear_location: true })}
            >
              Remove
            </button>
          </div>
        ) : (
          <div style={{ color: "#aaa", fontSize: "0.85rem" }}>
            No spot set. The display shows "Update settings to view flight info" until you set one.
          </div>
        )}
      </div>

      {/* ── Set the spot ─────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">{hasSpot ? "Change Your Spot" : "Set Your Spot"}</div>

        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginBottom: "0.75rem", fontSize: "0.85rem" }}
          onClick={detectLocation}
          disabled={detecting}
        >
          {detecting ? "Detecting…" : "📍 Use my detected location"}
        </button>
        {detectError && (
          <div style={{ color: "#d9534f", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
            {detectError}
          </div>
        )}

        <div className="m-btn-row" style={{ marginBottom: "1rem" }}>
          {METHODS.map((m) => (
            <button
              key={m.key}
              className={`m-btn ${method === m.key ? "m-btn-active" : "m-btn-neutral"}`}
              onClick={() => setMethod(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>

        {method === "address" && <AddressSearch onSave={saveSpot} />}
        {method === "coords" && <CoordsForm settings={settings} onSave={saveSpot} />}
        {method === "map" && <MapPicker settings={settings} onSave={saveSpot} />}
      </div>

      {saved && (
        <div className="m-card" style={{ background: "#1a2a1a", borderLeft: "3px solid #5cb85c" }}>
          <div style={{ color: "#5cb85c", fontSize: "0.9rem" }}>✓ Spot saved</div>
        </div>
      )}

      {/* ── Radius ───────────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Search Radius</div>
        <div className="m-btn-row" style={{ marginBottom: 8 }}>
          {RADIUS_PRESETS[units].map((r) => (
            <button
              key={r}
              className={`m-btn ${settings.radius === r ? "m-btn-active" : "m-btn-neutral"}`}
              onClick={() => saveRadius(r)}
            >
              {r}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <input
            type="number"
            className="m-input"
            min={RADIUS_MIN}
            max={RADIUS_MAX}
            value={radiusText}
            onChange={(e) => setRadiusText(e.target.value)}
            onBlur={() => saveRadius(radiusText)}
            style={{ width: 80 }}
          />
          <span style={{ color: "#5a7a9a", fontSize: "0.85rem" }}>
            {units === "km" ? "kilometers" : "miles"}
          </span>
        </div>
        <div className="m-form-desc" style={{ marginTop: 8 }}>
          Planes inside this circle are shown. The display shows the closest one. {RADIUS_MIN}–
          {RADIUS_MAX}.
        </div>
      </div>

      {/* ── Which planes ─────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Which Planes</div>
        <div className="m-btn-row">
          <button
            className={`m-btn ${!settings.airlines_only ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => settings.airlines_only && updateMut.mutate({ airlines_only: false })}
          >
            All planes
          </button>
          <button
            className={`m-btn ${settings.airlines_only ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => !settings.airlines_only && updateMut.mutate({ airlines_only: true })}
          >
            Airlines only
          </button>
        </div>
        <div className="m-form-desc" style={{ marginTop: 8 }}>
          Airlines only hides private, small and most military planes, on the display and here.
        </div>
      </div>

      {/* ── Units ────────────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Distance Units</div>
        <div className="m-btn-row">
          <button
            className={`m-btn ${units === "mi" ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => setUnits("mi")}
          >
            Miles
          </button>
          <button
            className={`m-btn ${units === "km" ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => setUnits("km")}
          >
            Kilometers
          </button>
        </div>
        <div className="m-form-desc" style={{ marginTop: 8 }}>
          Altitude is always in feet and speed in knots, as pilots use.
        </div>
      </div>

      {updateMut.isError && (
        <div className="m-card" style={{ borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontSize: "0.85rem" }}>
            {updateMut.error?.response?.data?.detail ??
              updateMut.error?.message ??
              "Failed to save settings"}
          </div>
        </div>
      )}
    </div>
  );
}
