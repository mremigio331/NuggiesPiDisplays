import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

_ESPN_BASE = "http://site.api.espn.com/apis/site/v2/sports"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# sport key → ESPN league path. Soccer is resolved per league slug at call time.
ESPN_LEAGUE_PATHS: dict[str, str] = {
    "mlb": "baseball/mlb",
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "nhl": "hockey/nhl",
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


def _parse_base_game(
    event: dict, home: dict, away: dict, stype: dict, status: dict
) -> dict:
    """Fields common to every sport's scoreboard game entry."""
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
        "home_color": home["team"].get("color", "003366"),
        "away_color": away["team"].get("color", "003366"),
        "home_alt_color": home["team"].get("alternateColor", "ffffff"),
        "away_alt_color": away["team"].get("alternateColor", "ffffff"),
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

    def get_teams(self, sport: str, soccer_league: str = "fifa.world") -> list[dict]:
        """Return every team in a league, for favourite-team pickers.

        Team ids are only unique within a league, so callers must keep the
        sport alongside any id they store.
        """
        if sport == "soccer":
            league_path = f"soccer/{soccer_league}"
        else:
            league_path = ESPN_LEAGUE_PATHS.get(sport, "")
        if not league_path:
            logger.error(f"No ESPN league path for sport {sport!r}")
            return []

        url = f"{_ESPN_BASE}/{league_path}/teams"
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

    def get_nba_scoreboard(self) -> list[dict]:
        """Return today's NBA games in a simplified format."""
        url = f"{_ESPN_BASE}/basketball/nba/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN NBA fetch failed: {e}")
            return []

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

            game = _parse_base_game(event, home, away, stype, status)
            game["clock"] = status.get("displayClock", "")
            game["possession"] = possession
            games.append(game)

        return games

    def get_nba_game_details(self, event_id: str) -> dict | None:
        """Return boxscore player data for a specific game.

        Returns a dict with keys "away" and "home", each containing:
          - abbreviation: str
          - team_fouls: int (sum of all player PF)
          - players: list of {jersey, points, fouls} sorted by points desc
        """
        url = f"{_ESPN_BASE}/basketball/nba/summary?event={event_id}"
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

    # ── MLB ────────────────────────────────────────────────────────────────

    def get_mlb_scoreboard(self) -> list[dict]:
        """Return today's MLB games with live situation data."""
        url = f"{_ESPN_BASE}/baseball/mlb/scoreboard"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN MLB fetch failed: {e}")
            return []

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

            game = _parse_base_game(event, home, away, stype, status)
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
            game = _parse_base_game(event, home, away, stype, status)
            game["clock"] = status.get("displayClock", "")
            games.append(game)
        return games

    def get_nhl_game_details(self, event_id: str) -> dict | None:
        """Return team stats (SOG/hits/blocks), goal scorers, and on-ice players."""
        url = f"{_ESPN_BASE}/hockey/nhl/summary?event={event_id}"
        try:
            raw = self._get(url)
        except Exception as e:
            logger.error(f"ESPN NHL game details fetch failed for {event_id}: {e}")
            return None

        try:
            home_away_map = _build_home_away_map(raw)
            result: dict = {"home": {}, "away": {}, "goals": []}

            # Build player_map: athlete_id str → {jersey, team_id}
            player_map: dict[str, dict] = {}
            for team_data in raw.get("boxscore", {}).get("players") or []:
                team = team_data.get("team", {})
                tid = str(team.get("id", ""))
                for stats_group in team_data.get("statistics", []):
                    for entry in stats_group.get("athletes", []):
                        athlete = entry.get("athlete", {})
                        aid = str(athlete.get("id", ""))
                        if aid:
                            player_map[aid] = {
                                "jersey": athlete.get("jersey", "?"),
                                "team_id": tid,
                            }

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

            # Goals from plays array — ESPN NHL has no top-level "scoring" key;
            # goals appear as plays with type.text == "Goal"
            for play in raw.get("plays") or []:
                if (play.get("type") or {}).get("text", "") != "Goal":
                    continue
                team = play.get("team") or {}
                tid = str(team.get("id", ""))
                side = home_away_map.get(tid, "away")
                period_num = (play.get("period") or {}).get("number", 0)
                clock = (play.get("clock") or {}).get("displayValue", "")
                scorer_jersey = "?"
                for participant in play.get("participants") or []:
                    aid = str((participant.get("athlete") or {}).get("id", ""))
                    if aid:
                        scorer_jersey = player_map.get(aid, {}).get("jersey", "?")
                        break
                result["goals"].append(
                    {
                        "period": period_num,
                        "time": clock,
                        "jersey": scorer_jersey,
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
            game = _parse_base_game(event, home, away, stype, status)
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
            situation = comp.get("situation") or {}

            # ESPN sends down = -1 between plays (kickoff, PAT, timeout).
            down = _to_int(situation.get("down"))

            game = _parse_base_game(event, home, away, stype, status)
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
