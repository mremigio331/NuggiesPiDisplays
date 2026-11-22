import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { TILE_ATTRIBUTION, TILE_URL } from "./FlightMap";

// Click (or tap) the map to drop a pin. Calls onPick({ latitude, longitude }).
export default function LocationPickerMap({ latitude, longitude, picked, onPick }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const pinRef = useRef(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  useEffect(() => {
    const hasSpot = latitude != null && longitude != null;
    const map = L.map(elRef.current).setView(
      hasSpot ? [latitude, longitude] : [20, 0],
      hasSpot ? 11 : 2
    );
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 18 }).addTo(map);
    map.on("click", (e) => {
      const { lat, lng } = e.latlng.wrap();
      onPickRef.current?.({
        latitude: Math.round(lat * 1e6) / 1e6,
        longitude: Math.round(lng * 1e6) / 1e6,
      });
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      pinRef.current = null;
    };
    // The start view only; later spot changes come through `picked`.
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!picked) {
      pinRef.current?.remove();
      pinRef.current = null;
      return;
    }
    const at = [picked.latitude, picked.longitude];
    if (pinRef.current) pinRef.current.setLatLng(at);
    else
      pinRef.current = L.circleMarker(at, {
        radius: 7,
        color: "#ffffff",
        weight: 2,
        fillColor: "#e8453c",
        fillOpacity: 1,
      }).addTo(map);
  }, [picked]);

  return (
    <div
      ref={elRef}
      style={{
        height: 300,
        width: "100%",
        borderRadius: 8,
        overflow: "hidden",
        zIndex: 0,
        cursor: "crosshair",
      }}
    />
  );
}
