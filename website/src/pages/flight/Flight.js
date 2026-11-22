import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getFlightRoute, getNearbyFlights } from "../../services/API";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";
import FlightMap, { PLANE_COLORS } from "../../components/flight/FlightMap";
import {
  airlineLogo,
  detailRows,
  planeKey,
  planeName,
  planeSubtitle,
  routeCodes,
  summaryRows,
  trackerUrl,
} from "../../components/flight/planeInfo";

const ICON_BTN = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: "1.2rem",
  color: "#5a7a9a",
  padding: "4px 2px",
  lineHeight: 1,
};

function spotText(location) {
  if (!location || location.latitude == null) return "";
  return location.label || `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`;
}

// Hidden when the airline has no logo (the device answers 404).
function AirlineLogo({ plane, size }) {
  const [failed, setFailed] = useState(false);
  const src = airlineLogo(plane);
  if (!src || failed) return null;
  return (
    <img
      src={src}
      width={size}
      height={size}
      alt=""
      style={{ borderRadius: 6, flex: "none" }}
      onError={() => setFailed(true)}
    />
  );
}

function Rows({ rows }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "2px 12px",
        fontSize: "0.85rem",
      }}
    >
      {rows.map(([k, v]) => (
        <React.Fragment key={k}>
          <span style={{ color: "#5a7a9a" }}>{k}</span>
          <span style={{ color: "#ddd" }}>{v}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

// Same layout as the panel: logo, flight number, airline, from/to.
// "More info" opens the rest.
function ClosestCard({ plane, units }) {
  const [more, setMore] = useState(false);
  const url = trackerUrl(plane);
  return (
    <div className="m-card" style={{ borderLeft: `3px solid ${PLANE_COLORS.closest}` }}>
      <div className="m-card-title">Closest plane · on the display</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <AirlineLogo key={airlineLogo(plane) || "none"} plane={plane} size={40} />
        <div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#fff", lineHeight: 1.1 }}>
            {planeName(plane)}
          </div>
          {planeSubtitle(plane) && (
            <div style={{ color: "#4fd1d1", fontSize: "0.85rem" }}>{planeSubtitle(plane)}</div>
          )}
        </div>
      </div>
      <Rows rows={summaryRows(plane, units)} />
      <button
        className="m-btn m-btn-neutral"
        style={{ fontSize: "0.75rem", padding: "3px 10px", marginTop: 8 }}
        onClick={() => setMore((m) => !m)}
      >
        {more ? "Less info" : "More info"}
      </button>
      {more && (
        <div style={{ marginTop: 8 }}>
          <Rows rows={detailRows(plane, units)} />
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-block",
                marginTop: 8,
                color: "#5b9bd5",
                fontSize: "0.8rem",
              }}
            >
              Track on adsb.lol ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function PlaneList({ aircraft, units, closestKey, selected, onSelect }) {
  return (
    <div className="m-card">
      <div className="m-card-title">All planes, nearest first</div>
      {aircraft.map((p, i) => {
        const key = planeKey(p);
        const isSel = key === selected;
        return (
          <button
            key={key}
            onClick={() => onSelect(key)}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto",
              gap: 10,
              width: "100%",
              textAlign: "left",
              background: isSel ? "#1a2a40" : "none",
              border: "none",
              borderBottom: i < aircraft.length - 1 ? "1px solid #1a2a40" : "none",
              padding: "6px 4px",
              cursor: "pointer",
              color: "#ddd",
              fontSize: "0.85rem",
            }}
          >
            <span>
              <span
                style={{
                  color: key === closestKey ? PLANE_COLORS.closest : "#fff",
                  fontWeight: 600,
                }}
              >
                {planeName(p)}
              </span>
              {p.airline?.short_name && (
                <span style={{ color: "#8aa0b8", marginLeft: 6 }}>{p.airline.short_name}</span>
              )}
              {routeCodes(p.route) && (
                <span style={{ color: "#4fd1d1", marginLeft: 6 }}>{routeCodes(p.route)}</span>
              )}
              {!p.airline && p.type && (
                <span style={{ color: "#5a7a9a", marginLeft: 6 }}>{p.type}</span>
              )}
            </span>
            <span style={{ color: "#f0c040", minWidth: 70, textAlign: "right" }}>
              {p.distance} {units} {p.direction}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default function Flight() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState(null);
  const { data: selectedRoute } = useQuery({
    queryKey: ["flightRoute", selected],
    queryFn: () => getFlightRoute(selected),
    enabled: !!selected,
    // Routes are cached on the device for a day; no need to ask again here.
    staleTime: Infinity,
  });
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["flightNearby"],
    queryFn: getNearbyFlights,
    // The API refreshes from the feeds once a minute; match it.
    refetchInterval: 60 * 1000,
    staleTime: 30 * 1000,
  });

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
        Flights
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <SwitchDisplayButton mode="flight" />
        <button
          style={ICON_BTN}
          aria-label="Flight settings"
          onClick={() => navigate("/flight/settings")}
        >
          ⚙
        </button>
      </div>
    </div>
  );

  const subtitle = (
    <div className="m-section-sub">
      {spotText(data?.location) || "Planes in the sky around you"}
    </div>
  );

  if (isLoading) {
    return (
      <div>
        {header}
        {subtitle}
        <div className="m-card" style={{ textAlign: "center", color: "#aaa" }}>
          Looking for planes…
        </div>
      </div>
    );
  }

  if (data && !data.configured) {
    return (
      <div>
        {header}
        {subtitle}
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 6 }}>✈</div>
          <div style={{ color: "#ddd", marginBottom: 12 }}>
            Set your location to see the planes above you.
          </div>
          <button className="m-btn m-btn-primary" onClick={() => navigate("/flight/settings")}>
            Set location
          </button>
        </div>
      </div>
    );
  }

  if (error || !data?.aircraft) {
    return (
      <div>
        {header}
        {subtitle}
        <div className="m-card" style={{ borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontWeight: 600, marginBottom: 4 }}>
            Could not load flights
          </div>
          <div style={{ color: "#aaa", fontSize: "0.85rem" }}>
            {data?.error ?? error?.message ?? "Try again in a minute."}
          </div>
          <button className="m-btn m-btn-neutral" style={{ marginTop: 12 }} onClick={refetch}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { closest, units, radius, location } = data;
  // A tapped plane's route, looked up on demand, fills in its popup and row.
  const aircraft = selectedRoute?.route
    ? data.aircraft.map((p) =>
        planeKey(p) === selected && !p.route ? { ...p, route: selectedRoute.route } : p
      )
    : data.aircraft;
  const closestKey = closest ? planeKey(closest) : null;
  const updated = data.fetched_at
    ? new Date(data.fetched_at * 1000).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      })
    : "";

  return (
    <div>
      {header}
      {subtitle}

      <div className="m-card">
        <div
          className="m-card-title"
          style={{ display: "flex", justifyContent: "space-between", gap: 8 }}
        >
          <span>
            {aircraft.length} {data.airlines_only ? "airline " : ""}
            {aircraft.length === 1 ? "plane" : "planes"} within {radius} {units}
            {data.hidden > 0 && (
              <span style={{ fontWeight: 400, color: "#5a7a9a" }}>
                {" "}
                · {data.hidden} others hidden
              </span>
            )}
          </span>
          <span style={{ fontWeight: 400, color: "#5a7a9a", fontSize: "0.75rem" }}>
            <span style={{ color: PLANE_COLORS.closest }}>✈</span> closest ·{" "}
            <span style={{ color: PLANE_COLORS.other }}>✈</span> others
          </span>
        </div>
        <FlightMap
          latitude={location.latitude}
          longitude={location.longitude}
          radius={radius}
          units={units}
          aircraft={aircraft}
          closestHex={closestKey}
          selectedHex={selected}
          onSelect={setSelected}
        />
        <div className="m-form-desc" style={{ marginTop: 6 }}>
          Tap a plane for details.
        </div>
      </div>

      {data.stale && (
        <div className="m-card" style={{ borderLeft: "3px solid #f0a800" }}>
          <div style={{ color: "#f0a800", fontSize: "0.85rem" }}>
            Flight data didn't refresh. Showing planes from {updated}.
          </div>
        </div>
      )}

      {closest ? (
        <ClosestCard plane={closest} units={units} />
      ) : (
        <div className="m-card" style={{ textAlign: "center", color: "#aaa" }}>
          No {data.airlines_only ? "airline flights" : "planes"} in the air within {radius} {units}{" "}
          right now.
        </div>
      )}

      {aircraft.length > 1 && (
        <PlaneList
          aircraft={aircraft}
          units={units}
          closestKey={closestKey}
          selected={selected}
          onSelect={setSelected}
        />
      )}

      <div style={{ textAlign: "right", color: "#555", fontSize: "0.75rem", marginTop: 4 }}>
        Updated {updated}
        {data.source && ` · via ${data.source}`}
        {" · "}
        <button
          style={{
            background: "none",
            border: "none",
            color: "#5b9bd5",
            cursor: "pointer",
            fontSize: "0.75rem",
          }}
          disabled={isFetching}
          onClick={refetch}
        >
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </div>
  );
}
