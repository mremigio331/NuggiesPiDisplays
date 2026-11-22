// Text about one plane, shared by the map popups and the Flights page so
// both say the same thing as the panel: flight number, airline, from/to,
// aircraft and distance flown up top, everything else behind More info.
import { flightLogoUrl } from "../../services/API";

// Stable id for a plane across refreshes (its ICAO hex when it has one).
export const planeKey = (p) => p.hex || `${p.callsign}-${p.latitude}-${p.longitude}`;

// The flight number (DL 629) for an airline flight, else the callsign.
export function planeName(p) {
  return (
    p.airline?.flight_number ||
    p.callsign ||
    p.registration ||
    (p.hex || "").toUpperCase() ||
    "Unknown"
  );
}

const airlineName = (p) => p.airline?.name || "";

export const airlineLogo = (p, size = 64) =>
  p.airline?.iata ? flightLogoUrl(p.airline.iata, size) : null;

const airportCode = (a) => a?.iata || a?.icao || "";

// "SEA → PDX", or "" when the route is unknown.
export function routeCodes(route) {
  const from = airportCode(route?.origin);
  const to = airportCode(route?.destination);
  return from && to ? `${from} → ${to}` : "";
}

// "SEA · Seattle Tacoma International Airport"
const airportText = (a) =>
  a ? [airportCode(a), a.name || a.location].filter(Boolean).join(" · ") : "";

// "Boeing 737 MAX 9 (B39M)"; the feed's description or the bare code when
// the type is not in the list.
const aircraftText = (p) => {
  const text = p.aircraft?.name
    ? `${p.aircraft.name} (${p.aircraft.code})`
    : [p.type, p.description].filter(Boolean).join(" · ");
  // Say "Helicopter" unless the name already does.
  if (p.helicopter && !/helicopter/i.test(text))
    return text ? `Helicopter · ${text}` : "Helicopter";
  return text;
};

const altitudeText = (p) =>
  Number.isFinite(p.altitude_ft) ? `${p.altitude_ft.toLocaleString()} ft` : "";
const distanceText = (p, units) =>
  Number.isFinite(p.distance) ? `${p.distance} ${units} ${p.direction}` : "";

// The second line under the flight number: the airline, or the plane type
// for a plane with no airline. Same as the panel.
export const planeSubtitle = (p) => airlineName(p) || p.aircraft?.name || p.type || "";

// "1,850 mi · 320 mi to go" (straight line from the start airport).
const flownText = (route, units) =>
  Number.isFinite(route?.flown)
    ? `${route.flown.toLocaleString()} ${units} · ${route.to_go.toLocaleString()} ${units} to go`
    : "";

// What the panel shows: where the flight is from and going, and how far it
// has flown. A plane with no known route says so, then shows its type.
export function summaryRows(p, units) {
  // A plane with no airline shows its type under the name already.
  const aircraft = p.airline ? aircraftText(p) : "";
  const rows = p.route
    ? [
        ["From", airportText(p.route.origin)],
        ["To", airportText(p.route.destination)],
        ["Aircraft", aircraft],
        ["Flown", flownText(p.route, units)],
      ]
    : [
        // Still being looked up: leave the route out until it arrives.
        ["Route", p.route_status === "pending" ? "" : "No departure or arrival info"],
        ["Aircraft", aircraftText(p)],
      ];
  return rows.filter(([, v]) => v);
}

// Everything else, behind "More info".
export function detailRows(p, units) {
  const rows = [
    ["Callsign", p.airline ? p.callsign : ""],
    ["Registration", p.registration],
    ["Operator", p.operator],
    ["Altitude", altitudeText(p)],
    ["Speed", Number.isFinite(p.speed_kt) ? `${p.speed_kt} kt` : ""],
    ["Heading", Number.isFinite(p.track) ? `${p.track}°` : ""],
    [
      "Climb",
      Number.isFinite(p.vertical_rate_fpm) && p.vertical_rate_fpm !== 0
        ? `${p.vertical_rate_fpm > 0 ? "+" : ""}${p.vertical_rate_fpm} ft/min`
        : "",
    ],
    ["From you", distanceText(p, units)],
    ["Squawk", p.squawk],
    ["ICAO", (p.hex || "").toUpperCase()],
  ];
  return rows.filter(([, v]) => v);
}

export function trackerUrl(p) {
  return p.hex ? `https://globe.adsb.lol/?icao=${encodeURIComponent(p.hex)}` : null;
}
