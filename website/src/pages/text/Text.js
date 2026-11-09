import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useTextSettings } from "../../hooks/useTextSettings";
import SwitchDisplayButton from "../../components/shared/SwitchDisplayButton";
import LedPreview from "../../components/text/LedPreview";

export default function Text() {
  const navigate = useNavigate();
  const { data: settings, isLoading } = useTextSettings();

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <div className="m-section-title" style={{ margin: 0 }}>
          Text
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <SwitchDisplayButton mode="text" />
          <button
            onClick={() => navigate("/text/settings")}
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
      <div className="m-section-sub">Your message on the board</div>

      {isLoading || !settings ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
          <div className="m-spinner m-spinner-lg" />
        </div>
      ) : (
        <div className="m-card" style={{ textAlign: "center" }}>
          <LedPreview
            rowCount={settings.row_count}
            rows={settings.rows}
            scrollSeconds={settings.scroll_seconds}
          />
          <button
            className="m-btn m-btn-neutral"
            style={{ marginTop: 16, width: "100%" }}
            onClick={() => navigate("/text/settings")}
          >
            ✏️ Edit Text
          </button>
        </div>
      )}
    </div>
  );
}
