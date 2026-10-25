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
  { label: "Blue", value: "0,0,255", rgb: [0, 0, 255] },
  { label: "Cyan", value: "0,255,255", rgb: [0, 255, 255] },
  { label: "Green", value: "0,255,0", rgb: [0, 255, 0] },
  { label: "Magenta", value: "255,0,255", rgb: [255, 0, 255] },
  { label: "Orange", value: "255,165,0", rgb: [255, 165, 0] },
  { label: "Red", value: "255,0,0", rgb: [255, 0, 0] },
  { label: "White", value: "255,255,255", rgb: [255, 255, 255] },
  { label: "Yellow", value: "255,255,0", rgb: [255, 255, 0] },
];

// Dropdown choices = solid presets plus Caitlin Mode, sorted alphabetically by
// label (the emoji is ignored for sorting so it lands after "Blue").
const COLOR_OPTIONS = [
  ...COLOR_PRESETS.map((p) => ({ label: p.label, value: p.value, sortKey: p.label })),
  { label: "🌈 Caitlin Mode", value: "rainbow", sortKey: "Caitlin Mode" },
].sort((a, b) => a.sortKey.localeCompare(b.sortKey));

const CYCLE_OPTIONS = [3, 5, 10, 15, 30, 60];

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
      hour12: !use24h,
    });
  } catch {
    return now.toLocaleTimeString("en-US", { hour12: !use24h });
  }
}

function tzAbbr(date, timeZone) {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      hour: "numeric",
      timeZoneName: "short",
    }).formatToParts(date);
    const name = parts.find((p) => p.type === "timeZoneName")?.value;
    // GMT+X style names aren't useful as a label; fall back to the city.
    if (name && !/\d/.test(name)) return name;
  } catch {
    /* ignore */
  }
  return timeZone.split("/").pop().replace(/_/g, " ").slice(0, 4).toUpperCase();
}

// Preview of the physical display: focus = one zone (time / date / tz),
// multi = up to three columns divided into thirds. Both follow list order.
const RAINBOW_GRADIENT =
  "linear-gradient(90deg, #ff0000, #ff8800, #ffee00, #00cc44, #0088ff, #8800ff, #ff0000)";

// Text styled as an animated rainbow sliding to the right (matches the board's
// "Caitlin Mode"). Uses background-clip so the gradient fills the glyphs.
function rainbowTextStyle(extra = {}) {
  return {
    background: RAINBOW_GRADIENT,
    backgroundSize: "200% 100%",
    WebkitBackgroundClip: "text",
    backgroundClip: "text",
    WebkitTextFillColor: "transparent",
    color: "transparent",
    animation: "clockRainbowSlide 2.5s linear infinite",
    ...extra,
  };
}

