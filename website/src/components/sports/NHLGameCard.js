import React from "react";
import TeamRow from "./TeamRow";
import { isFavoriteGame } from "../../utility/favorites";

function nhlPeriodLabel(game) {
  const { state, period, clock } = game;

  if (state === "in") {
    const p = period <= 3 ? `P${period}` : period === 4 ? "OT" : "SO";
    return clock ? `${p} ${clock}` : p;
  }

  if (state === "post") {
    if (period === 4) return "Final/OT";
    if (period > 4) return "Final/SO";
    return "Final";
  }

  return null;
}

export default function NHLGameCard({ game, favoriteTeams, activeEventIds }) {
  const {
    away_team,
    home_team,
    away_score,
    home_score,
    state,
    status_detail,
    away_color,
    home_color,
  } = game;

  const isFav = isFavoriteGame(game, favoriteTeams);
  const isActive = activeEventIds?.has(game.event_id);
  const isLive = state === "in";
  const isFinal = state === "post";
  const awayWin = isFinal && away_score > home_score;
  const homeWin = isFinal && home_score > away_score;
  const periodLabel = nhlPeriodLabel(game);

  return (
    <div
      className="m-card"
      style={{
        marginBottom: "0.5rem",
        borderColor: isActive ? "#2196f3" : isFav ? "#c47d00" : undefined,
        boxShadow: isActive ? "0 0 0 1px #2196f3" : undefined,
        padding: "0.6rem 0.75rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        {isLive && (
          <span
            style={{
              background: "#c0392b",
              color: "#fff",
              fontSize: "0.62rem",
              fontWeight: 700,
              padding: "1px 5px",
              borderRadius: 3,
              letterSpacing: 1,
            }}
          >
            LIVE
          </span>
        )}

        {periodLabel && (
          <span style={{ color: isLive ? "#f0a800" : "#666", fontSize: "0.75rem" }}>
            {periodLabel}
          </span>
        )}

        {state === "pre" && status_detail && (
          <span style={{ color: "#666", fontSize: "0.75rem" }}>{status_detail}</span>
        )}

        <span style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
          {isActive && (
            <span
              style={{ fontSize: "0.65rem", color: "#2196f3", fontWeight: 700, letterSpacing: 0.5 }}
            >
              ON NOW
            </span>
          )}
          {isFav && <span style={{ fontSize: "0.7rem", color: "#c47d00" }}>★ Fav</span>}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        <TeamRow
          abbr={away_team}
          score={away_score}
          color={away_color}
          state={state}
          winner={awayWin}
        />
        <TeamRow
          abbr={home_team}
          score={home_score}
          color={home_color}
          state={state}
          winner={homeWin}
        />
      </div>
    </div>
  );
}
