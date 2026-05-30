import React from "react";

export default function GameSection({ title, showTopMargin = false, games, GameCard, favoriteTeams, activeEventIds }) {
  if (!games.length) return null;

  return (
    <>
      <div className="m-card-title" style={{ marginBottom: 6, marginTop: showTopMargin ? 12 : 0 }}>
        {title}
      </div>
      {games.map((g, i) => (
        <GameCard key={i} game={g} favoriteTeams={favoriteTeams} activeEventIds={activeEventIds} />
      ))}
    </>
  );
}
