import * as React from "react";
import { useNavigate } from "react-router-dom";
import { TrainLogos } from "../../utility/SubwayLogos";

export default function CurrentStop({ stopName, trainLines, isLoading }) {
  const navigate = useNavigate();

  return (
    <div className="m-card" style={{ marginBottom: 14 }}>
      <div className="m-card-title">Current Stop</div>

      <div
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          {isLoading ? (
            <div style={{ color: "#5a7a9a", fontSize: "0.95rem" }}>Loading…</div>
          ) : (
            <div
              style={{
                fontSize: "1.05rem",
                fontWeight: 700,
                color: "#d4dfe8",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {stopName || "—"}
            </div>
          )}

          {trainLines.length > 0 && (
            <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
              {trainLines.map((line) =>
                TrainLogos[line] ? (
                  <img key={line} width="24" height="24" src={TrainLogos[line]} alt={line} />
                ) : (
                  <span
                    key={line}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 24,
                      height: 24,
                      background: "#1a2a40",
                      borderRadius: "50%",
                      fontSize: "0.65rem",
                      fontWeight: 700,
                      color: "#fff",
                    }}
                  >
                    {line}
                  </span>
                )
              )}
            </div>
          )}
        </div>

        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.8rem", padding: "6px 14px", height: "auto", flex: "none" }}
          onClick={() => navigate("/mta/settings")}
        >
          Change
        </button>
      </div>
    </div>
  );
}
