import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

_ESPN_BASE = "http://site.api.espn.com/apis/site/v2/sports"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# sport key → ESPN league path.
ESPN_LEAGUE_PATHS: dict[str, str] = {
    "mlb": "baseball/mlb",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "nhl": "hockey/nhl",
    # Soccer leagues are each their own sport key → ESPN "soccer/<slug>" path.
    # Keep in sync with SOCCER_SPORTS in api/endpoints/sports/soccer.py.
    "nwsl": "soccer/usa.nwsl",
    "epl": "soccer/eng.1",
    "laliga": "soccer/esp.1",
    "bundesliga": "soccer/ger.1",
}

# NHL penalty play detection. ESPN's play-by-play has no single "Penalty"
# type.text — each infraction gets its own label ("Tripping", "Fighting",
# "Unsportsmanlike Conduct", …). Rather than enumerate every penalty name
# (there are dozens and ESPN adds new ones), we match on the shared signature
# of every penalty play's text: "<player> <infraction> against <opponent>".
# Goals, hits, shots, etc. never use that "against" phrasing, so this reliably
# isolates penalties without a brittle name list.
_NHL_PENALTY_RE = re.compile(r"\bagainst\b", re.IGNORECASE)
# Play type ids that use "against" but are NOT penalties (none today, but
# Hit text can read "... hit against ..."). Hits carry their own type id 503,
# so we exclude known non-penalty gameplay type ids explicitly.
_NHL_NON_PENALTY_TYPE_IDS = {
    "502",  # Face Off
    "503",  # Hit
    "505",  # Goal
    "506",  # Shot
    "507",  # Missed
    "508",  # Blocked
    "516",  # Stoppage
    "518",  # Period Start
    "519",  # Period End
    "1401",  # Takeaway
    "1402",  # Giveaway
}


