# Nuggies Display API

FastAPI backend serving the RGB LED matrix display system. Manages display processes, settings, and proxies data from ESPN, Yahoo Finance, MTA GTFS, and weather APIs.

**Base URL:** `http://nuggies.local:8000/api`

---

## Endpoints

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/system/status` | Display state and active mode |
| `POST` | `/system/display` | Switch display mode |
| `POST` | `/system/display/start` | Start the active display |
| `POST` | `/system/display/stop` | Stop the active display |
| `POST` | `/system/restart` | Reboot the Pi |
| `POST` | `/system/update-app` | Pull latest code, re-run setup, reboot |
| `WS` | `/system/update` | Stream setup.sh --update output |
| `GET` | `/system/update-status` | Check if update is available |
| `POST` | `/system/check-update` | Trigger update check |
| `POST` | `/system/factory-reset` | Reset settings + pull latest + re-setup |
| `POST` | `/system/factory-reset-wifi` | Full reset + wipe WiFi + reboot |
| `POST` | `/system/forget-wifi` | Clear saved WiFi connections |
| `POST` | `/system/restart-wifi-service` | Restart captive portal service |
| `GET` | `/system/log-level` | Current log level |
| `PUT` | `/system/log-level` | Set log level (DEBUG/INFO/WARNING/ERROR) |
| `GET` | `/system/logs` | List available log files |
| `GET` | `/system/logs/{log_key}` | Tail a log file (query: `?lines=100`) |
| `GET` | `/system/dev-mode` | Check if dev mode is active |

### MTA Subway

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/mta/trains/next_four` | Next 4 trains at current station |
| `GET` | `/mta/trains/all_data` | Full train data for current station |
| `GET` | `/mta/configs` | MTA display settings |
| `PUT` | `/mta/configs` | Update an MTA config key |
| `GET` | `/mta/stations` | All available stations |
| `GET` | `/mta/stations/current` | Currently displayed station |
| `PUT` | `/mta/stations/current` | Set current station |
| `GET` | `/mta/stations/enabled` | Stations enabled for cycling |
| `PUT` | `/mta/stations/{station_id}/enabled` | Toggle station enabled |
| `PUT` | `/mta/stations/force_change` | Force immediate station change |

### Sports

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/sports/settings` | Sports display settings |
| `PUT` | `/sports/settings` | Update sport, league, display mode, etc. |
| `GET` | `/sports/now` | Currently displayed game(s) on matrix |
| `GET` | `/sports/teams` | Teams in a league (query: `?sport=nfl`) |
| `GET` | `/sports/favorites` | Favourite team ids, keyed by sport |
| `PUT` | `/sports/favorites` | Replace one sport's favourites |
| `PUT` | `/sports/favorites/{team_id}` | Favourite a team (query/body: `sport`) |
| `DELETE` | `/sports/favorites/{team_id}` | Unfavourite a team |
| `GET` | `/sports/locks` | Locked games (expired locks excluded) |
| `PUT` | `/sports/locks/{event_id}` | Lock a game to the matrix for 24h |
| `DELETE` | `/sports/locks/{event_id}` | Unlock a game |
| `DELETE` | `/sports/locks` | Unlock all games |
| `GET` | `/sports/nba/scoreboard` | Today's NBA games |
| `GET` | `/sports/nba/game/{event_id}` | NBA game details (box score) |
| `GET` | `/sports/mlb/scoreboard` | Today's MLB games |
| `GET` | `/sports/mlb/game/{event_id}` | MLB game details (batters/pitchers) |
| `GET` | `/sports/nhl/scoreboard` | Today's NHL games |
| `GET` | `/sports/nhl/game/{event_id}` | NHL game details (stats/goals) |
| `GET` | `/sports/nfl/scoreboard` | Today's NFL games |
| `GET` | `/sports/nfl/game/{event_id}` | NFL game details (team stats/leaders/scoring) |
| `GET` | `/sports/football/leagues` | Available football leagues (NFL, NCAAF, …) |
| `GET` | `/sports/soccer/scoreboard` | Soccer matches (query: `?league=fifa.world`) |
| `GET` | `/sports/soccer/game/{event_id}` | Soccer match details |
| `GET` | `/sports/soccer/leagues` | Available soccer leagues |

### Stocks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/stonks/settings` | Stock display settings |
| `PUT` | `/stonks/settings` | Update stock settings |
| `GET` | `/stonks/search` | Search tickers (query: `?q=AAPL`) |
| `GET` | `/stonks/{symbol}/info` | Stock info (name, price, change) |
| `GET` | `/stonks/{symbol}/{cycle_key}` | Chart data (intraday/6month/ytd/1year) |
| `GET` | `/stonks/now` | Currently displayed stock/cycle |
| `PUT` | `/stonks/now` | Set current stock/cycle on matrix |

### Clock

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/clock/settings` | Clock display settings |
| `PUT` | `/clock/settings` | Update clock settings |
| `GET` | `/clock/timezones` | Searchable timezone list |
| `WS` | `/clock/ws` | Real-time clock updates |

### Weather

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/weather/settings` | Weather display settings |
| `PUT` | `/weather/settings` | Update weather settings |
| `GET` | `/weather/data` | Current + forecast weather data |
| `GET` | `/weather/geocode` | Geocode a city name |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | API health check |

---

## Running

```bash
cd api
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs at `http://localhost:8000/docs`.
