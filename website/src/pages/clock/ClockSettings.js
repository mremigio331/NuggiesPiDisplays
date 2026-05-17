import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useClockSettings } from "../../hooks/useClockSettings";
import { useClockTimezones } from "../../hooks/useClockTimezones";
import { useDebounce } from "../../hooks/useDebounce";
import { useNotify } from "../../hooks/useNotify";
import { updateClockSettings } from "../../services/API";
import SettingsHeader from "../../components/shared/SettingsHeader";
import LoadingSpinner from "../../components/shared/LoadingSpinner";

const COLOR_PRESETS = [
  { label: "White", value: "255,255,255", rgb: [255, 255, 255] },
  { label: "Red", value: "255,0,0", rgb: [255, 0, 0] },
  { label: "Green", value: "0,255,0", rgb: [0, 255, 0] },
  { label: "Blue", value: "0,0,255", rgb: [0, 0, 255] },
  { label: "Yellow", value: "255,255,0", rgb: [255, 255, 0] },
  { label: "Cyan", value: "0,255,255", rgb: [0, 255, 255] },
  { label: "Magenta", value: "255,0,255", rgb: [255, 0, 255] },
  { label: "Orange", value: "255,165,0", rgb: [255, 165, 0] },
];

function rgbToValue(rgb) {
  if (!Array.isArray(rgb)) return "255,255,255";
  return rgb.join(",");
}

function valueToRgb(value) {
  return value.split(",").map(Number);
}

function findPreset(rgb) {
  const v = rgbToValue(rgb);
  return COLOR_PRESETS.find((p) => p.value === v) ?? COLOR_PRESETS[0];
}

function useLiveClock(timezone, use24h = false) {
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  try {
    return now.toLocaleTimeString("en-US", {
      timeZone: timezone,
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: !use24h,
    });
  } catch {
    return now.toLocaleTimeString("en-US", { hour12: !use24h });
  }
}

