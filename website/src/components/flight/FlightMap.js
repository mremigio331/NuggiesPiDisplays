import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  airlineLogo,
  detailRows,
  planeKey,
  planeName,
  planeSubtitle,
  summaryRows,
  trackerUrl,
} from "./planeInfo";

// Planes come from public ADS-B feeds, so every string is escaped before it
// goes into popup HTML.
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

const METERS_PER = { mi: 1609.344, km: 1000 };

export const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// A plane pointing up (north); rotated by the plane's track.
const PLANE_PATH =
  "M12 2c.8 0 1.3.9 1.3 2v5.2l7.7 4.6v2l-7.7-2.3v4.6l2.2 1.7v1.6L12 20.3l-3.5 1.1v-1.6l2.2-1.7v-4.6L3 15.8v-2l7.7-4.6V4c0-1.1.5-2 1.3-2z";

// A helicopter from above, nose up: rotor blades crossing over the body,
// tail boom down to the tail rotor.
const HELI_SVG = (color, stroke) =>
  `<path d="M3 3 L21 17 M21 3 L3 17" stroke="${color}" stroke-width="2.2" stroke-linecap="round"/>` +
  `<ellipse cx="12" cy="10" rx="4" ry="5" fill="${color}" stroke="${stroke}" stroke-width="1"/>` +
  `<path d="M12 15 L12 21 M9 21 L15 21" stroke="${color}" stroke-width="2" stroke-linecap="round"/>`;

export const PLANE_COLORS = { closest: "#ffcc00", other: "#4a9fe8" };

function planeIcon(plane, isClosest, isSelected) {
  const color = isClosest ? PLANE_COLORS.closest : PLANE_COLORS.other;
  const size = isClosest || isSelected ? 30 : 22;
  const stroke = isSelected ? "#ffffff" : "#0d1626";
  const rot = Number.isFinite(plane.track) ? plane.track : 0;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
    html:
      `<svg viewBox="0 0 24 24" width="${size}" height="${size}" ` +
      `style="transform:rotate(${rot}deg);display:block">` +
      (plane.helicopter
        ? HELI_SVG(color, stroke)
        : `<path d="${PLANE_PATH}" fill="${color}" stroke="${stroke}" stroke-width="1"/>`) +
      `</svg>`,
  });
}

const tableHtml = (rows) =>
  `<table>` +
  rows
    .map(
      ([k, v]) =>
        `<tr><td style="color:#666;padding-right:8px">${esc(k)}</td><td>${esc(v)}</td></tr>`
    )
    .join("") +
  `</table>`;

// Same layout as the panel: logo, flight number, airline, from/to. The rest
// sits in a "More info" fold (a <details>, so it needs no script).
function popupHtml(p, units, isClosest) {
  const url = trackerUrl(p);
  const logo = airlineLogo(p);
  const sub = planeSubtitle(p);
  return (
    `<div style="min-width:200px;font-size:0.8rem;color:#16191f">` +
    `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">` +
    (logo
      ? `<img src="${esc(logo)}" width="32" height="32" alt="" style="border-radius:4px" onerror="this.remove()">`
      : "") +
    `<div><div style="font-weight:700;font-size:1rem">${esc(planeName(p))}` +
    (isClosest ? ` <span style="color:#b38f00;font-size:0.75rem">· closest</span>` : "") +
    `</div>` +
    (sub ? `<div style="color:#2a7f86">${esc(sub)}</div>` : "") +
    `</div></div>` +
    tableHtml(summaryRows(p, units)) +
    `<details style="margin-top:6px"><summary style="cursor:pointer;color:#1a5fa8">More info</summary>` +
    tableHtml(detailRows(p, units)) +
    (url
      ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" ` +
        `style="display:inline-block;margin-top:6px">Track on adsb.lol ↗</a>`
      : "") +
    `</details></div>`
  );
}

export default function FlightMap({
  latitude,
  longitude,
  radius,
  units,
  aircraft,
  closestHex,
  selectedHex,
  onSelect,
}) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const homeRef = useRef(null);
  const circleRef = useRef(null);
  const markersRef = useRef(new Map());
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Create the map once.
  useEffect(() => {
    // A start view makes the map "loaded", so layers attach right away.
    const map = L.map(elRef.current, { zoomControl: true }).setView([20, 0], 2);
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 18 }).addTo(map);
    mapRef.current = map;
    const markers = markersRef.current;
    return () => {
      markers.clear();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // The spot and the radius circle; zoom to fit the circle when they change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || latitude == null || longitude == null) return;
    const center = [latitude, longitude];
    const meters = radius * (METERS_PER[units] ?? METERS_PER.mi);
    if (!circleRef.current) {
      circleRef.current = L.circle(center, {
        radius: meters,
        color: "#4a9fe8",
        weight: 1.5,
        fillOpacity: 0.06,
        interactive: false,
      }).addTo(map);
      homeRef.current = L.circleMarker(center, {
        radius: 6,
        color: "#ffffff",
        weight: 2,
        fillColor: "#e8453c",
        fillOpacity: 1,
      })
        .bindTooltip("Your spot")
        .addTo(map);
    } else {
      circleRef.current.setLatLng(center).setRadius(meters);
      homeRef.current.setLatLng(center);
    }
    // From the spot and radius, not circle.getBounds(), which needs the
    // circle to be drawn on the map first.
    map.fitBounds(L.latLng(center).toBounds(meters * 2), { padding: [10, 10] });
  }, [latitude, longitude, radius, units]);

  // Planes: move existing markers in place so an open popup stays open.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers = markersRef.current;
    const seen = new Set();
    for (const p of aircraft ?? []) {
      const key = planeKey(p);
      seen.add(key);
      const isClosest = key === closestHex;
      const icon = planeIcon(p, isClosest, key === selectedHex);
      const html = popupHtml(p, units, isClosest);
      let m = markers.get(key);
      if (m) {
        // Keep "More info" open across the once-a-minute refresh.
        const fold = () => m.getPopup()?.getElement()?.querySelector("details");
        const wasOpen = fold()?.open;
        m.setLatLng([p.latitude, p.longitude]).setIcon(icon).setPopupContent(html);
        if (wasOpen && fold()) fold().open = true;
        m.setZIndexOffset(isClosest ? 1000 : 0);
      } else {
        m = L.marker([p.latitude, p.longitude], {
          icon,
          zIndexOffset: isClosest ? 1000 : 0,
        })
          .bindPopup(html)
          .addTo(map);
        m.on("click", () => onSelectRef.current?.(key));
        // Only clear the pick if it is still this plane (opening another
        // plane's popup closes this one first).
        m.on("popupclose", () => onSelectRef.current?.((cur) => (cur === key ? null : cur)));
        markers.set(key, m);
      }
    }
    for (const [key, m] of markers) {
      if (!seen.has(key)) {
        m.remove();
        markers.delete(key);
      }
    }
  }, [aircraft, closestHex, selectedHex, units]);

  // Selecting a plane from the list opens its popup.
  useEffect(() => {
    const m = selectedHex && markersRef.current.get(selectedHex);
    if (m && !m.isPopupOpen()) {
      m.openPopup();
      mapRef.current?.panTo(m.getLatLng());
    }
  }, [selectedHex]);

  return (
    <div
      ref={elRef}
      style={{ height: 340, width: "100%", borderRadius: 8, overflow: "hidden", zIndex: 0 }}
    />
  );
}
