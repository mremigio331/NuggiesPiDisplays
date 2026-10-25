import axios from "axios";
import { apiEndpoint } from "../configs/apiConfig";

const api = axios.create({ baseURL: `${apiEndpoint}/api` });

const handle = async (promise) => {
  const res = await promise;
  return res.data;
};

// System
export const getSystemStatus = () => handle(api.get("/system/status"));
export const startDisplay = () => handle(api.post("/system/display/start"));
export const stopDisplay = () => handle(api.post("/system/display/stop"));
export const switchDisplay = (mode) => handle(api.post("/system/display", { mode }));
export const restartPi = () => handle(api.post("/system/restart"));
export const restartApi = () => handle(api.post("/system/restart-api"));
export const restartDisplay = () => handle(api.post("/system/restart-display"));
export const restartWebsite = () => handle(api.post("/system/restart-website"));
export const factoryReset = () => handle(api.post("/system/factory-reset"));
export const factoryResetWifi = () => handle(api.post("/system/factory-reset-wifi"));
export const getDevMode = () => handle(api.get("/system/dev-mode"));
export const forgetWifi = () => handle(api.post("/system/forget-wifi"));
export const restartWifiService = () => handle(api.post("/system/restart-wifi-service"));
// Force the setup portal to come up on a device that currently reports a
// connection: writes the .force_portal marker and restarts the wifi service
// detached so the setup AP reappears. This is how a connected device is
// reconfigured. See POST /api/system/force-wifi-portal (task 5.1).
export const forceWifiPortal = () => handle(api.post("/system/force-wifi-portal"));
// Trigger an update. With no component (or "all") this is the classic full
// update + reboot. A component ("api"|"display"|"website"|"system") scopes it
// to that part (restarts only the affected service). force=true reinstalls even
// if that part did not change in the pulled range.
export const updateApp = (runSetup = true, component = null, force = false) =>
  api
    .post("/system/update-app", {
      run_setup: runSetup,
      component,
      force,
    })
    .then((res) => res.data)
    .catch((err) => {
      // 409 = an update is already running. That isn't an error for the UI —
      // the body carries the in-flight run_id so we can attach to that run.
      if (err.response && err.response.status === 409) {
        return { ...err.response.data, already_running: true };
      }
      throw err;
    });
export const getLogLevel = () => handle(api.get("/system/log-level"));
export const setLogLevel = (log_level) => handle(api.put("/system/log-level", { log_level }));
export const getUpdateStatus = () => handle(api.get("/system/update-status"));
// Release stage this device tracks: { stage: "beta"|"prod", valid: [...] }.
export const getUpdateStage = () => handle(api.get("/system/update-stage"));
export const setUpdateStage = (stage) => handle(api.put("/system/update-stage", { stage }));
export const checkUpdate = () => handle(api.post("/system/check-update"));
export const getUpdateLog = (offset = 0, runId = "") =>
  handle(api.get("/system/update-log", { params: { offset, run_id: runId } }));
export const getUserGuide = () => handle(api.get("/system/user-guide"));
export const getLogsList = () => handle(api.get("/system/logs"));
// IP-based geolocation suggestion: { latitude, longitude, city_label, timezone }
export const getGeolocation = () => handle(api.get("/system/geolocate"));

// WiFi — derived device address for the post-reboot / reconnect instructions.
// Returns { configured, connected, ssid, portal_active, hostname, mdns_name, ip }.
// mdns_name is "<hostname>.local"; ip is the device IPv4 (or null). Nothing is
// hardcoded to nuggies — the address follows the device's own hostname.
export const getWifiStatus = () => handle(api.get("/wifi/status"));
export const getLogContent = (key, lines = 200) =>
  api.get(`/system/logs/${key}`, { params: { lines } }).then((r) => r.data);

// MTA — trains
export const getNextFourTrains = () => handle(api.get("/mta/trains/next_four"));

// MTA — configs
export const getMTAConfigs = () => handle(api.get("/mta/configs"));
export const updateMTAConfig = (key, value) => handle(api.put("/mta/configs", { key, value }));

// MTA — stations
export const getAllStations = () => handle(api.get("/mta/stations"));
export const getCurrentStation = () => handle(api.get("/mta/stations/current"));
export const setCurrentStation = (station) => handle(api.put("/mta/stations/current", { station }));
export const getEnabledStations = () => handle(api.get("/mta/stations/enabled"));
export const setStationEnabled = (id, enabled) =>
  handle(api.put(`/mta/stations/${encodeURIComponent(id)}/enabled`, { enabled }));