function TimezoneSelect({ value, onChange }) {
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounce(search);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  const { data, isLoading } = useClockTimezones(page, debouncedSearch);
  const timezones = data?.timezones ?? [];
  const totalPages = data?.total_pages ?? 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: "0.8rem", color: "#5a7a9a" }}>
        Current: <span style={{ fontWeight: 600, color: "#e8f0f8" }}>{value || "—"}</span>
      </div>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search timezones…"
        className="m-input"
      />
      <div
        style={{
          border: "1px solid #2a3a4a",
          borderRadius: 8,
          overflow: "hidden",
          maxHeight: 220,
          overflowY: "auto",
          background: "#0d1922",
        }}
      >
        {isLoading && (
          <div style={{ padding: "10px 12px", color: "#5a7a9a", fontSize: "0.85rem" }}>
            Loading…
          </div>
        )}
        {!isLoading && timezones.length === 0 && (
          <div style={{ padding: "10px 12px", color: "#5a7a9a", fontSize: "0.85rem" }}>
            No results
          </div>
        )}
        {!isLoading &&
          timezones.map((tz) => (
            <div
              key={tz}
              onClick={() => onChange(tz)}
              style={{
                padding: "7px 12px",
                cursor: "pointer",
                fontSize: "0.88rem",
                background: tz === value ? "#1a3a5a" : "transparent",
                color: tz === value ? "#7eb8f7" : "#c8d8e8",
                borderBottom: "1px solid #1a2a3a",
                userSelect: "none",
              }}
            >
              {tz}
            </div>
          ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button
          className="m-btn m-btn-neutral"
          style={{ flex: 1, height: 36, fontSize: "0.85rem" }}
          onClick={() => setPage((p) => p - 1)}
          disabled={page === 1 || isLoading}
        >
          ‹ Prev
        </button>
        <span style={{ flex: 1, textAlign: "center", fontSize: "0.8rem", color: "#5a7a9a" }}>
          {page} / {totalPages}
        </span>
        <button
          className="m-btn m-btn-neutral"
          style={{ flex: 1, height: 36, fontSize: "0.85rem" }}
          onClick={() => setPage((p) => p + 1)}
          disabled={page === totalPages || isLoading}
        >
          Next ›
        </button>
      </div>
    </div>
  );
}

export default function ClockSettings() {
  const qc = useQueryClient();
  const { error: notifyError } = useNotify();
  const { data: settings, isLoading } = useClockSettings();

  const [timezone, setTimezone] = React.useState("");
  const [colorPreset, setColorPreset] = React.useState(COLOR_PRESETS[0]);
  const [use24h, setUse24h] = React.useState(false);
  const [saveStatus, setSaveStatus] = React.useState(null); // null | "saving" | "saved"

  // Refs so the debounced callback always reads the latest values
  const tzRef = React.useRef(timezone);
  const colorRef = React.useRef(colorPreset);
  const use24hRef = React.useRef(use24h);
  const timerRef = React.useRef(null);

  React.useEffect(() => {
    tzRef.current = timezone;
  }, [timezone]);
  React.useEffect(() => {
    colorRef.current = colorPreset;
  }, [colorPreset]);
  React.useEffect(() => {
    use24hRef.current = use24h;
  }, [use24h]);

  React.useEffect(() => {
    if (settings) {
      setTimezone(settings.timezone ?? "America/New_York");
      setColorPreset(findPreset(settings.color));
      setUse24h(settings.use_24h ?? false);
    }
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: updateClockSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clockSettings"] });
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus(null), 2000);
    },
    onError: (err) => {
      setSaveStatus(null);
      notifyError(err);
    },
  });

  // Debounce saves: preview updates instantly, API call fires 500 ms after the last change
  const scheduleSave = React.useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setSaveStatus("saving");
    timerRef.current = setTimeout(() => {
      saveMut.mutate({
        timezone: tzRef.current,
        color: valueToRgb(colorRef.current.value),
        use_24h: use24hRef.current,
      });
    }, 500);
  }, []);

  const handleTimezone = (tz) => {
    setTimezone(tz);
    tzRef.current = tz;
    scheduleSave();
  };
  const handleColor = (preset) => {
    setColorPreset(preset);
    colorRef.current = preset;
    scheduleSave();
  };
  const handle24h = (checked) => {
    setUse24h(checked);
    use24hRef.current = checked;
    scheduleSave();
  };

  const liveTime = useLiveClock(timezone || "UTC", use24h);
  const previewHex = "#" + colorPreset.rgb.map((v) => v.toString(16).padStart(2, "0")).join("");

  if (isLoading) return <LoadingSpinner />;

  const saveIndicator = (
    <span style={{ fontSize: "0.75rem", color: saveStatus === "saved" ? "#29d66e" : "#5a7a9a", transition: "color 0.3s" }}>
      {saveStatus === "saving" && "Saving…"}
      {saveStatus === "saved" && "✓ Saved"}
    </span>
  );

  return (
    <div>
      <SettingsHeader title="Clock Settings" backTo="/clock" right={saveIndicator} />
      <div className="m-section-sub" style={{ marginBottom: 16 }}>
        Changes apply automatically
      </div>

      {/* Live preview */}
      <div className="m-card" style={{ textAlign: "center" }}>
        <div className="m-card-title">Preview</div>
        <div
          style={{
            fontSize: "2rem",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            color: previewHex,
            letterSpacing: 2,
          }}
        >
          {liveTime}
        </div>
        <div style={{ fontSize: "0.8rem", color: "#5a7a9a", marginTop: 4 }}>{timezone}</div>
      </div>

      {/* Timezone */}
      <div className="m-card">
        <div className="m-card-title">Timezone</div>
        <TimezoneSelect value={timezone} onChange={handleTimezone} />
      </div>

      {/* Color & format */}
      <div className="m-card">
        <div className="m-card-title">Display</div>

        <div className="m-toggle-row">
          <span className="m-label">Color</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                display: "inline-block",
                width: 16,
                height: 16,
                borderRadius: 3,
                background: previewHex,
                border: "1px solid #555",
              }}
            />
            <select
              className="m-select"
              style={{ width: "auto" }}
              value={colorPreset.value}
              onChange={(e) => handleColor(COLOR_PRESETS.find((p) => p.value === e.target.value))}
            >
              {COLOR_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="m-toggle-row">
          <span className="m-label">24-hour time</span>
          <label className="m-switch">
            <input type="checkbox" checked={use24h} onChange={(e) => handle24h(e.target.checked)} />
            <span className="m-switch-slider" />
          </label>
        </div>
      </div>
    </div>
  );
}