def _parse_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _to_int(val) -> int:
    """Coerce anything numeric-ish (incl. '12.0' / 12.0) to int, else 0."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


_NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def _last_name(display_name: str) -> str:
    """Extract last name from a full display name, e.g. 'Aaron Judge' → 'Judge'.

    Generational suffixes are skipped so 'Devin Neal Jr.' → 'Neal'.
    """
    if not display_name:
        return ""
    parts = [p for p in display_name.strip().split() if p]
    while len(parts) > 1 and parts[-1].lower() in _NAME_SUFFIXES:
        parts.pop()
    return parts[-1] if parts else ""


_PITCH_TYPE_MAP: dict[str, str] = {
    "ball": "B",
    "intentional ball": "B",
    "called strike": "S",
    "swinging strike": "S",
    "foul": "F",
    "foul tip": "F",
    "foul bunt": "F",
    # "hit by pitch" omitted — it ends the at-bat
}

# Events that happen mid-at-bat but aren't pitches: skip without stopping the search.
_BETWEEN_PLAY_FRAGMENTS = (
    "substitution",
    "pitching change",
    "runner advance",
    "runner scores",
    "stolen base",
    "caught stealing",
    "wild pitch",
    "passed ball",
    "balk",
    "pickoff",
    "challenge",
    "review",
    "ejection",
    "delay",
    "mound visit",
)


# ── Football (NFL / NCAA) parsing tables ──────────────────────────────────────
# Shared by every football league — ESPN uses the same stat names for NFL and
# college football, so adding a league needs no changes here.

_FOOTBALL_TEAM_STATS: dict[str, str] = {
    "totalYards": "yards",
    "netPassingYards": "pass_yards",
    "rushingYards": "rush_yards",
    "turnovers": "turnovers",
    "firstDowns": "first_downs",
    "thirdDownEff": "third_down",
    "totalPenaltiesYards": "penalties",
    "sacksYardsLost": "sacks",
    "completionAttempts": "comp_att",
    "possessionTime": "possession_time",
    "redZoneAttempts": "red_zone",
}

_FOOTBALL_LEADER_CATS: dict[str, str] = {
    "passingYards": "passing",
    "rushingYards": "rushing",
    "receivingYards": "receiving",
}

_LEADER_TD_RE = re.compile(r"(\d+)\s*TD")
_LEADER_INT_RE = re.compile(r"(\d+)\s*INT")

# Scoring-play labels matched against type.text
_FOOTBALL_SCORE_TYPES: tuple[tuple[str, str], ...] = (
    ("touchdown", "TD"),
    ("field goal", "FG"),
    ("safety", "SF"),
    ("two-point", "2P"),
    ("extra point", "XP"),
)

# …and by points scored, for plays ESPN labels oddly (e.g. a fumble-return
# touchdown typed "Sack Opp Fumble Recovery", abbreviation "SFOP").
_FOOTBALL_SCORE_BY_POINTS: dict[int, str] = {
    8: "TD",
    7: "TD",
    6: "TD",
    3: "FG",
    1: "XP",
}


def _match_int(pattern: re.Pattern, text: str) -> int:
    """First integer captured by pattern in text, else 0."""
    match = pattern.search(text or "")
    return _to_int(match.group(1)) if match else 0


def _football_rank(competitor: dict) -> int | None:
    """AP top-25 rank for a competitor, or None when unranked.

    ESPN reports the ranking as competitor.curatedRank.current; 99 (and 0) mean
    unranked. Only 1–25 count as ranked.
    """
    rank = _to_int((competitor.get("curatedRank") or {}).get("current"))
    return rank if 1 <= rank <= 25 else None


def _football_score_type(ptype: dict, points: int) -> str:
    """Compact 2-char scoring-play label, e.g. 'TD', 'FG', 'SF'."""
    text = (ptype.get("text") or "").lower()
    for fragment, label in _FOOTBALL_SCORE_TYPES:
        if fragment in text:
            return label
    label = _FOOTBALL_SCORE_BY_POINTS.get(points)
    if label:
        return label
    abbr = (ptype.get("abbreviation") or "").strip().upper()
    return (abbr or text.upper())[:2]


def _resolve_team_colors(
    team: dict, color_map: dict[str, dict[str, str]] | None
) -> tuple[str, str]:
    """Return (color, alt_color) for a scoreboard team.

    ESPN's scoreboard payload often omits one or both colors (notably the NHL
    scoreboard, which returns no alternates at all). We prefer the scoreboard's
    own value, fall back to the teams-endpoint ``color_map`` keyed by team id,
    and finally to a readable literal default so a row always has usable colors.
    """
    tid = str(team.get("id") or "")
    mapped = (color_map or {}).get(tid, {})
    color = team.get("color") or mapped.get("color") or "003366"
    alt = team.get("alternateColor") or mapped.get("alt_color") or "ffffff"
    return color, alt


def _parse_base_game(
    event: dict,
    home: dict,
    away: dict,
    stype: dict,
    status: dict,
    color_map: dict[str, dict[str, str]] | None = None,
) -> dict:
    """Fields common to every sport's scoreboard game entry.

    ``color_map`` (team_id -> {"color", "alt_color"}) fills in colors the
    scoreboard omits; see _team_color_map / _resolve_team_colors.
    """
    home_color, home_alt = _resolve_team_colors(home["team"], color_map)
    away_color, away_alt = _resolve_team_colors(away["team"], color_map)
    return {
        "event_id": event.get("id", ""),
        "home_team": home["team"].get("abbreviation", ""),
        "away_team": away["team"].get("abbreviation", ""),
        # ESPN team ids are unique within a league but reused across leagues
        # (id 2 is the Red Sox, Celtics, Bills and Sabres), so anything keyed by
        # team id must also be keyed by sport.
        "home_id": str(home["team"].get("id", "")),
        "away_id": str(away["team"].get("id", "")),
        "home_score": int(home.get("score") or 0),
        "away_score": int(away.get("score") or 0),
        "home_color": home_color,
        "away_color": away_color,
        "home_alt_color": home_alt,
        "away_alt_color": away_alt,
        "status": stype.get("description", "Scheduled"),
        "status_detail": stype.get("shortDetail", ""),
        "period": status.get("period", 0),
        "state": stype.get("state", "pre"),
        "game_date": event.get("date", ""),
    }


def _parse_possession(situation: dict, home_id: str, away_id: str) -> str | None:
    """Return "home" | "away" | None from a live competition situation block.

    ESPN reports the team with the ball either as situation.possession (a team
    id string) or as situation.team.id, depending on the sport.
    """
    poss_id = str(
        situation.get("possession") or (situation.get("team") or {}).get("id") or ""
    )
    if not poss_id:
        return None
    if poss_id == home_id:
        return "home"
    if poss_id == away_id:
        return "away"
    return None


def _line_scores(competitor: dict) -> list[int]:
    """Per-period scores for one competitor, e.g. [7, 10, 0, 3]."""
    return [_to_int(ls.get("value")) for ls in competitor.get("linescores") or []]


def _build_home_away_map(raw: dict) -> dict[str, str]:
    """Map team_id → 'home'|'away' from the ESPN summary header."""
    header_comp = (raw.get("header", {}).get("competitions") or [{}])[0]
    result: dict[str, str] = {}
    for comp_team in header_comp.get("competitors", []):
        tid = comp_team.get("team", {}).get("id")
        if tid:
            result[tid] = comp_team.get("homeAway", "away")
    return result


class ESPNClient:
    """Thin wrapper around the unofficial ESPN public scoreboard API."""

    def __init__(self, cache_ttl: int = 30):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._ttl = cache_ttl
        # Per-sport parsed team-color maps (see _team_color_map). Memoised for
        # the client's lifetime since team colors are effectively static.
        self._color_maps: dict[str, dict[str, dict[str, str]]] = {}
        # Per-team overall record (see get_team_record), memoised for the
        # client's lifetime — records change at most once per game.
        self._record_cache: dict[str, str] = {}

    def _get(self, url: str) -> dict:
        cached = self._cache.get(url)
        if cached and (time.time() - cached[0]) < self._ttl:
            return cached[1]
        resp = requests.get(url, timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        self._cache[url] = (time.time(), data)
        return data

    # ── Teams ──────────────────────────────────────────────────────────────

    def get_teams(self, sport: str) -> list[dict]:
        """Return every team in a league, for favourite-team pickers.

        Team ids are only unique within a league, so callers must keep the
        sport alongside any id they store.
        """
        league_path = ESPN_LEAGUE_PATHS.get(sport, "")
        if not league_path:
            logger.error(f"No ESPN league path for sport {sport!r}")
            return []

        # ESPN defaults the teams list to 50 per page. Big leagues blow past
        # that — college football alone returns ~760 teams across divisions —
        # so request a large page to get the full roster in one call. Smaller
        # leagues just return everything they have. The web picker then filters
        # this list client-side (search), so there is no further paging.
        url = f"{_ESPN_BASE}/{league_path}/teams?limit=1000"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN teams fetch failed for {sport}: {e}")
            return []

        try:
            leagues = (raw.get("sports") or [{}])[0].get("leagues") or [{}]
            entries = leagues[0].get("teams") or []
        except (IndexError, AttributeError):
            return []

        teams = []
        for entry in entries:
            team = entry.get("team") or {}
            team_id = str(team.get("id") or "")
            if not team_id or team.get("isAllStar"):
                continue
            teams.append(
                {
                    "id": team_id,
                    "abbreviation": team.get("abbreviation") or "",
                    "name": team.get("displayName") or "",
                    "short_name": team.get("shortDisplayName") or "",
                    "color": team.get("color") or "",
                    "alt_color": team.get("alternateColor") or "",
                }
            )
        teams.sort(key=lambda t: t["abbreviation"] or t["name"])
        return teams

    def get_team_schedule(self, sport: str, team_id: str) -> list[dict]:
        """Every game on one team's schedule, oldest first, in scoreboard shape.

        Used by the favourites feed, which needs each favourited team's *last*
        completed game and its *next* (or live) game — information the daily
        scoreboard cannot give, since it only knows about today's slate.

        ESPN's ``teams/{id}/schedule`` endpoint returns the whole season of
        events (past with final scores, future scheduled). Each event carries
        the same ``competitions``/``competitors`` structure as the scoreboard,
        so every game is parsed through :func:`_parse_base_game` and comes out
        in the identical dict shape the renderers already consume (team abbrs,
        ids, scores, colors, state, ``game_date``). Returns ``[]`` for an
        unknown sport or on any fetch/parse failure — one team's schedule gap
        must never sink the whole favourites feed.
        """
        league_path = ESPN_LEAGUE_PATHS.get(sport, "")
        if not league_path:
            logger.error(f"No ESPN league path for sport {sport!r}")
            return []

        url = f"{_ESPN_BASE}/{league_path}/teams/{team_id}/schedule"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN schedule fetch failed for {sport} team {team_id}: {e}")
            return []

        color_map = self._team_color_map(league_path)
        games: list[dict] = []
        for event in raw.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            status = comp.get("status", {})
            stype = status.get("type", {})

            # On the schedule endpoint a competitor's `score` is a dict
            # ({"value": 24.0, "displayValue": "24"}) rather than the plain
            # number the scoreboard returns. Flatten it to the numeric value so
            # _parse_base_game's int(score) works for both shapes; an upcoming
            # game has no score, which becomes 0.
            def _flatten_score(competitor: dict) -> dict:
                score = competitor.get("score")
                if isinstance(score, dict):
                    return {**competitor, "score": score.get("value") or 0}
                return competitor

            game = _parse_base_game(
                event,
                _flatten_score(home),
                _flatten_score(away),
                stype,
                status,
                color_map,
            )
            # Schedule events don't carry a live clock; set empty so renderers
            # that read game["clock"] behave the same as for a pre/post game.
            game["clock"] = status.get("displayClock", "")
            games.append(game)

        # Oldest first so "last completed" and "next upcoming" are easy to pick
        # by scanning from the ends.
        games.sort(key=lambda g: g.get("game_date", ""))
        return games

    def get_team_record(self, sport: str, team_id: str) -> str:
        """The team's overall win-loss record, e.g. '4-2' (empty when unknown).

        The schedule endpoint's upcoming games carry no records, so the
        favourites feed fetches them here from ESPN's ``teams/{id}`` endpoint
        (``team.record.items`` → the entry typed ``total``). Records change at
        most once per game, so each team's record is memoised per client for the
        life of the process; the schedule client already uses a long TTL on the
        underlying HTTP cache too.
        """
        league_path = ESPN_LEAGUE_PATHS.get(sport, "")
        if not league_path:
            return ""
        cache_key = f"{league_path}/{team_id}"
        cached = self._record_cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{_ESPN_BASE}/{league_path}/teams/{team_id}"
        record = ""
        try:
            raw = self._get(url)
            items = ((raw.get("team") or {}).get("record") or {}).get("items") or []
            # Prefer the 'total' record; fall back to the first item.
            total = next((i for i in items if i.get("type") == "total"), None)
            record = (total or (items[0] if items else {})).get("summary", "") or ""
        except Exception as e:
            logger.error(f"ESPN record fetch failed for {sport} team {team_id}: {e}")
            record = ""
        self._record_cache[cache_key] = record
        return record

    def get_summary_leaders(self, sport: str, event_id: str) -> dict:
        """Per-team stat leaders for one game, as ESPN provides them.

        Reads the game summary's ``leaders`` block, which ESPN populates with
        SEASON leaders even for an upcoming (not-yet-played) game — so the
        favourites feed can show "who leads each team" for a future matchup. The
        categories are whatever ESPN returns for that sport (NHL: goals/assists/
        points; football: passingYards/rushingYards/receivingYards/sacks/
        tackles; etc.), NOT a hardcoded per-sport list — we take what we are
        given, in order, capped at 4.

        Returns ``{"home": [...], "away": [...]}`` where each entry is
        ``{"category", "label", "name", "value"}`` (``name`` is the player's
        last name, ``value`` the display value). Sides are resolved from the
        summary header's home/away map. Empty lists when there are no leaders
        (e.g. early season) or on any failure — the caller then shows nothing.
        """
        league_path = ESPN_LEAGUE_PATHS.get(sport, "")
        if not league_path or not event_id:
            return {"home": [], "away": []}

        url = f"{_ESPN_BASE}/{league_path}/summary?event={event_id}"
        result: dict = {"home": [], "away": []}
        try:
            raw = self._get(url)
            home_away = _build_home_away_map(raw)  # team_id -> "home"|"away"
            for team_block in raw.get("leaders") or []:
                tid = str((team_block.get("team") or {}).get("id") or "")
                side = home_away.get(tid)
                if side not in ("home", "away"):
                    continue
                entries: list[dict] = []
                for cat in (team_block.get("leaders") or [])[:4]:
                    leader = (cat.get("leaders") or [{}])[0]
                    athlete = leader.get("athlete") or {}
                    name = (
                        athlete.get("lastName")
                        or _last_name(athlete.get("displayName", ""))
                        or athlete.get("shortName", "")
                    )
                    entries.append(
                        {
                            "category": cat.get("name", ""),
                            "label": (cat.get("displayName") or cat.get("name") or ""),
                            "name": name,
                            "value": str(leader.get("displayValue", "") or ""),
                        }
                    )
                result[side] = entries
        except Exception as e:
            logger.error(f"ESPN leaders fetch failed for {sport} event {event_id}: {e}")
            return {"home": [], "away": []}
        return result

    def _team_color_map(self, league_path: str) -> dict[str, dict[str, str]]:
        """Map ``team_id -> {"color", "alt_color"}`` for an ESPN league path.

        ``league_path`` is the ESPN path segment (e.g. "hockey/nhl",
        "soccer/eng.1", "football/college-football") so this works for every
        sport, including the ones whose scoreboard methods take an ESPN league
        slug rather than our internal sport key.

        ESPN's scoreboard feed frequently omits ``alternateColor`` (and
        occasionally ``color``) — the NHL scoreboard returns ``None`` for every
        team's alternate — while the teams endpoint always carries both. We use
        this map to fill those gaps so secondary colors render correctly.

        Team colors effectively never change within a season, so the parsed map
        is memoised per league for the life of the client. A failed teams fetch
        caches an empty map so a flaky call doesn't retry on every scoreboard
        poll; the scoreboard's own values (and literal fallbacks) still apply.
        """
        cached = self._color_maps.get(league_path)
        if cached is not None:
            return cached

        color_map: dict[str, dict[str, str]] = {}
        # ESPN caps the teams list at 50/page by default; college football alone
        # has ~760, so request a large page to get the whole league in one call.
        url = f"{_ESPN_BASE}/{league_path}/teams?limit=1000"
        try:
            raw = self._get(url)
            leagues = (raw.get("sports") or [{}])[0].get("leagues") or [{}]
            entries = leagues[0].get("teams") or []
        except Exception as e:
            logger.error(f"ESPN team-color map fetch failed for {league_path}: {e}")
            entries = []

        for entry in entries:
            team = entry.get("team") or {}
            tid = str(team.get("id") or "")
            if not tid:
                continue
            color_map[tid] = {
                "color": team.get("color") or "",
                "alt_color": team.get("alternateColor") or "",
            }
        self._color_maps[league_path] = color_map
        return color_map

    def _get_basketball_scoreboard(self, league: str) -> list[dict]:
        """Return today's games for a basketball league (nba, wnba).

        NBA and WNBA share identical ESPN payload shapes, so both leagues use
        this helper — only the league slug (e.g. "basketball/nba") differs.
        """
        url = f"{_ESPN_BASE}/basketball/{league}/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN {league.upper()} fetch failed: {e}")
            return []

        color_map = self._team_color_map(f"basketball/{league}")
        games = []
        for event in raw.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            status = comp.get("status", {})
            stype = status.get("type", {})
            state = stype.get("state", "pre")  # "pre" | "in" | "post"

            situation = comp.get("situation") or {}
            possession = _parse_possession(
                situation,
                str(home["team"].get("id", "")),
                str(away["team"].get("id", "")),
            )

            game = _parse_base_game(event, home, away, stype, status, color_map)
            game["clock"] = status.get("displayClock", "")
            game["possession"] = possession
            games.append(game)

        return games

    def get_nba_scoreboard(self) -> list[dict]:
        """Return today's NBA games in a simplified format."""
        return self._get_basketball_scoreboard("nba")

    def get_wnba_scoreboard(self) -> list[dict]:
        """Return today's WNBA games in a simplified format."""
        return self._get_basketball_scoreboard("wnba")

    def _get_basketball_game_details(self, league: str, event_id: str) -> dict | None:
        """Return boxscore player data for a basketball game (nba, wnba).

        Returns a dict with keys "away" and "home", each containing:
          - abbreviation: str
          - team_fouls: int (sum of all player PF)
          - players: list of {jersey, points, fouls} sorted by points desc
        """
        url = f"{_ESPN_BASE}/basketball/{league}/summary?event={event_id}"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN game details fetch failed for {event_id}: {e}")
            return None

        try:
            home_away_map = _build_home_away_map(raw)
            boxscore = raw.get("boxscore", {})
            players_data = boxscore.get("players", [])

            result: dict[str, dict] = {}

            for team_data in players_data:
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                abbr = team.get("abbreviation", "???")
                home_away = home_away_map.get(tid, "away")

                stats_groups = team_data.get("statistics", [])
                if not stats_groups:
                    continue

                stats_group = stats_groups[0]
                labels = stats_group.get("labels", [])

                def _idx(name: str) -> int:
                    return labels.index(name) if name in labels else -1

                pts_idx = _idx("PTS")
                ast_idx = _idx("AST")
                reb_idx = _idx("REB")
                pf_idx = _idx("PF")

                def _stat(stats: list, idx: int) -> int:
                    return _parse_int(stats[idx]) if 0 <= idx < len(stats) else 0

                players: list[dict] = []
                team_fouls = 0

                for entry in stats_group.get("athletes", []):
                    athlete = entry.get("athlete", {})
                    if not athlete.get("active", True):
                        continue
                    stats = entry.get("stats", [])
                    pf = _stat(stats, pf_idx)
                    team_fouls += pf
                    players.append(
                        {
                            "jersey": athlete.get("jersey", "?"),
                            "name": athlete.get("displayName", ""),
                            "points": _stat(stats, pts_idx),
                            "assists": _stat(stats, ast_idx),
                            "rebounds": _stat(stats, reb_idx),
                            "fouls": pf,
                        }
                    )

                players.sort(key=lambda p: p["points"], reverse=True)

                result[home_away] = {
                    "abbreviation": abbr,
                    "team_fouls": team_fouls,
                    "players": players,
                }

            return result if result else None

        except Exception as e:
            logger.error(f"Failed to parse game details for {event_id}: {e}")
            return None

    def get_nba_game_details(self, event_id: str) -> dict | None:
        """Return NBA boxscore player data for a specific game."""
        return self._get_basketball_game_details("nba", event_id)

    def get_wnba_game_details(self, event_id: str) -> dict | None:
        """Return WNBA boxscore player data for a specific game."""
        return self._get_basketball_game_details("wnba", event_id)

    # ── MLB ────────────────────────────────────────────────────────────────

    def get_mlb_scoreboard(self) -> list[dict]:
        """Return today's MLB games with live situation data."""
        url = f"{_ESPN_BASE}/baseball/mlb/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN MLB fetch failed: {e}")
            return []

        color_map = self._team_color_map("baseball/mlb")
        games = []
        for event in raw.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            status = comp.get("status", {})
            stype = status.get("type", {})
            state = stype.get("state", "pre")
            short_detail = stype.get("shortDetail", "")

            sd = short_detail.lower()
            if "top" in sd:
                inning_half = "top"
            elif "bot" in sd or "bottom" in sd:
                inning_half = "bot"
            else:
                inning_half = None

            situation = comp.get("situation") or {}

            def _jersey(key: str) -> str:
                return (situation.get(key) or {}).get("athlete", {}).get("jersey", "?")

            def _sit_stat(key: str, stat: str) -> str:
                for s in (situation.get(key) or {}).get("statistics", []):
                    if s.get("name") == stat:
                        return s.get("displayValue", "")
                return ""

            def _sit_name(key: str) -> str:
                return _last_name(
                    (situation.get(key) or {}).get("athlete", {}).get("displayName", "")
                )

            game = _parse_base_game(event, home, away, stype, status, color_map)
            game.update(
                {
                    "inning_half": inning_half,
                    "balls": situation.get("balls"),
                    "strikes": situation.get("strikes"),
                    "outs": situation.get("outs"),
                    "on_first": bool(situation.get("onFirst")),
                    "on_second": bool(situation.get("onSecond")),
                    "on_third": bool(situation.get("onThird")),
                    "batter_jersey": _jersey("batter"),
                    "batter_avg": _sit_stat("batter", "battingAverage"),
                    "batter_name": _sit_name("batter"),
                    "pitcher_jersey": _jersey("pitcher"),
                    "pitcher_era": _sit_stat("pitcher", "ERA"),
                    "pitcher_name": _sit_name("pitcher"),
                }
            )
            games.append(game)

        return games

    # ── NHL ────────────────────────────────────────────────────────────────

    def get_nhl_scoreboard(self) -> list[dict]:
        """Return today's NHL games in simplified format."""
        url = f"{_ESPN_BASE}/hockey/nhl/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN NHL fetch failed: {e}")
            return []

        color_map = self._team_color_map("hockey/nhl")
        games = []
        for event in raw.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            status = comp.get("status", {})
            stype = status.get("type", {})
            game = _parse_base_game(event, home, away, stype, status, color_map)
            game["clock"] = status.get("displayClock", "")
            games.append(game)
        return games

    def get_nhl_game_details(self, event_id: str) -> dict | None:
        """Return team stats (SOG/hits/blocks), goal scorers, on-ice players,
        per-side skater stat lines (goals/assists/hits), and ordered scoring
        and penalty lists (player name + period)."""
        url = f"{_ESPN_BASE}/hockey/nhl/summary?event={event_id}"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN NHL game details fetch failed for {event_id}: {e}")
            return None

        try:
            home_away_map = _build_home_away_map(raw)
            result: dict = {
                "home": {},
                "away": {},
                "goals": [],
                "scoring": [],
                "penalties": [],
            }

            # Build player_map: athlete_id str → {jersey, name, team_id} and
            # collect per-side skater stat lines (name + goals/assists/hits) for
            # the leader-board panels. Skaters appear in the "forwards" and
            # "defenses" statistic groups; goalies are a separate group we skip.
            player_map: dict[str, dict] = {}
            skaters: dict[str, list[dict]] = {"home": [], "away": []}
            for team_data in raw.get("boxscore", {}).get("players") or []:
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                side = home_away_map.get(tid, "away")
                for stats_group in team_data.get("statistics", []):
                    group = (stats_group.get("name") or "").lower()
                    labels = stats_group.get("labels") or []
                    is_skater_group = group in ("forwards", "defenses", "skaters")

                    def _col(label: str) -> int:
                        return labels.index(label) if label in labels else -1

                    g_idx = _col("G")
                    a_idx = _col("A")
                    h_idx = _col("HT")

                    for entry in stats_group.get("athletes", []):
                        athlete = entry.get("athlete", {})
                        aid = str(athlete.get("id", ""))
                        name = athlete.get("displayName", "")
                        if aid:
                            player_map[aid] = {
                                "jersey": athlete.get("jersey", "?"),
                                "name": name,
                                "team_id": tid,
                            }
                        if not is_skater_group:
                            continue
                        stats = entry.get("stats", [])

                        def _val(idx: int) -> int:
                            if 0 <= idx < len(stats):
                                return _parse_int(stats[idx])
                            return 0

                        skaters[side].append(
                            {
                                "jersey": athlete.get("jersey", "?"),
                                "name": name,
                                "goals": _val(g_idx),
                                "assists": _val(a_idx),
                                "hits": _val(h_idx),
                            }
                        )

            # Team stats from boxscore.teams
            # ESPN NHL uses "shotsTotal" (not "shotsOnGoal")
            _STAT_MAP = {
                "shotsTotal": "shots",
                "shotsOnGoal": "shots",  # fallback in case name differs
                "hits": "hits",
                "blockedShots": "blocks",
            }
            tid_to_abbr: dict[str, str] = {}
            for team_data in raw.get("boxscore", {}).get("teams") or []:
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                abbr = team.get("abbreviation", "???")
                tid_to_abbr[tid] = abbr
                side = home_away_map.get(tid, "away")
                result[side]["abbreviation"] = abbr
                stats: dict[str, int] = {"shots": 0, "hits": 0, "blocks": 0}
                for s in team_data.get("statistics", []):
                    mapped = _STAT_MAP.get(s.get("name", ""))
                    if mapped:
                        try:
                            stats[mapped] = int(
                                float(s.get("displayValue") or s.get("value") or 0)
                            )
                        except (ValueError, TypeError):
                            pass
                result[side]["stats"] = stats

            # Save per-side skater lines for the leader-board panels.
            result["home"]["skaters"] = skaters["home"]
            result["away"]["skaters"] = skaters["away"]

            # Goals, scoring list, and penalties all come from the plays array —
            # ESPN NHL has no top-level "scoring" key. Goals are plays with
            # type.text == "Goal"; penalties are plays whose text uses the
            # "<player> <infraction> against <opponent>" phrasing (see
            # _NHL_PENALTY_RE). We walk plays once, in chronological order, so
            # "goals"/"scoring"/"penalties" are all oldest-first.
            for play in raw.get("plays") or []:
                ptype = play.get("type") or {}
                ptype_text = ptype.get("text", "")
                ptype_id = str(ptype.get("id", ""))
                team = play.get("team") or {}
                tid = str(team.get("id", ""))
                side = home_away_map.get(tid, "away")
                period_num = (play.get("period") or {}).get("number", 0)
                clock = (play.get("clock") or {}).get("displayValue", "")

                # Scorer / primary participant name + jersey from participants.
                def _primary(role: str | None = None) -> dict:
                    for participant in play.get("participants") or []:
                        if role and participant.get("type") != role:
                            continue
                        aid = str((participant.get("athlete") or {}).get("id", ""))
                        info = player_map.get(aid)
                        if info:
                            return info
                        # Fall back to the inline athlete displayName (penalty
                        # participants sometimes lack a boxscore stat line).
                        name = (participant.get("athlete") or {}).get("displayName")
                        if name:
                            return {"jersey": "?", "name": name}
                    return {}

                if ptype_text == "Goal":
                    scorer = _primary("scorer") or _primary()
                    result["goals"].append(
                        {
                            "period": period_num,
                            "time": clock,
                            "jersey": scorer.get("jersey", "?"),
                            "name": scorer.get("name", ""),
                            "team": tid_to_abbr.get(tid, ""),
                            "side": side,
                        }
                    )
                    result["scoring"].append(
                        {
                            "period": period_num,
                            "time": clock,
                            "name": scorer.get("name", ""),
                            "team": tid_to_abbr.get(tid, ""),
                            "side": side,
                        }
                    )
                elif (
                    ptype_id not in _NHL_NON_PENALTY_TYPE_IDS
                    and _NHL_PENALTY_RE.search(play.get("text") or "")
                ):
                    # First participant is the penalized player.
                    offender = _primary()
                    result["penalties"].append(
                        {
                            "period": period_num,
                            "time": clock,
                            "name": offender.get("name", ""),
                            "type": ptype_text,
                            "team": tid_to_abbr.get(tid, ""),
                            "side": side,
                        }
                    )

            # On-ice players — top-level "onIce" list (NOT inside situation).
            # Each item has "entries" with "athleteid" strings. We determine
            # home/away by cross-referencing the first athlete in player_map.
            for on_ice_item in raw.get("onIce") or []:
                entries = on_ice_item.get("entries") or []
                if not entries:
                    continue
                jerseys: list[str] = []
                side: str | None = None
                for entry in entries:
                    aid = str(entry.get("athleteid", ""))
                    player_info = player_map.get(aid, {})
                    jerseys.append(player_info.get("jersey", "?"))
                    if side is None and player_info.get("team_id"):
                        side = home_away_map.get(player_info["team_id"])
                if side:
                    result[side]["on_ice"] = jerseys

            # Power play detection: whichever team has more players on ice is on PP
            home_ice = result.get("home", {}).get("on_ice", [])
            away_ice = result.get("away", {}).get("on_ice", [])
            result["home"]["on_power_play"] = len(home_ice) > len(away_ice)
            result["away"]["on_power_play"] = len(away_ice) > len(home_ice)

            return result

        except Exception as e:
            logger.error(f"Failed to parse NHL game details for {event_id}: {e}")
            return None

    # ── MLB ────────────────────────────────────────────────────────────────

    def get_mlb_game_details(self, event_id: str) -> dict | None:
        """Return decisions + boxscore player stats for a specific MLB game."""
        url = f"{_ESPN_BASE}/baseball/mlb/summary?event={event_id}"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN MLB game details fetch failed for {event_id}: {e}")
            return None

        try:
            result: dict = {}

            # Collect all pitches in the CURRENT at-bat from the plays array.
            # Strategy: walk backwards; SKIP known between-play events (subs,
            # baserunning); STOP on anything else (hits, outs, walks, HBP, …).
            # This avoids having to enumerate every possible at-bat-ending type.
            ab_pitches: list[dict] = []
            for play in reversed(raw.get("plays", [])):
                ptype = (play.get("type") or {}).get("text", "").lower()
                mapped = _PITCH_TYPE_MAP.get(ptype)
                if mapped:
                    coord = (
                        play.get("pitchCoordinate")
                        or play.get("coordinate")
                        or play.get("pitchData")
                        or {}
                    )
                    px = py = None
                    if isinstance(coord, dict):
                        rx = coord.get("x") or coord.get("coordinateX")
                        ry = (
                            coord.get("y") or coord.get("z") or coord.get("coordinateY")
                        )
                        if rx is not None and ry is not None:
                            try:
                                px, py = float(rx), float(ry)
                            except (TypeError, ValueError):
                                pass
                    ab_pitches.append({"result": mapped, "x": px, "y": py})
                elif any(f in ptype for f in _BETWEEN_PLAY_FRAGMENTS):
                    continue  # mid-at-bat non-pitch event — skip, keep searching
                else:
                    break  # hit, out, walk, HBP, or any other at-bat boundary
            ab_pitches.reverse()  # restore chronological order
            result["current_ab_pitches"] = ab_pitches

            # Decisions
            def _parse_decision(d: dict | None) -> dict | None:
                if not d:
                    return None
                athlete = d.get("athlete", {})
                stats = {
                    s.get("name", ""): s.get("displayValue", "")
                    for s in d.get("statistics", [])
                }
                return {
                    "jersey": athlete.get("jersey", "?"),
                    "name": athlete.get("displayName", ""),
                    "era": stats.get("ERA", ""),
                    "record": stats.get("record", ""),
                }

            decisions_raw = raw.get("decisions") or {}
            result["decisions"] = {
                "winner": _parse_decision(decisions_raw.get("winner")),
                "loser": _parse_decision(decisions_raw.get("loser")),
                "save": _parse_decision(decisions_raw.get("save")),
            }

            home_away_map = _build_home_away_map(raw)
            boxscore = raw.get("boxscore", {})
            for team_data in boxscore.get("players", []):
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                abbr = team.get("abbreviation", "???")
                home_away = home_away_map.get(tid, "away")

                batters: list[dict] = []
                pitchers: list[dict] = []

                for stats_group in team_data.get("statistics", []):
                    labels = stats_group.get("labels", [])

                    def _idx(name: str) -> int:
                        return labels.index(name) if name in labels else -1

                    def _stat(stats: list, idx: int) -> str:
                        return stats[idx] if 0 <= idx < len(stats) else ""

                    if "IP" in labels:
                        ip_idx = _idx("IP")
                        k_idx = _idx("K")
                        era_idx = _idx("ERA")
                        for entry in stats_group.get("athletes", []):
                            athlete = entry.get("athlete", {})
                            stats = entry.get("stats", [])
                            pitchers.append(
                                {
                                    "jersey": athlete.get("jersey", "?"),
                                    "name": athlete.get("displayName", ""),
                                    "ip": _stat(stats, ip_idx),
                                    "k": _parse_int(_stat(stats, k_idx)),
                                    "era": _stat(stats, era_idx),
                                }
                            )
                    else:
                        h_idx = _idx("H")
                        r_idx = _idx("R")
                        rbi_idx = _idx("RBI")
                        for entry in stats_group.get("athletes", []):
                            athlete = entry.get("athlete", {})
                            if not athlete.get("active", True):
                                continue
                            stats = entry.get("stats", [])
                            batters.append(
                                {
                                    "jersey": athlete.get("jersey", "?"),
                                    "name": athlete.get("displayName", ""),
                                    "hits": _parse_int(_stat(stats, h_idx)),
                                    "runs": _parse_int(_stat(stats, r_idx)),
                                    "rbi": _parse_int(_stat(stats, rbi_idx)),
                                }
                            )

                result[home_away] = {
                    "abbreviation": abbr,
                    "batters": batters,
                    "pitchers": pitchers,
                }

            return result or None

        except Exception as e:
            logger.error(f"Failed to parse MLB game details for {event_id}: {e}")
            return None

    # ── Soccer ─────────────────────────────────────────────────────────────

    def get_soccer_scoreboard(self, league: str = "fifa.world") -> list[dict]:
        """Return current soccer matches for the given league."""
        url = f"{_ESPN_BASE}/soccer/{league}/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN Soccer ({league}) fetch failed: {e}")
            return []

        color_map = self._team_color_map(f"soccer/{league}")
        games = []
        for event in raw.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            status = comp.get("status", {})
            stype = status.get("type", {})
            game = _parse_base_game(event, home, away, stype, status, color_map)
            game["clock"] = status.get("displayClock", "")
            # Soccer period: 1=first half, 2=second half, 3+=extra time
            game["detail"] = stype.get("detail", "")
            games.append(game)
        return games

    def get_soccer_game_details(
        self, event_id: str, league: str = "fifa.world"
    ) -> dict | None:
        """Return goal scorers and match stats for a soccer match."""
        url = f"{_ESPN_BASE}/soccer/{league}/summary?event={event_id}"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN Soccer game details fetch failed for {event_id}: {e}")
            return None

        try:
            home_away_map = _build_home_away_map(raw)
            result: dict = {"home": {}, "away": {}, "goals": []}

            # Team abbreviations from boxscore.teams
            tid_to_abbr: dict[str, str] = {}
            for team_data in raw.get("boxscore", {}).get("teams") or []:
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                abbr = team.get("abbreviation", "???")
                tid_to_abbr[tid] = abbr
                side = home_away_map.get(tid, "away")
                result[side]["abbreviation"] = abbr

                # Team stats (possession, shots, shots on target)
                stats: dict[str, str] = {}
                for s in team_data.get("statistics", []):
                    name = s.get("name", "")
                    val = s.get("displayValue", "")
                    if name in ("possessionPct", "possession"):
                        stats["possession"] = val
                    elif name in ("shotsTotal", "totalShots"):
                        stats["shots"] = val
                    elif name in ("shotsOnTarget", "shotsOnGoal"):
                        stats["sog"] = val
                    elif name == "foulsCommitted":
                        stats["fouls"] = val
                    elif name in ("yellowCards", "yellowRedCards"):
                        stats["yellows"] = val
                    elif name == "redCards":
                        stats["reds"] = val
                    elif name in ("cornerKicks", "corners"):
                        stats["corners"] = val
                result[side]["stats"] = stats

            # Goal scorers from keyEvents or scoringPlays
            key_events = raw.get("keyEvents") or raw.get("scoringPlays") or []
            for play in key_events:
                ptype = (play.get("type") or {}).get("text", "").lower()
                if "goal" not in ptype:
                    continue
                team = play.get("team") or {}
                tid = str(team.get("id", ""))
                side = home_away_map.get(tid, "away")
                clock = (play.get("clock") or {}).get("displayValue", "")
                # Try to get scorer name
                scorer = ""
                for p in play.get("participants") or []:
                    athlete = p.get("athlete") or {}
                    if athlete.get("displayName"):
                        scorer = _last_name(athlete["displayName"])
                        break
                if not scorer:
                    text = play.get("text", "")
                    if text:
                        scorer = text.split("(")[0].strip().split(" ")[-1][:6]

                result["goals"].append(
                    {
                        "time": clock,
                        "scorer": scorer[:6],
                        "team": tid_to_abbr.get(tid, ""),
                        "side": side,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to parse Soccer game details for {event_id}: {e}")
            return None

    # ── Football (NFL / NCAA) ──────────────────────────────────────────────
    #
    # Every football league lives behind ESPN's /football/{league}/ endpoints
    # and returns an identical payload shape, so one pair of methods serves
    # them all — pass the ESPN league slug:
    #   "nfl"              → /football/nfl/...
    #   "college-football" → /football/college-football/...

    def get_football_scoreboard(self, league: str = "nfl") -> list[dict]:
        """Return the current football slate for the given league."""
        url = f"{_ESPN_BASE}/football/{league}/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN football ({league}) fetch failed: {e}")
            return []

        color_map = self._team_color_map(f"football/{league}")
        games = []
        for event in raw.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            home_rank = _football_rank(home)
            away_rank = _football_rank(away)

            status = comp.get("status", {})
            stype = status.get("type", {})
            situation = comp.get("situation") or {}

            # ESPN sends down = -1 between plays (kickoff, PAT, timeout).
            down = _to_int(situation.get("down"))

            game = _parse_base_game(event, home, away, stype, status, color_map)
            game["clock"] = status.get("displayClock", "")
            game["possession"] = _parse_possession(
                situation,
                str(home["team"].get("id", "")),
                str(away["team"].get("id", "")),
            )
            game.update(
                {
                    "down": down if down > 0 else 0,
                    "distance": _to_int(situation.get("distance")),
                    "down_distance": situation.get("shortDownDistanceText") or "",
                    "yard_line_text": situation.get("possessionText") or "",
                    "is_red_zone": bool(situation.get("isRedZone")),
                    "home_timeouts": situation.get("homeTimeouts"),
                    "away_timeouts": situation.get("awayTimeouts"),
                    "home_line_scores": _line_scores(home),
                    "away_line_scores": _line_scores(away),
                    # AP top-25 rank, or None when unranked (college football)
                    "home_rank": home_rank,
                    "away_rank": away_rank,
                }
            )
            games.append(game)

        return games

    def get_football_game_details(
        self, event_id: str, league: str = "nfl"
    ) -> dict | None:
        """Return team stats, stat leaders, scoring plays and the current drive."""
        url = f"{_ESPN_BASE}/football/{league}/summary?event={event_id}"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(
                f"ESPN football ({league}) details fetch failed for {event_id}: {e}"
            )
            return None

        try:
            home_away_map = _build_home_away_map(raw)
            result: dict = {"home": {}, "away": {}, "scoring": [], "drive": {}}
            tid_to_abbr: dict[str, str] = {}

            # Team stats from boxscore.teams
            for team_data in raw.get("boxscore", {}).get("teams") or []:
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                abbr = team.get("abbreviation", "???")
                tid_to_abbr[tid] = abbr
                side = home_away_map.get(tid, "away")
                result[side]["abbreviation"] = abbr
                stats: dict[str, str] = {}
                for s in team_data.get("statistics", []):
                    key = _FOOTBALL_TEAM_STATS.get(s.get("name", ""))
                    if key:
                        stats[key] = str(s.get("displayValue") or s.get("value") or "0")
                result[side]["stats"] = stats

            # Stat leaders — one passing / rushing / receiving leader per team
            for group in raw.get("leaders") or []:
                tid = str((group.get("team") or {}).get("id", ""))
                side = home_away_map.get(tid, "away")
                leaders: dict[str, dict] = result[side].setdefault("leaders", {})
                for category in group.get("leaders") or []:
                    key = _FOOTBALL_LEADER_CATS.get(category.get("name", ""))
                    if not key:
                        continue
                    entry = next(iter(category.get("leaders") or []), None)
                    if not entry:
                        continue
                    athlete = entry.get("athlete") or {}
                    detail = entry.get("displayValue") or ""
                    leaders[key] = {
                        # ESPN's lastName keeps suffixes ("Etienne Jr.") —
                        # _last_name strips them.
                        "name": _last_name(
                            athlete.get("lastName") or athlete.get("displayName", "")
                        ),
                        "jersey": athlete.get("jersey", "") or "",
                        "yards": _to_int(entry.get("value")),
                        "touchdowns": _match_int(_LEADER_TD_RE, detail),
                        "interceptions": _match_int(_LEADER_INT_RE, detail),
                        "detail": detail,
                    }

            # Scoring plays, chronological. Points come from the running score
            # delta, which also resolves ESPN's odd play-type labels.
            running = {"away": 0, "home": 0}
            for play in raw.get("scoringPlays") or []:
                tid = str((play.get("team") or {}).get("id", ""))
                side = home_away_map.get(tid, "away")
                away_score = _to_int(play.get("awayScore"))
                home_score = _to_int(play.get("homeScore"))
                scores = {"away": away_score, "home": home_score}
                points = scores[side] - running[side]
                running = scores
                result["scoring"].append(
                    {
                        "period": (play.get("period") or {}).get("number", 0),
                        "time": (play.get("clock") or {}).get("displayValue", ""),
                        "type": _football_score_type(play.get("type") or {}, points),
                        "points": points,
                        "side": side,
                        "team": tid_to_abbr.get(tid, ""),
                        "away_score": away_score,
                        "home_score": home_score,
                        "text": play.get("text", "") or "",
                    }
                )

            # Current drive (live games only)
            current = (raw.get("drives") or {}).get("current") or {}
            if current:
                drive_team = current.get("team") or {}
                dtid = str(drive_team.get("id", ""))
                result["drive"] = {
                    "side": home_away_map.get(dtid, ""),
                    "team": drive_team.get("abbreviation") or tid_to_abbr.get(dtid, ""),
                    "description": current.get("description", "") or "",
                    "yards": _to_int(current.get("yards")),
                    "plays": len(current.get("plays") or []),
                    "is_score": bool(current.get("isScore")),
                }

            return result

        except Exception as e:
            logger.error(f"Failed to parse football details for {event_id}: {e}")
            return None
