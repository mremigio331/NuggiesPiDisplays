import React from "react";

export default function TeamRow({ abbr, score, color, state, winner }) {
  const dot = color ? `#${color.replace(/^#/, "")}` : "#444";
  const textColor = winner ? "#fff" : state === "post" ? "#777" : "#ccc";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: dot, flexShrink: 0 }} />
      <span style={{ flex: 1, fontWeight: 600, fontSize: "0.9rem", color: textColor }}>{abbr}</span>
      {state !== "pre" && (
        <span
          style={{
            fontSize: "1.3rem",
            fontWeight: 700,
            minWidth: 32,
            textAlign: "right",
            color: state === "in" ? "#f0a800" : winner ? "#fff" : "#666",
          }}
        >
          {score}
        </span>
      )}
    </div>
  );
}
