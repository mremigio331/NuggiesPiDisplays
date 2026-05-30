import logging
import time

import requests

logger = logging.getLogger(__name__)

_ESPN_BASE = "http://site.api.espn.com/apis/site/v2/sports"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _parse_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _last_name(display_name: str) -> str:
    """Extract last name from a full display name, e.g. 'Aaron Judge' → 'Judge'."""
    if not display_name:
        return ""
    parts = display_name.strip().split()
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


def _parse_base_game(
    event: dict, home: dict, away: dict, stype: dict, status: dict
) -> dict:
    """Fields common to every sport's scoreboard game entry."""
    return {
        "event_id": event.get("id", ""),
        "home_team": home["team"].get("abbreviation", ""),
        "away_team": away["team"].get("abbreviation", ""),
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

            # Possession — ESPN returns situation.possession (team id string) or
            # situation.team.id for live basketball games.
            situation = comp.get("situation") or {}
            home_id = str(home["team"].get("id", ""))
            away_id = str(away["team"].get("id", ""))
            poss_id = str(
                situation.get("possession")
                or (situation.get("team") or {}).get("id")
                or ""
            )
            possession = (
                "home"
                if poss_id and poss_id == home_id
                else "away" if poss_id and poss_id == away_id else None
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