function ClockPreview({ timezones, mode, use24h, color, rainbow }) {
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const timeColorStyle = rainbow ? rainbowTextStyle() : { color };

  if (!timezones || timezones.length === 0) {
    return (
      <div style={{ color: "#5a7a9a", fontSize: "0.85rem", padding: "12px 0" }}>
        Add a timezone to preview.
      </div>
    );
  }

  const fmt = (tz) => {
    try {
      const s = now.toLocaleTimeString("en-US", {
        timeZone: tz,
        hour: "numeric",
        minute: "2-digit",
        hour12: !use24h,
      });
      if (use24h) return { time: s, ampm: "" };
      const [t, ap] = s.split(" ");
      return { time: t, ampm: ap || "" };
    } catch {
      return { time: "--:--", ampm: "" };
    }
  };

  if (mode === "multi") {
    const page = timezones.slice(0, 3);
    return (
      <div style={{ display: "flex", width: "100%" }}>
        {page.map((tz, i) => {
          const { time, ampm } = fmt(tz);
          return (
            <div
              key={tz}
              style={{
                flex: 1,
                textAlign: "center",
                borderLeft: i === 0 ? "none" : "1px solid #2a3a4a",
                padding: "6px 2px",
              }}
            >
              <div style={{ fontSize: "0.7rem", color: "#5a7a9a", textTransform: "uppercase" }}>
                {tzAbbr(now, tz)}
              </div>
              <div
                style={{
                  fontSize: "1.3rem",
                  fontWeight: 700,
                  fontVariantNumeric: "tabular-nums",
                  lineHeight: 1.1,
                  ...timeColorStyle,
                }}
              >
                {time}
              </div>
              {ampm && <div style={{ fontSize: "0.7rem", ...timeColorStyle }}>{ampm}</div>}
            </div>
          );
        })}
      </div>
    );
  }

  // Focus: three stacked lines for the first zone (time / date / tz). Focus
  // includes seconds (the board has room for them on the time line).
  const tz = timezones[0];
  const fmtFocus = (zone) => {
    try {
      const s = now.toLocaleTimeString("en-US", {
        timeZone: zone,
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hour12: !use24h,
      });
      if (use24h) return { time: s, ampm: "" };
      const [t, ap] = s.split(" ");
      return { time: t, ampm: ap || "" };
    } catch {
      return { time: "--:--:--", ampm: "" };
    }
  };
  const { time, ampm } = fmtFocus(tz);
  let dateStr = "";
  try {
    dateStr = now.toLocaleDateString("en-US", {
      timeZone: tz,
      weekday: "short",
      month: "short",
      day: "2-digit",
    });
  } catch {
    dateStr = "";
  }
  return (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          fontSize: "2rem",
          fontWeight: 700,
          fontVariantNumeric: "tabular-nums",
          letterSpacing: 2,
          ...timeColorStyle,
        }}
      >
        {time}
        {ampm && <span style={{ fontSize: "1rem", marginLeft: 4 }}>{ampm}</span>}
      </div>
      <div style={{ fontSize: "0.8rem", color: "#5a7a9a", marginTop: 2 }}>{dateStr}</div>
      <div
        style={{
          fontSize: "0.85rem",
          color: "#7eb8f7",
          marginTop: 2,
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        {tzAbbr(now, tz)}
      </div>
    </div>
  );
}

function TimezoneRow({ tz, index, total, use24h, onRemove, onMove }) {
  const liveTime = useLiveClock(tz, use24h);
  const label = tz.split("/").pop().replace(/_/g, " ");
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
        padding: "8px 12px",
        background: "#0d1922",
        border: "1px solid #2a3a4a",
        borderRadius: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <button
            className="m-btn m-btn-neutral"
            style={{ fontSize: "0.6rem", padding: "0 6px", height: 16, lineHeight: 1 }}
            onClick={() => onMove(index, -1)}
            disabled={index === 0}
            aria-label={`Move ${label} up`}
          >
            ▲
          </button>
          <button
            className="m-btn m-btn-neutral"
            style={{ fontSize: "0.6rem", padding: "0 6px", height: 16, lineHeight: 1 }}
            onClick={() => onMove(index, 1)}
            disabled={index === total - 1}
            aria-label={`Move ${label} down`}
          >
            ▼
          </button>
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: "0.88rem",
              color: "#e8f0f8",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {label}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#5a7a9a" }}>{tz}</div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span
          style={{
            fontSize: "0.95rem",
            fontWeight: 600,
            fontVariantNumeric: "tabular-nums",
            color: "#7eb8f7",
            whiteSpace: "nowrap",
          }}
        >
          {liveTime}
        </span>
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.75rem", padding: "4px 10px" }}
          onClick={onRemove}
          disabled={total <= 1}
          title={total <= 1 ? "Keep at least one timezone" : "Remove"}
          aria-label={`Remove ${label}`}
        >
          ✕
        </button>
      </div>
    </div>
  );
}

