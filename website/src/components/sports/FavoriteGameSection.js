import React from "react";
import GameControls from "./GameControls";
import { cardForSport, SPORT_LABELS } from "./sportCards";
import { favoritesForSport } from "../../utility/favorites";

/**
 * Renders a mixed-league list of favourite games. Each game is drawn with the
 * card for its own `sport` tag and highlighted using that league's favourite
 * ids (ESPN ids are only unique within a league, so highlighting must be keyed
 * by sport too). A small league badge keeps the mixed feed legible.
 */
export default function FavoriteGameSection({
  title,
  showTopMargin = false,
  games,
  settings,
  activeEventIds,
  lockedIds,
  isPending,
  onShowGame,
  onLockGame,
  onUnlockGame,
}) {
  if (!games.length) return null;

  return (
    <>
      <div className="m-card-title" style={{ marginBottom: 6, marginTop: showTopMargin ? 12 : 0 }}>
        {title}
      </div>
      {games.map((g, i) => {
        const sport = g.sport;
        const GameCard = cardForSport(sport);
        const favoriteTeams = favoritesForSport(settings, sport);
        return (
          <div key={g.event_id ?? i}>
            <div
              style={{
                fontSize: "0.7rem",
                color: "#888",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: 2,
              }}
            >
              {SPORT_LABELS[sport] ?? sport}
            </div>
            <GameCard game={g} favoriteTeams={favoriteTeams} activeEventIds={activeEventIds} />
            <GameControls
              isLocked={lockedIds?.has(g.event_id)}
              isOnMatrix={activeEventIds?.has(g.event_id)}
              isPending={isPending}
              onShow={() => onShowGame(g.event_id)}
              onLock={() => onLockGame(g.event_id)}
              onUnlock={() => onUnlockGame(g.event_id)}
            />
          </div>
        );
      })}
    </>
  );
}
