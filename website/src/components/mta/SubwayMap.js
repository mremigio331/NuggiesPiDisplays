import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import selectedMarker from "../../assets/MapMarkers/MTA_Selected.png";
import notSelectedMarker from "../../assets/MapMarkers/MTA_Not_Selected.png";
import { TrainLogos } from "../../utility/SubwayLogos";
import { AllStations } from "../../constants/SubwayStations";
import { setCurrentStation } from "../../services/API";
import { getNotificationsContext, N } from "../../services/Notifications";
import { v4 as uuidv4 } from "uuid";

export default function SubwayMap({
  currentStation,
  centerCoords,
  mapInitialized,
  setMapInitialized,
}) {
  const { pushNotification, dismissNotification, modifyNotificationContent } =
    getNotificationsContext();
  const mapRef = useRef(null);

  const handleStationClick = async (fullStationName) => {
    const id = uuidv4();
    pushNotification({
      id,
      type: N.INFO,
      content: `Changing to ${fullStationName}…`,
      loading: true,
      dismissible: false,
      onDismiss: () => dismissNotification(id),
    });
    try {
      await setCurrentStation(fullStationName);
      modifyNotificationContent(id, {
        content: `Station changed to ${fullStationName}`,
        type: N.SUCCESS,
        loading: false,
        dismissible: true,
        onDismiss: () => dismissNotification(id),
      });
    } catch (err) {
      modifyNotificationContent(id, {
        content: `Failed: ${err.message}`,
        type: N.ERROR,
        loading: false,
        dismissible: true,
        onDismiss: () => dismissNotification(id),
      });
    }
  };

  const initializeMap = () => {
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    const zoom = currentStation?.stop_name === "Loading" ? 12 : 16;
    const map = L.map("mta-map").setView([centerCoords.lat, centerCoords.lon], zoom);

    L.tileLayer("https://{s}.google.com/vt/lyrs={type}&x={x}&y={y}&z={z}", {
      attribution: 'Map data &copy; <a href="https://www.google.com/maps">Google Maps</a>',
      maxZoom: 20,
      subdomains: ["mt0", "mt1", "mt2", "mt3"],
      type: "r",
    }).addTo(map);

    AllStations.forEach((station) => {
      const isSelected =
        station.complexId === currentStation?.complex_id &&
        station.stationName === currentStation?.stop_name;

      const icon = L.icon({
        iconUrl: isSelected ? selectedMarker : notSelectedMarker,
        iconSize: [45, 45],
        iconAnchor: [22.5, 45],
        popupAnchor: [1, -34],
      });

      const marker = L.marker(station.coordinates, { icon }).addTo(map);
      const container = document.createElement("div");
      container.style.cssText = "display:inline-block;width:260px";
      const root = createRoot(container);

      root.render(
        <div style={{ padding: "4px 0" }}>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#16191f", marginBottom: 6 }}>
            {station.stationName}
          </div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 10 }}>
            {station.trainLines.map((line) =>
              TrainLogos[line] ? (
                <img key={line} width="20" height="20" src={TrainLogos[line]} alt={line} />
              ) : null
            )}
          </div>
          <button
            onClick={() => handleStationClick(station.fullStationName)}
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "#1a5fa8",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: "0.85rem",
              fontWeight: 600,
            }}
          >
            Switch to this station
          </button>
        </div>
      );

      marker.bindPopup(container, { autoClose: true, closeOnClick: true });
      marker.on("popupclose", () => root.unmount());
    });

    mapRef.current = map;
    setMapInitialized(true);
  };

  useEffect(() => {
    if (!mapInitialized) initializeMap();
  }, [mapInitialized]);

  useEffect(() => {
    if (mapRef.current && mapInitialized) {
      mapRef.current.flyTo([centerCoords.lat, centerCoords.lon], 16, { duration: 1 });
    }
  }, [centerCoords]);

  useEffect(() => {
    return () => {
      mapRef.current?.remove();
    };
  }, []);

  return <div id="mta-map" style={{ width: "100%", height: "600px", borderRadius: "8px" }} />;
}
