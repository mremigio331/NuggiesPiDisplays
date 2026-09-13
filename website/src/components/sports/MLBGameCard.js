import React from "react";
import TeamRow from "./TeamRow";
import { isFavoriteGame } from "../../utility/favorites";

function BSODots({ count, max, color }) {
  return (
    <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: i < count ? color : "#333",
            border: `1px solid ${i < count ? color : "#555"}`,
            display: "inline-block",
          }}
        />
      ))}
    </span>
  );
}

function BaseDiamond({ onFirst, onSecond, onThird, size = 14 }) {
  const occ = "#f0a800";
  const empty = "#333";
  const line = "#444";
  const h = size;
  const w = size;
  const cx = w / 2;
  const cy = h / 2;

  return (
    <svg width={w} height={h} style={{ flexShrink: 0 }}>
      <line x1={cx} y1={h - 2} x2={w - 2} y2={cy} stroke={line} strokeWidth={1} />
      <line x1={w - 2} y1={cy} x2={cx} y2={2} stroke={line} strokeWidth={1} />
      <line x1={cx} y1={2} x2={2} y2={cy} stroke={line} strokeWidth={1} />
      <line x1={2} y1={cy} x2={cx} y2={h - 2} stroke={line} strokeWidth={1} />
      <rect x={cx - 3} y={h - 5} width={5} height={5} fill={empty} />
      <rect x={w - 5} y={cy - 3} width={5} height={5} fill={onFirst ? occ : empty} />
      <rect x={cx - 3} y={1} width={5} height={5} fill={onSecond ? occ : empty} />
      <rect x={1} y={cy - 3} width={5} height={5} fill={onThird ? occ : empty} />
    </svg>
  );
}

function mlbInningLabel(game) {
  const { state, period, inning_half, status_detail } = game;

  if (state === "in") {
    const half = inning_half === "top" ? "▲" : inning_half === "bot" ? "▼" : "";
    const suffix = period === 1 ? "st" : period === 2 ? "nd" : period === 3 ? "rd" : "th";
    return `${half} ${period}${suffix}`;
  }

  if (state === "post") return "Final";
  return status_detail || "Scheduled";
}

export default function MLBGameCard({ game, favoriteTeams, activeEventIds }) {
  const {
    away_team,
    home_team,
    away_score,
    home_score,
    state,
    away_color,
    home_color,
    balls,
    strikes,
    outs,
    on_first,
    on_second,
    on_third,
  } = game;

  const isFav = isFavoriteGame(game, favoriteTeams);
  const isActive = activeEventIds?.has(game.event_id);
  const isLive = state === "in";
  const isFinal = state === "post";
  const awayWin = isFinal && away_score > home_score;
  const homeWin = isFinal && home_score > away_score;

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

        <span style={{ color: isLive ? "#f0a800" : "#666", fontSize: "0.75rem" }}>
          {mlbInningLabel(game)}
        </span>

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

      <div
        style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: isLive ? 10 : 0 }}
      >
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

      {isLive && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            paddingTop: 6,
            borderTop: "1px solid #222",
          }}
        >
          <BaseDiamond onFirst={on_first} onSecond={on_second} onThird={on_third} size={28} />

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#666", fontSize: "0.7rem", width: 10 }}>B</span>
              <BSODots count={balls ?? 0} max={4} color="#27ae60" />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#666", fontSize: "0.7rem", width: 10 }}>S</span>
              <BSODots count={strikes ?? 0} max={3} color="#f0a800" />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#666", fontSize: "0.7rem", width: 10 }}>O</span>
              <BSODots count={outs ?? 0} max={3} color="#e74c3c" />
            </div>
          </div>

          {game.batter_jersey && game.batter_jersey !== "?" && (
            <div
              style={{ marginLeft: "auto", fontSize: "0.72rem", color: "#aaa", textAlign: "right" }}
            >
              <div>
                Bat <span style={{ color: "#fff" }}>#{game.batter_jersey}</span>
                {game.batter_avg ? <span style={{ color: "#888" }}> {game.batter_avg}</span> : null}
              </div>
              {game.pitcher_jersey && game.pitcher_jersey !== "?" && (
                <div>
                  Pit <span style={{ color: "#fff" }}>#{game.pitcher_jersey}</span>
                  {game.pitcher_era ? (
                    <span style={{ color: "#888" }}> {game.pitcher_era}</span>
                  ) : null}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
