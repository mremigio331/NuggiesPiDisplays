import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useMTAConfigs } from "../../hooks/useMTAConfigs";
import { useAllStations } from "../../hooks/useAllStations";
import { useEnabledStations } from "../../hooks/useEnabledStations";
import { useDebounce } from "../../hooks/useDebounce";
import { updateMTAConfig, setCurrentStation, setStationEnabled } from "../../services/API";
import { getNotificationsContext, N } from "../../services/Notifications";
import { v4 as uuidv4 } from "uuid";

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];

function useNotify() {
  const { pushNotification, dismissNotification, modifyNotificationContent } =
    getNotificationsContext();

  const notify = (run) => {
    const id = uuidv4();
    pushNotification({
      id,
      type: N.INFO,
      content: "Saving…",
      loading: true,
      dismissible: false,
      onDismiss: () => dismissNotification(id),
    });
    return run(id);
  };

  const ok = (id, msg = "Saved.") =>
    modifyNotificationContent(id, {
      content: msg,
      type: N.SUCCESS,
      loading: false,
      dismissible: true,
      onDismiss: () => dismissNotification(id),
    });

  const fail = (id, err) =>
    modifyNotificationContent(id, {
      content: `Failed: ${err.message}`,
      type: N.ERROR,
      loading: false,
      dismissible: true,
      onDismiss: () => dismissNotification(id),
    });

  return { notify, ok, fail };
}

