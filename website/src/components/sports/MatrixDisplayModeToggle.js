import React from "react";

export default function MatrixDisplayModeToggle({ displayMode, isPending, onChangeMode }) {
  return (
    <div className="m-card" style={{ padding: "0.5rem 0.75rem", marginBottom: 12 }}>
      <div style={{ color: "#888", fontSize: "0.72rem", marginBottom: 6 }}>Matrix display</div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className={`m-btn ${displayMode === "focus" ? "m-btn-active" : "m-btn-neutral"}`}
          style={{ padding: "3px 12px", fontSize: "0.78rem" }}
          disabled={isPending}
          onClick={() => onChangeMode("focus")}
        >
          Focus
        </button>
        <button
          className={`m-btn ${displayMode === "overview" ? "m-btn-active" : "m-btn-neutral"}`}
          style={{ padding: "3px 12px", fontSize: "0.78rem" }}
          disabled={isPending}
          onClick={() => onChangeMode("overview")}
        >
          Overview
        </button>
      </div>
    </div>
  );
}
