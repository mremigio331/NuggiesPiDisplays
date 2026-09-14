import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  getSportsSettings,
  updateSportsSettings,
  getSportsTeams,
  addFavoriteTeam,
  removeFavoriteTeam,
} from "../../services/API";
import { favoritesForSport } from "../../utility/favorites";

// Leagues in alphabetical order
const SPORTS = [
  { key: "mlb", label: "MLB" },
  { key: "nba", label: "NBA" },
  { key: "nfl", label: "NFL" },
  { key: "nhl", label: "NHL" },
  { key: "nwsl", label: "NWSL" },
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

  const displayMode = settings?.display_mode ?? "focus";
  const sport = settings?.sport ?? "nba";
  const favTeams = favoritesForSport(settings, sport);

  // Real teams for the selected league, with the ESPN ids favourites are keyed by
  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ["sportsTeams", sport],
    queryFn: () => getSportsTeams(sport),
    staleTime: 24 * 60 * 60 * 1000, // rosters of teams change once a season
  });
  const teamOptions = teamsData?.teams ?? [];

  // Favourites are stored per sport, so toggling always writes into this league
  const favMut = useMutation({
    mutationFn: ({ teamId, favorited }) =>
      favorited ? removeFavoriteTeam(teamId, sport) : addFavoriteTeam(teamId, sport),
    onSuccess: (data) => qc.setQueryData(["sportsSettings"], data),
  });

  function toggleTeam(teamId) {
    favMut.mutate({ teamId, favorited: favTeams.includes(String(teamId)) });
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
          {SPORTS.map(({ key, label }) => (
            <button
              key={key}
              className={`m-btn ${sport === key ? "m-btn-active" : "m-btn-neutral"}`}
              disabled={mut.isPending}
              onClick={() => mut.mutate({ sport: key })}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="m-form-desc">
          Switches the matrix display and scoreboard between sports.
        </div>
      </div>

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
        <div className="m-form-desc" style={{ marginTop: 6 }}>
          Locking a game from the scoreboard overrides both: the matrix stays on that game, full
          screen, with its stat panels still cycling.
        </div>
      </div>

      {/* Favorite teams — kept per league, so switching sports shows its own picks */}
      <div className="m-card">
        <div className="m-card-title">
          Favorite Teams
          <span style={{ color: "#777", fontWeight: 400, fontSize: "0.75rem" }}>
            {" "}
            · {SPORTS.find((s) => s.key === sport)?.label ?? sport}
          </span>
        </div>
        <div className="m-form-desc" style={{ marginBottom: 10 }}>
          Highlighted on the scoreboard. Tap to toggle. Each league keeps its own list.
        </div>

        {teamsLoading && <div style={{ color: "#888", fontSize: "0.8rem" }}>Loading teams…</div>}
        {!teamsLoading && teamOptions.length === 0 && (
          <div style={{ color: "#888", fontSize: "0.8rem" }}>
            No teams available for this league.
          </div>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {teamOptions.map((team) => (
            <button
              key={team.id}
              className={`m-btn ${favTeams.includes(String(team.id)) ? "m-btn-active" : "m-btn-neutral"}`}
              style={{ padding: "4px 8px", fontSize: "0.8rem", minWidth: 44 }}
              disabled={favMut.isPending}
              onClick={() => toggleTeam(team.id)}
              title={team.name}
            >
              {team.abbreviation || team.short_name}
            </button>
          ))}
        </div>

        {favTeams.length > 0 && (
          <div style={{ marginTop: 8, color: "#aaa", fontSize: "0.75rem" }}>
            Selected:{" "}
            {favTeams
              .map((id) => teamOptions.find((t) => String(t.id) === String(id))?.abbreviation ?? id)
              .join(", ")}
          </div>
        )}
      </div>

      {(mut.isError || favMut.isError) && (
        <div className="m-card" style={{ borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontSize: "0.85rem" }}>Failed to save settings.</div>
        </div>
      )}
    </div>
  );
}