/* ── Current Station ───────────────────────────────────────────── */
function StationPicker({ currentStation, allStations }) {
  const qc = useQueryClient();
  const { notify, ok, fail } = useNotify();
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounce(search, 200);
  const [pending, setPending] = React.useState(null);

  const filtered = React.useMemo(() => {
    if (!allStations) return [];
    if (!debouncedSearch) return allStations;
    const q = debouncedSearch.toLowerCase();
    return allStations.filter((s) => s.toLowerCase().includes(q));
  }, [allStations, debouncedSearch]);

  const handleSelect = async (station) => {
    if (station === currentStation || pending) return;
    setPending(station);
    notify(async (id) => {
      try {
        await setCurrentStation(station);
        qc.invalidateQueries({ queryKey: ["mtaConfigs"] });
        qc.invalidateQueries({ queryKey: ["mtaTrains"] });
        ok(id, `Station set to ${station}`);
      } catch (err) {
        fail(id, err);
      } finally {
        setPending(null);
      }
    });
  };

  return (
    <div className="m-card">
      <div className="m-card-title">Current Station</div>
      <div style={{ fontWeight: 700, fontSize: "1rem", color: "#e8f0f8", marginBottom: 12 }}>
        {currentStation || "—"}
      </div>
      <input
        className="m-input"
        type="text"
        placeholder="Search stations…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <div
        style={{ maxHeight: 260, overflowY: "auto", border: "1px solid #1a2a40", borderRadius: 8 }}
      >
        {filtered.length === 0 && (
          <div style={{ padding: "10px 12px", color: "#5a7a9a", fontSize: "0.85rem" }}>
            No stations match
          </div>
        )}
        {filtered.map((s) => {
          const isCurrent = s === currentStation;
          const isLoading = s === pending;
          return (
            <div
              key={s}
              onClick={() => handleSelect(s)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "9px 12px",
                cursor: isCurrent || isLoading ? "default" : "pointer",
                borderBottom: "1px solid #1a2a40",
                background: isCurrent ? "#0a2a18" : "transparent",
                color: isCurrent ? "#29d66e" : "#c8d8e8",
                fontSize: "0.88rem",
              }}
            >
              <span>{s}</span>
              {isCurrent && (
                <span style={{ fontSize: "0.75rem", color: "#29d66e", fontWeight: 700 }}>
                  ACTIVE
                </span>
              )}
              {isLoading && (
                <div className="m-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Display Options ───────────────────────────────────────────── */
function DisplayOptions({ configs }) {
  const qc = useQueryClient();
  const { notify, ok, fail } = useNotify();
  const [cycleTime, setCycleTime] = React.useState(String(configs.cycle_time ?? "5"));
  const [cycleTimeDirty, setCycleTimeDirty] = React.useState(false);

  React.useEffect(() => {
    setCycleTime(String(configs.cycle_time ?? "5"));
    setCycleTimeDirty(false);
  }, [configs.cycle_time]);

  const saveConfig = (key, value) => {
    notify(async (id) => {
      try {
        await updateMTAConfig(key, value);
        qc.invalidateQueries({ queryKey: ["mtaConfigs"] });
        ok(id);
      } catch (err) {
        fail(id, err);
      }
    });
  };

  const saveCycleTime = () => {
    const v = parseInt(cycleTime, 10);
    if (!v || v <= 0) return;
    saveConfig("cycle_time", String(v));
    setCycleTimeDirty(false);
  };

  return (
    <div className="m-card">
      <div className="m-card-title">Display Options</div>

      {/* Cycle toggle */}
      <div className="m-toggle-row">
        <div>
          <div className="m-toggle-label">Cycle through stations</div>
          <div className="m-toggle-val">Automatically rotate between active stations</div>
        </div>
        <label className="m-switch">
          <input
            type="checkbox"
            checked={Boolean(configs.cycle)}
            onChange={(e) => saveConfig("cycle", e.target.checked)}
          />
          <span className="m-switch-slider" />
        </label>
      </div>

      {/* Cycle time */}
      <div
        className="m-toggle-row"
        style={{ alignItems: "flex-start", flexDirection: "column", gap: 8 }}
      >
        <div className="m-toggle-label">Seconds per station</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="m-input"
            type="number"
            min="1"
            max="300"
            value={cycleTime}
            onChange={(e) => {
              setCycleTime(e.target.value);
              setCycleTimeDirty(true);
            }}
            style={{ width: 80 }}
          />
          {cycleTimeDirty && (
            <button
              className="m-btn m-btn-primary"
              style={{ height: 38, padding: "0 14px", fontSize: "0.85rem" }}
              onClick={saveCycleTime}
            >
              Save
            </button>
          )}
        </div>
      </div>

      {/* Log level */}
      <div className="m-toggle-row">
        <div className="m-toggle-label">Log level</div>
        <select
          className="m-select"
          style={{ width: "auto" }}
          value={String(configs.log_level ?? "INFO")}
          onChange={(e) => saveConfig("log_level", e.target.value)}
        >
          {LOG_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/* ── Station Cycling List ──────────────────────────────────────── */
function StationCycleList({ allStations, enabledStations }) {
  const qc = useQueryClient();
  const { pushNotification, dismissNotification, modifyNotificationContent } =
    getNotificationsContext();
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounce(search, 200);
  const [pending, setPending] = React.useState(new Set());

  const enabledSet = React.useMemo(() => new Set(enabledStations ?? []), [enabledStations]);

  const filtered = React.useMemo(() => {
    if (!allStations) return [];
    if (!debouncedSearch) return allStations;
    const q = debouncedSearch.toLowerCase();
    return allStations.filter((s) => s.toLowerCase().includes(q));
  }, [allStations, debouncedSearch]);

  const handleToggle = async (station, enabled) => {
    if (pending.has(station)) return;
    setPending((p) => new Set([...p, station]));
    const id = uuidv4();
    pushNotification({
      id,
      type: N.INFO,
      content: `${enabled ? "Enabling" : "Disabling"} ${station}…`,
      loading: true,
      dismissible: false,
      onDismiss: () => dismissNotification(id),
    });
    try {
      await setStationEnabled(station, enabled);
      qc.invalidateQueries({ queryKey: ["enabledStations"] });
      modifyNotificationContent(id, {
        content: `${station} ${enabled ? "enabled" : "disabled"}`,
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
    } finally {
      setPending((p) => {
        const n = new Set(p);
        n.delete(station);
        return n;
      });
    }
  };

  return (
    <div className="m-card">
      <div className="m-card-title">
        Stations in Rotation
        <span style={{ marginLeft: 8, fontWeight: 400, color: "#4a9fe8" }}>
          {enabledSet.size} active
        </span>
      </div>
      <div style={{ fontSize: "0.8rem", color: "#5a7a9a", marginBottom: 10 }}>
        These stations will cycle when rotation is on.
      </div>
      <input
        className="m-input"
        type="text"
        placeholder="Filter stations…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <div
        style={{ maxHeight: 320, overflowY: "auto", border: "1px solid #1a2a40", borderRadius: 8 }}
      >
        {filtered.map((s) => {
          const enabled = enabledSet.has(s);
          const isLoading = pending.has(s);
          return (
            <div
              key={s}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "9px 12px",
                borderBottom: "1px solid #1a2a40",
                background: enabled ? "#0a1a10" : "transparent",
              }}
            >
              <span style={{ fontSize: "0.87rem", color: enabled ? "#c8f0d8" : "#8a9ab0" }}>
                {s}
              </span>
              {isLoading ? (
                <div className="m-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
              ) : (
                <label className="m-switch">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => handleToggle(s, e.target.checked)}
                  />
                  <span className="m-switch-slider" />
                </label>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function MTASettings() {
  const navigate = useNavigate();
  const { data: configs, isLoading: configsLoading } = useMTAConfigs();
  const { data: allStations, isLoading: stationsLoading } = useAllStations();
  const { data: enabledStations } = useEnabledStations();

  const isLoading = configsLoading || stationsLoading;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <button
          onClick={() => navigate("/mta")}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#5a7a9a",
            fontSize: "1.2rem",
            padding: 0,
            lineHeight: 1,
          }}
          aria-label="Back"
        >
          ←
        </button>
        <div className="m-section-title" style={{ margin: 0 }}>
          MTA Settings
        </div>
      </div>
      <div className="m-section-sub" style={{ marginBottom: 16 }}>
        Configure station and display options
      </div>

      {isLoading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
          <div className="m-spinner m-spinner-lg" />
        </div>
      ) : (
        <>
          <StationPicker currentStation={configs?.station} allStations={allStations} />
          <DisplayOptions configs={configs || {}} />
          <StationCycleList allStations={allStations} enabledStations={enabledStations} />
        </>
      )}
    </div>
  );
}
