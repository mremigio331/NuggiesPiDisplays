import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  getNBAScoreboard,
  getWNBAScoreboard,
  getMLBScoreboard,
  getNHLScoreboard,
  getNFLScoreboard,
  getNCAAFScoreboard,
  getNWSLScoreboard,
  getEPLScoreboard,
  getLaLigaScoreboard,
  getBundesligaScoreboard,
  getFavoritesScoreboard,
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
import FavoriteGameSection from "../../components/sports/FavoriteGameSection";

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

  // Leagues listed alphabetically. "favorites" is a cross-league feed, not a
  // real league — it has no single GameCard (each game uses its own) and no
  // locks, so it is handled specially below.
  const sportConfig = {
    favorites: {
      queryKey: ["favoritesScoreboard"],
      queryFn: getFavoritesScoreboard,
      label: "Favorites",
      aggregated: true,
    },
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
    // WNBA reuses NBAGameCard — the basketball scoreboard payload is identical
    wnba: {
      queryKey: ["wnbaScoreboard"],
      queryFn: getWNBAScoreboard,
      Card: NBAGameCard,
      label: "WNBA",
    },
    nfl: {
      queryKey: ["nflScoreboard"],
      queryFn: getNFLScoreboard,
      Card: FootballGameCard,
      label: "NFL",
    },
    // NCAAF reuses FootballGameCard — college football shares NFL's payload shape
    ncaaf: {
      queryKey: ["ncaafScoreboard"],
      queryFn: getNCAAFScoreboard,
      Card: FootballGameCard,
      label: "NCAA Football",
    },
    nhl: {
      queryKey: ["nhlScoreboard"],
      queryFn: getNHLScoreboard,
      Card: NHLGameCard,
      label: "NHL",
    },
    nwsl: {
      queryKey: ["nwslScoreboard"],
      queryFn: getNWSLScoreboard,
      Card: SoccerGameCard,
      label: "NWSL",
    },
    // European soccer leagues all share SoccerGameCard — same payload shape
    epl: {
      queryKey: ["eplScoreboard"],
      queryFn: getEPLScoreboard,
      Card: SoccerGameCard,
      label: "Premier League",
    },
    laliga: {
      queryKey: ["laligaScoreboard"],
      queryFn: getLaLigaScoreboard,
      Card: SoccerGameCard,
      label: "La Liga",
    },
    bundesliga: {
      queryKey: ["bundesligaScoreboard"],
      queryFn: getBundesligaScoreboard,
      Card: SoccerGameCard,
      label: "Bundesliga",
    },
  };
  const activeConfig = sportConfig[sport] ?? sportConfig.nba;
  const {
    queryKey,
    queryFn,
    Card: GameCard,
    label: sportLabel,
    aggregated,
  } = activeConfig;

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

  // Section renderer differs for the mixed-league favourites feed: each game is
  // drawn with its own sport's card and highlighted with its league's
  // favourites. Real leagues use the single-sport GameSection.
  const renderSection = (title, sectionGames, showTopMargin = false) => {
    if (aggregated) {
      return (
        <FavoriteGameSection
          title={title}
          showTopMargin={showTopMargin}
          games={sectionGames}
          settings={settings}
          activeEventIds={activeEventIds}
          lockedIds={lockedIds}
          isPending={gameControls.isPending}
          onShowGame={gameControls.onShowGame}
          onLockGame={gameControls.onLockGame}
          onUnlockGame={gameControls.onUnlockGame}
        />
      );
    }
    return (
      <GameSection
        title={title}
        showTopMargin={showTopMargin}
        games={sectionGames}
        GameCard={GameCard}
        favoriteTeams={favoriteTeams}
        activeEventIds={activeEventIds}
        {...gameControls}
      />
    );
  };

  return (
    <div>
      <SportsPageHeader
        sport={sport}
        isPending={modeMut.isPending}
        onSportChange={(nextSport) => modeMut.mutate({ sport: nextSport })}
        onOpenSettings={() => navigate("/sports/settings")}
      />

      {/* Overview/focus and locks apply to a single league's slate, not the
          mixed favourites feed, so they are hidden for favourites. */}
      {!aggregated && (
        <>
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
        </>
      )}

      <div className="m-section-sub" style={{ marginBottom: 10 }}>
        {sportLabel} scoreboard{lastUpdated ? ` · updated ${lastUpdated}` : ""}
      </div>

      {isLoading && <div style={{ color: "#888", fontSize: "0.85rem" }}>Loading…</div>}
      {error && <div style={{ color: "#e05050", fontSize: "0.85rem" }}>Failed to load scores.</div>}

      {!isLoading && !error && games.length === 0 && (
        <div className="m-card" style={{ color: "#888", textAlign: "center", padding: "1.5rem" }}>
          {aggregated
            ? "No games today for your favorite teams. Pick teams in Settings."
            : `No ${sportLabel} games today`}
        </div>
      )}

      {renderSection("Live", liveGames)}
      {renderSection("Upcoming", scheduledGames, liveGames.length > 0)}
      {renderSection(
        "Final",
        finalGames,
        liveGames.length > 0 || scheduledGames.length > 0
      )}
    </div>
  );
}