// Stocks
export const getStocksSettings = () => handle(api.get("/stonks/settings"));
export const updateStocksSettings = (body) => handle(api.put("/stonks/settings", body));
export const searchStocks = (q) => handle(api.get("/stonks/search", { params: { q } }));
export const getStockInfo = (symbol) => handle(api.get(`/stonks/${symbol}/info`));
export const getStockChart = (symbol, cycleKey) => handle(api.get(`/stonks/${symbol}/${cycleKey}`));
export const getStockNow = () => handle(api.get("/stonks/now"));
// Jump the display to a specific ticker + chart view once, then resume rotation
export const showStockView = (symbol, cycleKey) =>
  updateStocksSettings({ force_view: `${symbol}:${cycleKey}` });

// Sports
export const getNBAScoreboard = () => handle(api.get("/sports/nba/scoreboard"));
export const getWNBAScoreboard = () => handle(api.get("/sports/wnba/scoreboard"));
export const getMLBScoreboard = () => handle(api.get("/sports/mlb/scoreboard"));
export const getNHLScoreboard = () => handle(api.get("/sports/nhl/scoreboard"));
// Football — one sport per league (nfl, ncaaf, …), same payload shape
export const getFootballScoreboard = (sport = "nfl") =>
  handle(api.get(`/sports/${sport}/scoreboard`));
export const getFootballLeagues = () => handle(api.get("/sports/football/leagues"));
export const getNFLScoreboard = () => getFootballScoreboard("nfl");
export const getNCAAFScoreboard = () => getFootballScoreboard("ncaaf");
// Soccer — one sport per league (nwsl, …), same payload shape
export const getSoccerScoreboard = (sport = "nwsl") =>
  handle(api.get(`/sports/${sport}/scoreboard`));
export const getSoccerLeagues = () => handle(api.get("/sports/soccer/leagues"));
export const getNWSLScoreboard = () => getSoccerScoreboard("nwsl");
export const getEPLScoreboard = () => getSoccerScoreboard("epl");
export const getLaLigaScoreboard = () => getSoccerScoreboard("laliga");
export const getBundesligaScoreboard = () => getSoccerScoreboard("bundesliga");
// Favourites feed — games involving favourited teams across every league.
// Each game carries a `sport` key naming its league.
export const getFavoritesScoreboard = () => handle(api.get("/sports/favorites/scoreboard"));
export const getSportsSettings = () => handle(api.get("/sports/settings"));
export const updateSportsSettings = (body) => handle(api.put("/sports/settings", body));
export const getSportsNow = () => handle(api.get("/sports/now"));
// Game locks — the matrix cycles through locked games only. Each lock expires
// 24h after it is set; all four calls return the updated sports settings.
// Teams in a league, for the favourite-team picker (sport key encodes the league)
export const getSportsTeams = (sport) => handle(api.get("/sports/teams", { params: { sport } }));
// Favourite teams — per sport, keyed by ESPN team id
export const getSportsFavorites = () => handle(api.get("/sports/favorites"));
export const addFavoriteTeam = (teamId, sport) =>
  handle(api.put(`/sports/favorites/${encodeURIComponent(teamId)}`, { sport }));
export const removeFavoriteTeam = (teamId, sport) =>
  handle(api.delete(`/sports/favorites/${encodeURIComponent(teamId)}`, { params: { sport } }));
export const setFavoriteTeams = (teamIds, sport) =>
  handle(api.put("/sports/favorites", { team_ids: teamIds, sport }));
export const getSportsLocks = () => handle(api.get("/sports/locks"));
export const lockSportsGame = (eventId, sport) =>
  handle(api.put(`/sports/locks/${encodeURIComponent(eventId)}`, { sport }));
export const unlockSportsGame = (eventId) =>
  handle(api.delete(`/sports/locks/${encodeURIComponent(eventId)}`));
export const clearSportsLocks = () => handle(api.delete("/sports/locks"));
// Jump to a game once, then resume the normal rotation
export const showSportsGame = (eventId) => updateSportsSettings({ force_event_id: eventId });

// Clock
export const getClockSettings = () => handle(api.get("/clock/settings"));
export const updateClockSettings = (body) => handle(api.put("/clock/settings", body));
export const getClockTimezones = (page = 1, search = "") =>
  handle(api.get("/clock/timezones", { params: { page, search } }));

// Weather
export const getWeatherData = () => handle(api.get("/weather/data"));
export const getWeatherSettings = () => handle(api.get("/weather/settings"));
export const updateWeatherSettings = (body) => handle(api.put("/weather/settings", body));
export const geocodeLocation = (q) => handle(api.get("/weather/geocode", { params: { q } }));
