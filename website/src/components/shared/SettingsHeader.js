import React from "react";
import { useNavigate } from "react-router-dom";

export default function SettingsHeader({ title, backTo, right }) {
  const navigate = useNavigate();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
      <button
        onClick={() => navigate(backTo)}
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
        {title}
      </div>
      {right && <div style={{ marginLeft: "auto" }}>{right}</div>}
    </div>
  );
}
