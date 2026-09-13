import React from "react";
import GameControls from "./GameControls";

export default function GameSection({
  title,
  showTopMargin = false,
  games,
  GameCard,
  favoriteTeams,
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
      {games.map((g, i) => (
        <div key={g.event_id ?? i}>
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
      ))}
    </>
  );
}
