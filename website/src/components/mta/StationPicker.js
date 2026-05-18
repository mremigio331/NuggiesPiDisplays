import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useDebounce } from "../../hooks/useDebounce";
import { useNotify } from "../../hooks/useNotify";
import { setCurrentStation } from "../../services/API";

export default function StationPicker({ currentStation, allStations }) {
  const qc = useQueryClient();
  const { notify, ok, fail } = useNotify();
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounce(search, 200);
  const [pending, setPending] = React.useState(null);

  const stations = Array.isArray(allStations) ? allStations : [];

  const filtered = React.useMemo(() => {
    if (!debouncedSearch) return stations;
    const q = debouncedSearch.toLowerCase();
    return stations.filter((s) => s.toLowerCase().includes(q));
  }, [stations, debouncedSearch]);

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