function TimezoneSelect({ selected, onAdd }) {
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
          timezones.map((tz) => {
            const already = selected.includes(tz);
            return (
              <div
                key={tz}
                onClick={() => !already && onAdd(tz)}
                style={{
                  padding: "6px 8px 6px 12px",
                  cursor: already ? "default" : "pointer",
                  fontSize: "0.88rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  background: already ? "#132231" : "transparent",
                  color: already ? "#5a7a9a" : "#c8d8e8",
                  borderBottom: "1px solid #1a2a3a",
                  userSelect: "none",
                }}
              >
                <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {tz}
                </span>
                {already ? (
                  <span style={{ fontSize: "0.75rem", whiteSpace: "nowrap" }}>✓ Added</span>
                ) : (
                  <button
                    className="m-btn m-btn-neutral"
                    style={{ fontSize: "0.75rem", padding: "3px 10px", whiteSpace: "nowrap" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onAdd(tz);
                    }}
                  >
                    + Add
                  </button>
                )}
              </div>
            );
          })}
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

  const [timezones, setTimezones] = React.useState([]);
  const [displayMode, setDisplayMode] = React.useState("focus"); // "focus" | "multi"
  const [cycleSeconds, setCycleSeconds] = React.useState(5);
  const [colorPreset, setColorPreset] = React.useState(COLOR_PRESETS[0]);
  const [colorMode, setColorMode] = React.useState("solid"); // "solid" | "rainbow"
  const [use24h, setUse24h] = React.useState(false);
  const [saveStatus, setSaveStatus] = React.useState(null); // null | "saving" | "saved"

  const colorRef = React.useRef(colorPreset);
  const use24hRef = React.useRef(use24h);
  const timerRef = React.useRef(null);

  React.useEffect(() => {
    colorRef.current = colorPreset;
  }, [colorPreset]);
  React.useEffect(() => {
    use24hRef.current = use24h;
  }, [use24h]);

  React.useEffect(() => {
    if (settings) {
      setTimezones(
        Array.isArray(settings.timezones) && settings.timezones.length
          ? settings.timezones
          : ["America/New_York"]
      );
      setDisplayMode(settings.display_mode === "multi" ? "multi" : "focus");
      setCycleSeconds(settings.cycle_seconds ?? 5);
      setColorPreset(findPreset(settings.color));
      setColorMode(settings.color_mode === "rainbow" ? "rainbow" : "solid");
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

  const save = (payload) => {
    setSaveStatus("saving");
    saveMut.mutate(payload);
  };

  // Debounced save for the color/format controls so dragging a select doesn't
  // fire a request per keystroke.
  const scheduleDisplaySave = React.useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setSaveStatus("saving");
    timerRef.current = setTimeout(() => {
      saveMut.mutate({
        color: valueToRgb(colorRef.current.value),
        use_24h: use24hRef.current,
      });
    }, 500);
  }, [saveMut]);

  const handleMode = (nextMode) => {
    setDisplayMode(nextMode);
    save({ display_mode: nextMode });
  };

  const handleCycle = (secs) => {
    setCycleSeconds(secs);
    save({ cycle_seconds: secs });
  };

  const addTimezone = (tz) => {
    if (!tz || timezones.includes(tz)) return;
    const next = [...timezones, tz];
    setTimezones(next);
    save({ timezones: next });
  };

  const removeTimezone = (tz) => {
    if (timezones.length <= 1) return; // keep at least one
    const next = timezones.filter((z) => z !== tz);
    setTimezones(next);
    save({ timezones: next });
  };

  const moveTimezone = (index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= timezones.length) return;
    const next = [...timezones];
    [next[index], next[target]] = [next[target], next[index]];
    setTimezones(next);
    save({ timezones: next });
  };

  // The color dropdown offers the solid presets plus "Caitlin Mode" (rainbow).
  // Picking a solid preset also flips color_mode back to solid.
  const handleColorChoice = (choice) => {
    if (choice === "rainbow") {
      setColorMode("rainbow");
      save({ color_mode: "rainbow" });
      return;
    }
    const preset = COLOR_PRESETS.find((p) => p.value === choice) ?? COLOR_PRESETS[0];
    setColorPreset(preset);
    colorRef.current = preset;
    setColorMode("solid");
    save({ color: valueToRgb(preset.value), color_mode: "solid" });
  };
  const handle24h = (checked) => {
    setUse24h(checked);
    use24hRef.current = checked;
    scheduleDisplaySave();
  };

  const previewHex = "#" + colorPreset.rgb.map((v) => v.toString(16).padStart(2, "0")).join("");

  if (isLoading) return <LoadingSpinner />;

  const saveIndicator = (
    <span
      style={{
        fontSize: "0.75rem",
        color: saveStatus === "saved" ? "#29d66e" : "#5a7a9a",
        transition: "color 0.3s",
      }}
    >
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

      <style>{`@keyframes clockRainbowSlide { from { background-position: 0% 0; } to { background-position: -200% 0; } }`}</style>

      {/* Live preview */}
      <div className="m-card" style={{ textAlign: "center" }}>
        <div className="m-card-title">Preview</div>
        <ClockPreview
          timezones={timezones}
          mode={displayMode}
          use24h={use24h}
          color={previewHex}
          rainbow={colorMode === "rainbow"}
        />
        {timezones.length > (displayMode === "multi" ? 3 : 1) && (
          <div style={{ fontSize: "0.75rem", color: "#5a7a9a", marginTop: 8 }}>
            Cycles through {timezones.length} timezones every {cycleSeconds}s
          </div>
        )}
      </div>

      {/* View mode */}
      <div className="m-card">
        <div className="m-card-title">View</div>
        <div className="m-btn-row">
          <button
            className={`m-btn ${displayMode === "focus" ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => handleMode("focus")}
          >
            Focus
          </button>
          <button
            className={`m-btn ${displayMode === "multi" ? "m-btn-active" : "m-btn-neutral"}`}
            onClick={() => handleMode("multi")}
          >
            Multi
          </button>
        </div>
        <div style={{ color: "#5a7a9a", fontSize: "0.8rem", marginTop: 8 }}>
          {displayMode === "multi"
            ? "Shows up to three timezones at a time, divided into thirds, paging down your list."
            : "Shows one timezone at a time, cycling down your list."}
        </div>
      </div>

      {/* Timezones */}
      <div className="m-card">
        <div className="m-card-title">Timezones</div>
        <div style={{ color: "#5a7a9a", fontSize: "0.8rem", marginBottom: 10 }}>
          The display goes down this list in order. Use ▲▼ to reorder.
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
          {timezones.map((tz, i) => (
            <TimezoneRow
              key={tz}
              tz={tz}
              index={i}
              total={timezones.length}
              use24h={use24h}
              onRemove={() => removeTimezone(tz)}
              onMove={moveTimezone}
            />
          ))}
        </div>

        <div style={{ fontSize: "0.85rem", color: "#c8d8e8", marginBottom: 6 }}>Add a timezone</div>
        <TimezoneSelect selected={timezones} onAdd={addTimezone} />
      </div>

      {/* Cycle interval */}
      <div className="m-card">
        <div className="m-card-title">Cycle</div>
        <div className="m-toggle-row">
          <span className="m-label">Seconds per screen</span>
          <select
            className="m-select"
            style={{ width: "auto" }}
            value={cycleSeconds}
            onChange={(e) => handleCycle(Number(e.target.value))}
          >
            {CYCLE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}s
              </option>
            ))}
          </select>
        </div>
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
                background:
                  colorMode === "rainbow"
                    ? "linear-gradient(90deg, red, orange, yellow, green, blue, violet)"
                    : previewHex,
                border: "1px solid #555",
              }}
            />
            <select
              className="m-select"
              style={{ width: "auto" }}
              value={colorMode === "rainbow" ? "rainbow" : colorPreset.value}
              onChange={(e) => handleColorChoice(e.target.value)}
            >
              {COLOR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
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
