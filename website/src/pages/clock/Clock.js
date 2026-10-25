import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useClockSettings } from "../../hooks/useClockSettings";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";

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

function rgbToHex(rgb) {
  if (!Array.isArray(rgb)) return "#ffffff";
  return "#" + rgb.map((v) => v.toString(16).padStart(2, "0")).join("");
}

function findPresetHex(rgb) {
  const value = Array.isArray(rgb) ? rgb.join(",") : "255,255,255";
  const preset = COLOR_PRESETS.find((p) => p.value === value);
  return preset ? rgbToHex(preset.rgb) : rgbToHex(rgb);
}

// "Caitlin Mode" (color_mode === "rainbow"): an animated rainbow that slides to
// the right, matching the board and the Settings-page preview. Uses
// background-clip so the gradient fills the glyphs.
const RAINBOW_GRADIENT =
  "linear-gradient(90deg, #ff0000, #ff8800, #ffee00, #00cc44, #0088ff, #8800ff, #ff0000)";

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

function ClockRow({ tz, use24h, colorStyle }) {
  const liveTime = useLiveClock(tz, use24h);
  const label = tz.split("/").pop().replace(/_/g, " ");
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 10,
      }}
    >
      <span style={{ fontSize: "0.9rem", color: "#5a7a9a" }}>{label}</span>
      <span
        style={{
          fontSize: "1.4rem",
          fontWeight: 700,
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
          ...colorStyle,
        }}
      >
        {liveTime}
      </span>
    </div>
  );
}

export default function Clock() {
  const navigate = useNavigate();
  const { data: settings, isLoading } = useClockSettings();

  const use24h = settings?.use_24h ?? false;
  const colorHex = settings ? findPresetHex(settings.color) : "#ffffff";
  const rainbow = settings?.color_mode === "rainbow";
  const timeColorStyle = rainbow ? rainbowTextStyle() : { color: colorHex };
  const timezones =
    Array.isArray(settings?.timezones) && settings.timezones.length
      ? settings.timezones
      : ["America/New_York"];
  const displayMode = settings?.display_mode === "multi" ? "multi" : "focus";
  const primaryTime = useLiveClock(timezones[0], use24h);

  return (
    <div>
      <style>{`@keyframes clockRainbowSlide { from { background-position: 0% 0; } to { background-position: -200% 0; } }`}</style>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <div className="m-section-title" style={{ margin: 0 }}>
          Clock
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <SwitchDisplayButton mode="clock" />
          <button
            onClick={() => navigate("/clock/settings")}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "1.2rem",
              color: "#5a7a9a",
            }}
            aria-label="Settings"
          >
            ⚙️
          </button>
        </div>
      </div>
      <div className="m-section-sub">Live clock preview</div>

      {isLoading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
          <div className="m-spinner m-spinner-lg" />
        </div>
      ) : (
        <div className="m-card" style={{ textAlign: "center", padding: "32px 18px" }}>
          {timezones.length > 1 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {timezones.map((tz) => (
                <ClockRow key={tz} tz={tz} use24h={use24h} colorStyle={timeColorStyle} />
              ))}
            </div>
          ) : (
            <>
              <div
                style={{
                  fontSize: "2.8rem",
                  fontWeight: 700,
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: 3,
                  lineHeight: 1,
                  ...timeColorStyle,
                }}
              >
                {primaryTime}
              </div>
              <div style={{ fontSize: "0.85rem", color: "#5a7a9a", marginTop: 10 }}>
                {timezones[0]}
              </div>
            </>
          )}
          <div style={{ fontSize: "0.75rem", color: "#5a7a9a", marginTop: 12 }}>
            {displayMode === "multi" ? "Multi view" : "Focus view"}
            {timezones.length > 1 && ` · ${timezones.length} timezones`}
          </div>
          <button
            className="m-btn m-btn-neutral"
            style={{ marginTop: 16, width: "100%" }}
            onClick={() => navigate("/clock/settings")}
          >
            ⚙️ Settings
          </button>
        </div>
      )}
    </div>
  );
}
