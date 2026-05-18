import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useDebounce } from "../../hooks/useDebounce";
import { useNotify } from "../../hooks/useNotify";
import { setStationEnabled } from "../../services/API";

export default function StationCycleList({ allStations, enabledStations }) {
  const qc = useQueryClient();
  const { start, ok, fail } = useNotify();
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounce(search, 200);
  const [pending, setPending] = React.useState(new Set());

  const stations = Array.isArray(allStations) ? allStations : [];
  const enabledSet = React.useMemo(
    () => new Set(Array.isArray(enabledStations) ? enabledStations : []),
    [enabledStations]
  );

  const filtered = React.useMemo(() => {
    if (!debouncedSearch) return stations;
    const q = debouncedSearch.toLowerCase();
    return stations.filter((s) => s.toLowerCase().includes(q));
  }, [stations, debouncedSearch]);

  const handleToggle = async (station, enabled) => {
    if (pending.has(station)) return;
    setPending((p) => new Set([...p, station]));
    const id = start(`${enabled ? "Enabling" : "Disabling"} ${station}…`);
    try {
      await setStationEnabled(station, enabled);
      qc.invalidateQueries({ queryKey: ["enabledStations"] });
      ok(id, `${station} ${enabled ? "enabled" : "disabled"}`);
    } catch (err) {
      fail(id, err);
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
