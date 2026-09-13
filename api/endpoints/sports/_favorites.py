"""Favourite teams, keyed by sport.

Stored as a dict of sport → list of ESPN team ids:

    "favorite_teams": { "nfl": ["8", "21"], "nba": ["2"] }

The nesting is required, not cosmetic: ESPN team ids are only unique inside a
league. Id 2 is the Red Sox in MLB, the Celtics in NBA, the Bills in NFL and the
Sabres in NHL, so a flat list would light up unrelated teams after switching
leagues.

Every read and write goes through normalise(), which guarantees a dict with a
list for the sport being touched — so adding or removing a team creates that
league's entry if it does not exist yet.
"""

MAX_ID_LEN = 32


def valid_team_id(value: str) -> bool:
    """ESPN team ids are short alphanumeric strings."""
    return bool(value) and value.isalnum() and len(value) <= MAX_ID_LEN


def _clean_ids(values) -> list[str]:
    """Unique, order-preserving list of valid ids."""
    if isinstance(values, (str, bytes)):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        # Only ids: str(None) would otherwise sneak in as "NONE"
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            continue
        team_id = str(value).strip().upper()
        if valid_team_id(team_id) and team_id not in seen:
            seen.add(team_id)
            cleaned.append(team_id)
    return cleaned


def normalise(favorites, current_sport: str = "") -> dict[str, list[str]]:
    """Coerce any stored shape into {sport: [team_id, …]}.

    A legacy flat list (abbreviations from before favourites were keyed by
    sport) is kept under the sport that is currently selected, so existing
    picks stay meaningful instead of silently applying to every league.
    """
    if isinstance(favorites, dict):
        return {
            str(sport): _clean_ids(ids)
            for sport, ids in favorites.items()
            if str(sport)
        }
    legacy = _clean_ids(favorites)
    return {current_sport: legacy} if legacy and current_sport else {}


def read_all(sports: dict) -> dict[str, list[str]]:
    """Every sport's favourites, normalised."""
    return normalise(sports.get("favorite_teams"), sports.get("sport", ""))


def read(sports: dict, sport: str) -> list[str]:
    """Favourite team ids for one sport (empty list when none)."""
    return read_all(sports).get(sport, [])


def write(sports: dict, favorites: dict[str, list[str]]) -> dict[str, list[str]]:
    sports["favorite_teams"] = favorites
    return favorites


def set_for(sports: dict, sport: str, team_ids) -> dict[str, list[str]]:
    """Replace one sport's favourites, creating the entry when missing."""
    favorites = read_all(sports)
    favorites[sport] = _clean_ids(team_ids)
    return write(sports, favorites)


def add(sports: dict, sport: str, team_id: str) -> dict[str, list[str]]:
    """Add a team to a sport's favourites, creating the entry when missing."""
    favorites = read_all(sports)
    current = favorites.setdefault(sport, [])
    team_id = str(team_id).strip().upper()
    if team_id not in current:
        current.append(team_id)
    return write(sports, favorites)


def remove(sports: dict, sport: str, team_id: str) -> dict[str, list[str]]:
    """Remove a team from a sport's favourites, keeping the entry in place."""
    favorites = read_all(sports)
    team_id = str(team_id).strip().upper()
    favorites[sport] = [t for t in favorites.setdefault(sport, []) if t != team_id]
    return write(sports, favorites)
