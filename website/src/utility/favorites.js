/**
 * Favourite teams are stored per sport as ESPN team ids, because ids are only
 * unique inside a league (id 2 is the Red Sox, Celtics, Bills and Sabres).
 *
 * Abbreviations are matched too, so picks made before favourites moved to ids
 * keep working without a migration step.
 */
export function isFavoriteGame(game, favoriteTeams = []) {
  if (!favoriteTeams.length) return false;
  const keys = [game.home_id, game.away_id, game.home_team, game.away_team]
    .filter(Boolean)
    .map(String);
  return favoriteTeams.some((fav) => keys.includes(String(fav)));
}

/** Favourite ids for one sport from the settings payload. */
export function favoritesForSport(settings, sport) {
  const all = settings?.favorite_teams;
  if (Array.isArray(all)) return all; // legacy flat list
  return all?.[sport] ?? [];
}
