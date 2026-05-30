import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  getNBAScoreboard,
  getMLBScoreboard,
  getNHLScoreboard,
  getSportsSettings,
  updateSportsSettings,
  getSportsNow,
} from "../../services/API";
import NBAGameCard from "../../components/sports/NBAGameCard";
import MLBGameCard from "../../components/sports/MLBGameCard";
import NHLGameCard from "../../components/sports/NHLGameCard";
import SportsPageHeader from "../../components/sports/SportsPageHeader";
import MatrixDisplayModeToggle from "../../components/sports/MatrixDisplayModeToggle";
import GameSection from "../../components/sports/GameSection";

export default function Sports() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: settings } = useQuery({
    queryKey: ["sportsSettings"],
    queryFn: getSportsSettings,
    staleTime: 5 * 60 * 1000,
  });

  const sport = settings?.sport ?? "nba";
  const displayMode = settings?.display_mode ?? "focus";
  const favoriteTeams = settings?.favorite_teams ?? [];

  const modeMut = useMutation({
    mutationFn: updateSportsSettings,
    onSuccess: (data) => qc.setQueryData(["sportsSettings"], data),
  });

  const sportConfig = {
    nba: {
      queryKey: ["nbaScoreboard"],
      queryFn: getNBAScoreboard,
      Card: NBAGameCard,
      label: "NBA",
    },
    mlb: {
      queryKey: ["mlbScoreboard"],
      queryFn: getMLBScoreboard,
      Card: MLBGameCard,
      label: "MLB",
    },
    nhl: {
      queryKey: ["nhlScoreboard"],
      queryFn: getNHLScoreboard,
      Card: NHLGameCard,
      label: "NHL",
    },
  };
  const {
    queryKey,
    queryFn,
    Card: GameCard,
    label: sportLabel,
  } = sportConfig[sport] ?? sportConfig.nba;

  const {
    data: scoreboardData,
    isLoading,
    error,
    dataUpdatedAt,
  } = useQuery({
    queryKey,
    queryFn,
    staleTime: 30 * 1000,
    refetchInterval: (query) => {
      const games = query.state.data?.games ?? [];
      return games.some((g) => g.state === "in") ? 30 * 1000 : 60 * 1000;
    },
  });

  const { data: nowData } = useQuery({
    queryKey: ["sportsNow"],
    queryFn: getSportsNow,
    staleTime: 0,
    refetchInterval: 5000,
  });
  const activeEventIds = new Set(nowData?.active_event_ids ?? []);

  const games = scoreboardData?.games ?? [];
  const liveGames = games.filter((g) => g.state === "in");
  const scheduledGames = games.filter((g) => g.state === "pre");
  const finalGames = games.filter((g) => g.state === "post");

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <div>
      <SportsPageHeader
        sport={sport}
        isPending={modeMut.isPending}
        onSportChange={(nextSport) => modeMut.mutate({ sport: nextSport })}
        onOpenSettings={() => navigate("/sports/settings")}
      />

      <MatrixDisplayModeToggle
        displayMode={displayMode}
        isPending={modeMut.isPending}
        onChangeMode={(nextMode) => modeMut.mutate({ display_mode: nextMode })}
      />

      <div className="m-section-sub" style={{ marginBottom: 10 }}>
        {sportLabel} scoreboard{lastUpdated ? ` · updated ${lastUpdated}` : ""}
      </div>

      {isLoading && <div style={{ color: "#888", fontSize: "0.85rem" }}>Loading…</div>}
      {error && <div style={{ color: "#e05050", fontSize: "0.85rem" }}>Failed to load scores.</div>}

      {!isLoading && !error && games.length === 0 && (
        <div className="m-card" style={{ color: "#888", textAlign: "center", padding: "1.5rem" }}>
          No {sportLabel} games today
        </div>
      )}

      <GameSection
        title="Live"
        games={liveGames}
        GameCard={GameCard}
        favoriteTeams={favoriteTeams}
        activeEventIds={activeEventIds}
      />

      <GameSection
        title="Upcoming"
        showTopMargin={liveGames.length > 0}
        games={scheduledGames}
        GameCard={GameCard}
        favoriteTeams={favoriteTeams}
        activeEventIds={activeEventIds}
      />

      <GameSection
        title="Final"
        showTopMargin={liveGames.length > 0 || scheduledGames.length > 0}
        games={finalGames}
        GameCard={GameCard}
        favoriteTeams={favoriteTeams}
        activeEventIds={activeEventIds}
      />
    </div>
  );
}
