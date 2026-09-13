import React from "react";
import TeamRow from "./TeamRow";
import { isFavoriteGame } from "../../utility/favorites";

// Shared by every football league (NFL, NCAAF, …) — identical game payload.
function footballPeriodLabel(game) {
  const { state, period, clock, status_detail } = game;

  if (state === "in") {
    if ((status_detail || "").toLowerCase().includes("half")) return "Halftime";
    const q = period <= 4 ? `Q${period}` : period === 5 ? "OT" : `OT${period - 4}`;
    return clock ? `${q} ${clock}` : q;
  }

  if (state === "post") {
    return period > 4 ? "Final/OT" : "Final";
  }

  return null;
}

const ORDINALS = { 1: "1st", 2: "2nd", 3: "3rd", 4: "4th" };

function downAndDistance(game) {
  const { down, distance, yard_line_text } = game;
  if (!down) return null;
  const label = ORDINALS[down] ?? down;
  const dd = distance ? `${label} & ${distance}` : `${label} & Goal`;
  return yard_line_text ? `${dd} at ${yard_line_text}` : dd;
}

export default function FootballGameCard({ game, favoriteTeams, activeEventIds }) {
  const {
    away_team,
    home_team,
    away_score,
    home_score,
    state,
    status_detail,
    away_color,
    home_color,
    possession,
    is_red_zone,
  } = game;

  const isFav = isFavoriteGame(game, favoriteTeams);
  const isActive = activeEventIds?.has(game.event_id);
  const isLive = state === "in";
  const isFinal = state === "post";
  const awayWin = isFinal && away_score > home_score;
  const homeWin = isFinal && home_score > away_score;
  const periodLabel = footballPeriodLabel(game);
  const situation = isLive ? downAndDistance(game) : null;
  const possessionTeam =
    possession === "away" ? away_team : possession === "home" ? home_team : null;

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
          {isLive && is_red_zone && (
            <span
              style={{
                background: "#c0392b",
                color: "#fff",
                fontSize: "0.6rem",
                fontWeight: 700,
                padding: "1px 5px",
                borderRadius: 3,
              }}
            >
              RED ZONE
            </span>
          )}
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

      {situation && (
        <div style={{ marginTop: 7, color: "#888", fontSize: "0.72rem" }}>
          {situation}
          {possessionTeam ? ` · ${possessionTeam} ball` : ""}
        </div>
      )}
    </div>
  );
}
