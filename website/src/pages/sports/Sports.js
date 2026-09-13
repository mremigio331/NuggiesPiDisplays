import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  getNBAScoreboard,
  getMLBScoreboard,
  getNHLScoreboard,
  getNFLScoreboard,
  getSoccerScoreboard,
  getSportsSettings,
  updateSportsSettings,
  getSportsNow,
  lockSportsGame,
  unlockSportsGame,
  clearSportsLocks,
} from "../../services/API";
import { favoritesForSport } from "../../utility/favorites";
import NBAGameCard from "../../components/sports/NBAGameCard";
import MLBGameCard from "../../components/sports/MLBGameCard";
import NHLGameCard from "../../components/sports/NHLGameCard";
import FootballGameCard from "../../components/sports/FootballGameCard";
import SoccerGameCard from "../../components/sports/SoccerGameCard";
import SportsPageHeader from "../../components/sports/SportsPageHeader";
import MatrixDisplayModeToggle from "../../components/sports/MatrixDisplayModeToggle";
import LockedGamesBanner from "../../components/sports/LockedGamesBanner";
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
  const soccerLeague = settings?.soccer_league ?? "fifa.world";
  // Favourites are per sport: ESPN team ids are reused across leagues
  const favoriteTeams = favoritesForSport(settings, sport);
  // Locks for the selected league; the API drops expired ones before we see them
  const lockedGames = (settings?.locked_games ?? []).filter(
    (lock) => !lock.sport || lock.sport === sport
  );
  const lockedIds = new Set(lockedGames.map((lock) => lock.event_id));

  const onSettingsSaved = (data) => qc.setQueryData(["sportsSettings"], data);

  const modeMut = useMutation({
    mutationFn: updateSportsSettings,
    onSuccess: onSettingsSaved,
  });

  // Every lock call returns the updated sports settings
  const lockMut = useMutation({
    mutationFn: ({ action, eventId }) => {
      if (action === "lock") return lockSportsGame(eventId, sport);
      if (action === "unlock") return unlockSportsGame(eventId);
      return clearSportsLocks();
    },
    onSuccess: onSettingsSaved,
  });

  // Leagues listed alphabetically
  const sportConfig = {
    mlb: {
      queryKey: ["mlbScoreboard"],
      queryFn: getMLBScoreboard,
      Card: MLBGameCard,
      label: "MLB",
    },
    nba: {
      queryKey: ["nbaScoreboard"],
      queryFn: getNBAScoreboard,
      Card: NBAGameCard,
      label: "NBA",
    },
    nfl: {
      queryKey: ["nflScoreboard"],
      queryFn: getNFLScoreboard,
      Card: FootballGameCard,
      label: "NFL",
    },
    nhl: {
      queryKey: ["nhlScoreboard"],
      queryFn: getNHLScoreboard,
      Card: NHLGameCard,
      label: "NHL",
    },
    soccer: {
      queryKey: ["soccerScoreboard", soccerLeague],
      queryFn: () => getSoccerScoreboard(soccerLeague),
      Card: SoccerGameCard,
      label: "FIFA World Cup",
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

  const gameControls = {
    lockedIds,
    isPending: modeMut.isPending || lockMut.isPending,
    onShowGame: (eventId) => modeMut.mutate({ force_event_id: eventId }),
    onLockGame: (eventId) => lockMut.mutate({ action: "lock", eventId }),
    onUnlockGame: (eventId) => lockMut.mutate({ action: "unlock", eventId }),
  };

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

      <LockedGamesBanner
        locks={lockedGames}
        games={games}
        isPending={gameControls.isPending}
        onUnlock={gameControls.onUnlockGame}
        onClearAll={() => lockMut.mutate({ action: "clear" })}
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
        {...gameControls}
      />

      <GameSection
        title="Upcoming"
        showTopMargin={liveGames.length > 0}
        games={scheduledGames}
        GameCard={GameCard}
        favoriteTeams={favoriteTeams}
        activeEventIds={activeEventIds}
        {...gameControls}
      />

      <GameSection
        title="Final"
        showTopMargin={liveGames.length > 0 || scheduledGames.length > 0}
        games={finalGames}
        GameCard={GameCard}
        favoriteTeams={favoriteTeams}
        activeEventIds={activeEventIds}
        {...gameControls}
      />
    </div>
  );
}
