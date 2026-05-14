import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useApiCheck, INCREMENT_RETRIES, RESET_RETRIES } from "../../providers/APICheckProvider";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";
import { useMTATrains } from "../../hooks/useMTATrains";
import { TrainLogos, getRandomTrainLogos } from "../../utility/SubwayLogos";
import { AllStations } from "../../constants/SubwayStations";
import SubwayMap from "../../components/mta/SubwayMap";
import CurrentStop from "../../components/mta/CurrentStop";

const DEFAULT_CENTER = { lat: 40.7831, lon: -73.9712 };

const ICON_BTN = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: "1.2rem",
  color: "#5a7a9a",
  padding: "4px 2px",
  lineHeight: 1,
};

function lookupStation(key) {
  return AllStations.find((s) => s.fullStationName === key) ?? null;
}

function useMTAData() {
  const { dispatch } = useApiCheck();
  const query = useMTATrains();

  React.useEffect(() => {
    if (query.isSuccess) dispatch({ type: RESET_RETRIES });
  }, [query.isSuccess]);

  React.useEffect(() => {
    if (query.isError) dispatch({ type: INCREMENT_RETRIES });
  }, [query.isError]);

  const stationKey = query.data?.station ?? "";
  const stopName = query.data?.stop_name ?? query.data?.station ?? "";
  const trains = query.data?.trains ?? [];
  const stationInfo = React.useMemo(() => lookupStation(stationKey), [stationKey]);

  return { ...query, trains, stopName, stationKey, stationInfo };
}

export default function MTA() {
  const navigate = useNavigate();
  const { trains, stopName, stationKey, stationInfo, isLoading, isError, refetch, isFetching } =
    useMTAData();
  const [loadingLogos, setLoadingLogos] = React.useState(getRandomTrainLogos());
  const [showMap, setShowMap] = React.useState(true);
  const [mapInit, setMapInit] = React.useState(false);
  const [center, setCenter] = React.useState(DEFAULT_CENTER);

  React.useEffect(() => {
    const id = setInterval(() => setLoadingLogos(getRandomTrainLogos()), 1000);
    return () => clearInterval(id);
  }, []);

  React.useEffect(() => {
    if (stationInfo) {
      setCenter({ lat: stationInfo.coordinates[0], lon: stationInfo.coordinates[1] });
      setMapInit(false);
    }
  }, [stationKey]);

  const trainLines = [...new Set(trains.map((t) => t.route))];
  const handleCenter = () => {
    if (stationInfo)
      setCenter({ lat: stationInfo.coordinates[0], lon: stationInfo.coordinates[1] });
  };

  return (
    <div>
      {/* ── Page header ─────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <div className="m-section-title" style={{ margin: 0 }}>
          MTA
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <SwitchDisplayButton mode="mta" />
          <button style={ICON_BTN} aria-label="Refresh" onClick={() => refetch()}>
            {isFetching ? "⏳" : "🔄"}
          </button>
          <button style={ICON_BTN} aria-label="Settings" onClick={() => navigate("/mta/settings")}>
            ⚙️
          </button>
        </div>
      </div>

      <div className="m-section-sub">New York City Subway</div>

      {/* ── Current stop ─────────────────────────────────────────── */}
      <CurrentStop stopName={stopName} trainLines={trainLines} isLoading={isLoading} />

      {/* ── Next trains ──────────────────────────────────────────── */}
      <div className="m-card">
        <div className="m-card-title">Next Trains</div>
        {isLoading ? (
          <div style={{ padding: "16px 0" }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {loadingLogos.slice(0, 8).map((src, i) => (
                <img key={i} width="22" height="22" src={src} alt="loading" />
              ))}
            </div>
          </div>
        ) : isError ? (
          <div style={{ color: "#e05050", padding: "12px 0", fontSize: "0.9rem" }}>
            Could not reach API. Retrying…
          </div>
        ) : trains.length === 0 ? (
          <div style={{ color: "#5a7a9a", padding: "12px 0", fontSize: "0.9rem" }}>
            No upcoming trains.
          </div>
        ) : (
          trains.map((train, i) => {
            const arriving = train.arrival_minutes <= 1;
            return (
              <div key={i} className="m-train-card">
                {TrainLogos[train.route] ? (
                  <img className="m-train-logo" src={TrainLogos[train.route]} alt={train.route} />
                ) : (
                  <div
                    className="m-train-logo"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: "#1a2a40",
                      borderRadius: "50%",
                      fontSize: "0.7rem",
                      fontWeight: 700,
                      color: "#fff",
                    }}
                  >
                    {train.route}
                  </div>
                )}
                <div style={{ flex: 1 }}>
                  <div className="m-train-dest" style={arriving ? { color: "#f0a800" } : undefined}>
                    {train.destination}
                  </div>
                  <div className="m-train-dir">
                    {train.direction === "N" ? "Northbound" : "Southbound"}
                  </div>
                </div>
                {!arriving && <div className="m-train-time waiting">{train.arrival_minutes}m</div>}
              </div>
            );
          })
        )}
      </div>

      {/* ── Map ──────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <button className="m-map-toggle" style={{ flex: 1 }} onClick={() => setShowMap((v) => !v)}>
          {showMap ? "▲ Hide Map" : "▼ Show Map"}
        </button>
        {showMap && (
          <button
            className="m-map-toggle"
            style={{ flex: "0 0 auto", width: 120 }}
            onClick={handleCenter}
            disabled={!stationInfo}
          >
            📍 Center Map
          </button>
        )}
      </div>

      {showMap && (
        <div className="m-card" style={{ padding: 0, overflow: "hidden" }}>
          <SubwayMap
            currentStation={
              stationInfo
                ? { stop_name: stationInfo.stationName, complex_id: stationInfo.complexId }
                : { stop_name: "Loading" }
            }
            centerCoords={center}
            mapInitialized={mapInit}
            setMapInitialized={setMapInit}
          />
        </div>
      )}
    </div>
  );
}
