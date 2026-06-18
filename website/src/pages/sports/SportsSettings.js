import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getSportsSettings, updateSportsSettings } from "../../services/API";

const NBA_TEAMS = [
  "ATL",
  "BOS",
  "BKN",
  "CHA",
  "CHI",
  "CLE",
  "DAL",
  "DEN",
  "DET",
  "GSW",
  "HOU",
  "IND",
  "LAC",
  "LAL",
  "MEM",
  "MIA",
  "MIL",
  "MIN",
  "NOP",
  "NYK",
  "OKC",
  "ORL",
  "PHI",
  "PHX",
  "POR",
  "SAC",
  "SAS",
  "TOR",
  "UTA",
  "WAS",
];

export default function SportsSettings() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["sportsSettings"],
    queryFn: getSportsSettings,
    staleTime: 5 * 60 * 1000,
  });

  const mut = useMutation({
    mutationFn: updateSportsSettings,
    onSuccess: (data) => qc.setQueryData(["sportsSettings"], data),
  });

  const favTeams = settings?.favorite_teams ?? [];
  const displayMode = settings?.display_mode ?? "focus";
  const sport = settings?.sport ?? "nba";
  const soccerLeague = settings?.soccer_league ?? "fifa.world";

  function toggleTeam(abbr) {
    const next = favTeams.includes(abbr) ? favTeams.filter((t) => t !== abbr) : [...favTeams, abbr];
    mut.mutate({ favorite_teams: next });
  }

  if (isLoading) {
    return (
      <div>
        <div className="m-section-title">Sports Settings</div>
        <div className="m-card" style={{ color: "#aaa" }}>
          Loading…
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        className="m-section-title"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        Sports Settings
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.8rem", padding: "2px 10px" }}
          onClick={() => navigate("/sports")}
        >
          ← Back
        </button>
      </div>

      {/* Sport selection */}
      <div className="m-card">
        <div className="m-card-title">Sport</div>
        <div className="m-btn-row" style={{ marginBottom: 8 }}>
          <button
            className={`m-btn ${sport === "nba" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ sport: "nba" })}
          >
            NBA
          </button>
          <button
            className={`m-btn ${sport === "mlb" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ sport: "mlb" })}
          >
            MLB
          </button>
          <button
            className={`m-btn ${sport === "nhl" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ sport: "nhl" })}
          >
            NHL
          </button>
          <button
            className={`m-btn ${sport === "soccer" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ sport: "soccer" })}
          >
            Soccer
          </button>
        </div>
        <div className="m-form-desc">
          Switches the matrix display and scoreboard between sports.
        </div>
      </div>

      {/* Soccer league selection — only shown when soccer is active */}
      {sport === "soccer" && (
        <div className="m-card">
          <div className="m-card-title">Soccer League</div>
          <div className="m-btn-row" style={{ marginBottom: 8 }}>
            <button
              className={`m-btn ${soccerLeague === "fifa.world" ? "m-btn-active" : "m-btn-neutral"}`}
              disabled={mut.isPending}
              onClick={() => mut.mutate({ soccer_league: "fifa.world" })}
            >
              FIFA World Cup
            </button>
          </div>
          <div className="m-form-desc">Select which soccer league to display on the matrix.</div>
        </div>
      )}

      {/* Display mode */}
      <div className="m-card">
        <div className="m-card-title">Matrix Display Mode</div>
        <div className="m-btn-row" style={{ marginBottom: 10 }}>
          <button
            className={`m-btn ${displayMode === "focus" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ display_mode: "focus" })}
          >
            Focus
          </button>
          <button
            className={`m-btn ${displayMode === "overview" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ display_mode: "overview" })}
          >
            Overview
          </button>
        </div>
        <div className="m-form-desc">
          <strong style={{ color: "#ccc" }}>Focus</strong> — one game at a time with a full stats
          panel cycling through points, assists, rebounds, and fouls. Advances to the next game
          after two full cycles (~2 min).
        </div>
        <div className="m-form-desc" style={{ marginTop: 6 }}>
          <strong style={{ color: "#ccc" }}>Overview</strong> — cycles through all games every 8
          seconds showing just the score and game status. Good for nights with many games.
        </div>
      </div>

      {/* Favorite teams */}
      <div className="m-card">
        <div className="m-card-title">Favorite Teams</div>
        <div className="m-form-desc" style={{ marginBottom: 10 }}>
          Highlighted on the scoreboard. Tap to toggle.
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {NBA_TEAMS.map((abbr) => (
            <button
              key={abbr}
              className={`m-btn ${favTeams.includes(abbr) ? "m-btn-active" : "m-btn-neutral"}`}
              style={{ padding: "4px 8px", fontSize: "0.8rem", minWidth: 44 }}
              disabled={mut.isPending}
              onClick={() => toggleTeam(abbr)}
            >
              {abbr}
            </button>
          ))}
        </div>
        {favTeams.length > 0 && (
          <div style={{ marginTop: 8, color: "#aaa", fontSize: "0.75rem" }}>
            Selected: {favTeams.join(", ")}
          </div>
        )}
      </div>

      {mut.isError && (
        <div className="m-card" style={{ borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontSize: "0.85rem" }}>Failed to save settings.</div>
        </div>
      )}
    </div>
  );
}
