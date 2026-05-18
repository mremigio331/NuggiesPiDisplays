import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNotify } from "../../hooks/useNotify";
import { updateMTAConfig } from "../../services/API";
import { LOG_LEVELS } from "../../constants/display";

export default function DisplayOptions({ configs }) {
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
