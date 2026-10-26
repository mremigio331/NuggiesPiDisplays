import React from "react";

// A small LED-matrix styled loader used wherever the app is waiting on an API
// response. Website-only, purely decorative — it mirrors the look of the
// physical 64x32 panel (dark bezel, glowing cells) at a compact size so it
// feels like part of the product rather than a generic spinner.
//
// Kept intentionally light: a sweeping lit bar over a dim LED grid, not the
// full mode-cycling mockup used for the multi-second reboot wait. A data fetch
// usually resolves in well under a second, so this reads instantly and never
// flashes a half-drawn mockup.
export function LedLoader({ width = 120, height = 60, label = "Loading\u2026" }) {
  // Render on the real panel aspect (2:1, like 64x32) and scale via width/height.
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div
        style={{
          background: "#111",
          padding: 6,
          borderRadius: 8,
          boxShadow: "0 0 0 2px #2a2a2a",
        }}
      >
        <div
          style={{
            position: "relative",
            width,
            height,
            background: "radial-gradient(circle at center, #0c0c0c 0, #050505 100%)",
            borderRadius: 3,
            overflow: "hidden",
          }}
        >
          {/* dim LED grid */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage: "radial-gradient(#1a1a1a 0.5px, transparent 0.5px)",
              backgroundSize: "4px 4px",
              opacity: 0.8,
            }}
          />
          {/* three pulsing dots in the center, LED-green */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
            }}
          >
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#7cff7c",
                  boxShadow: "0 0 4px #7cff7c",
                  animation: `ledLoaderPulse 1.1s ease-in-out ${i * 0.18}s infinite`,
                }}
              />
            ))}
          </div>
          {/* a soft sweep of light across the panel */}
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              width: "35%",
              background:
                "linear-gradient(90deg, transparent, rgba(124,255,124,0.18), transparent)",
              animation: "ledLoaderSweep 1.6s linear infinite",
            }}
          />
        </div>
      </div>
      {label && <div style={{ color: "#5a7a9a", fontSize: "0.75rem" }}>{label}</div>}
    </div>
  );
}

// Compact reload indicator for a BACKGROUND refetch (React Query `isFetching`
// while data is already on screen). Deliberately tiny and inline — initial load
// (`isLoading`) gets the full LedLoader above; a reload should hint activity
// without hiding the content the user is already looking at. A row of small
// pulsing LED-green dots, optionally with a label.
export function LedFetchingIndicator({ label = "" }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        verticalAlign: "middle",
      }}
      aria-label={label || "Refreshing"}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 4,
            height: 4,
            borderRadius: "50%",
            background: "#7cff7c",
            boxShadow: "0 0 3px #7cff7c",
            animation: `ledLoaderPulse 1.1s ease-in-out ${i * 0.18}s infinite`,
          }}
        />
      ))}
      {label && <span style={{ color: "#5a7a9a", fontSize: "0.72rem" }}>{label}</span>}
    </span>
  );
}

// Backwards-compatible default export: every existing <LoadingSpinner /> usage
// now renders the full LED loader, centered with the same padding as before.
export default function LoadingSpinner(props) {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
      <LedLoader {...props} />
    </div>
  );
}
