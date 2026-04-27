import * as React from "react";
import {
  Box,
  Button,
  Container,
  ContentLayout,
  Grid,
  Header,
  SpaceBetween,
  Spinner,
} from "@cloudscape-design/components";
import { useIsMobile } from "../../hooks/useIsMobile";
import { useMTATrains } from "../../hooks/useMTATrains";
import { useApiCheck, INCREMENT_RETRIES, RESET_RETRIES } from "../../providers/APICheckProvider";
import { TrainLogos, getRandomTrainLogos } from "../../utility/SubwayLogos";
import { AllStations } from "../../constants/SubwayStations";
import TrainCards from "../../components/mta/TrainCards";
import SubwayMap from "../../components/mta/SubwayMap";

const DEFAULT_CENTER = { lat: 40.7831, lon: -73.9712 };

function lookupStation(key) {
  return AllStations.find((s) => s.fullStationName === key) ?? null;
}

/* ── Shared data hook ──────────────────────────────────────────── */
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
  const isMobile = useIsMobile();
  return isMobile ? <MobileMTA /> : <DesktopMTA />;
}

/* ── Mobile ────────────────────────────────────────────────────── */
function MobileMTA() {
  const { trains, stopName, stationKey, stationInfo, isLoading, isError, refetch, isFetching } =
    useMTAData();
  const [loadingLogos, setLoadingLogos] = React.useState(getRandomTrainLogos());
  const [showMap, setShowMap] = React.useState(false);
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
      {/* Station header */}
      <div className="m-card" style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div className="m-section-title">{stopName || "Loading…"}</div>
            <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
              {trainLines.map((line) =>
                TrainLogos[line] ? (
                  <img key={line} width="22" height="22" src={TrainLogos[line]} alt={line} />
                ) : null
              )}
            </div>
          </div>
          <button
            onClick={() => refetch()}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "1.2rem",
              color: "#5a7a9a",
            }}
            aria-label="Refresh"
          >
            {isFetching ? "⏳" : "🔄"}
          </button>
        </div>
      </div>

      {/* Train list */}
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
          trains.map((train, i) => (
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
                <div className="m-train-dest">{train.destination}</div>
                <div className="m-train-dir">
                  {train.direction === "N" ? "Northbound" : "Southbound"}
                </div>
              </div>
              <div
                className={`m-train-time ${train.arrival_minutes === 0 ? "arriving" : "waiting"}`}
              >
                {train.arrival_minutes === 0 ? "Now" : `${train.arrival_minutes}m`}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Map controls */}
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

/* ── Desktop ───────────────────────────────────────────────────── */
function DesktopMTA() {
  const { trains, stopName, stationKey, stationInfo, isLoading, isError, refetch, isFetching } =
    useMTAData();
  const [loadingLogos, setLoadingLogos] = React.useState(getRandomTrainLogos());
  const [mapInit, setMapInit] = React.useState(false);
  const [center, setCenter] = React.useState(DEFAULT_CENTER);
  const IMG = "25";

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
  const stationForMap = stationInfo
    ? { stop_name: stationInfo.stationName, complex_id: stationInfo.complexId }
    : { stop_name: "Loading" };

  const infoPanel = (
    <SpaceBetween size="m">
      <Container
        header={
          <Header
            variant="h2"
            actions={
              <Button iconName="zoom-to-fit" disabled={!stationInfo} onClick={handleCenter}>
                Center Map
              </Button>
            }
          >
            <SpaceBetween direction="horizontal" size="s" alignItems="center">
              <span>{stopName || "Loading…"}</span>
              {trainLines.map((line) =>
                TrainLogos[line] ? (
                  <img key={line} width={IMG} height={IMG} src={TrainLogos[line]} alt={line} />
                ) : null
              )}
            </SpaceBetween>
          </Header>
        }
      >
        {isLoading ? (
          <SpaceBetween size="m">
            <Spinner size="large" />
            <SpaceBetween direction="horizontal" size="xs">
              {loadingLogos.map((src, i) => (
                <img key={i} width={IMG} height={IMG} src={src} alt="loading" />
              ))}
            </SpaceBetween>
          </SpaceBetween>
        ) : isError ? (
          <Box color="text-status-error">Could not reach API. Retrying…</Box>
        ) : trains.length === 0 ? (
          <Box color="text-status-inactive">No upcoming trains.</Box>
        ) : (
          <TrainCards trains={trains} isMobile={false} />
        )}
      </Container>
    </SpaceBetween>
  );

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          actions={
            <Button
              iconName="refresh"
              variant="icon"
              loading={isFetching}
              onClick={() => refetch()}
            />
          }
        >
          MTA
        </Header>
      }
    >
      <Grid gridDefinition={[{ colspan: 4 }, { colspan: 8 }]}>
        {infoPanel}
        <SubwayMap
          currentStation={stationForMap}
          centerCoords={center}
          mapInitialized={mapInit}
          setMapInitialized={setMapInit}
        />
      </Grid>
    </ContentLayout>
  );
}
