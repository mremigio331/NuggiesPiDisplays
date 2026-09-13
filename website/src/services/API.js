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
export const factoryReset = () => handle(api.post("/system/factory-reset"));
export const factoryResetWifi = () => handle(api.post("/system/factory-reset-wifi"));
export const getDevMode = () => handle(api.get("/system/dev-mode"));
export const forgetWifi = () => handle(api.post("/system/forget-wifi"));
export const restartWifiService = () => handle(api.post("/system/restart-wifi-service"));
export const updateApp = (runSetup = true) =>
  handle(api.post("/system/update-app", { run_setup: runSetup }));
export const getLogLevel = () => handle(api.get("/system/log-level"));
export const setLogLevel = (log_level) => handle(api.put("/system/log-level", { log_level }));
export const getUpdateStatus = () => handle(api.get("/system/update-status"));
export const checkUpdate = () => handle(api.post("/system/check-update"));
export const getLogsList = () => handle(api.get("/system/logs"));
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

// Sports
export const getNBAScoreboard = () => handle(api.get("/sports/nba/scoreboard"));
export const getMLBScoreboard = () => handle(api.get("/sports/mlb/scoreboard"));
export const getNHLScoreboard = () => handle(api.get("/sports/nhl/scoreboard"));
// Football — one sport per league (nfl, ncaaf, …), same payload shape
export const getFootballScoreboard = (sport = "nfl") =>
  handle(api.get(`/sports/${sport}/scoreboard`));
export const getFootballLeagues = () => handle(api.get("/sports/football/leagues"));
export const getNFLScoreboard = () => getFootballScoreboard("nfl");
export const getSoccerScoreboard = (league = "fifa.world") =>
  handle(api.get("/sports/soccer/scoreboard", { params: { league } }));
export const getSoccerLeagues = () => handle(api.get("/sports/soccer/leagues"));
export const getSportsSettings = () => handle(api.get("/sports/settings"));
export const updateSportsSettings = (body) => handle(api.put("/sports/settings", body));
export const getSportsNow = () => handle(api.get("/sports/now"));
// Game locks — the matrix cycles through locked games only. Each lock expires
// 24h after it is set; all four calls return the updated sports settings.
// Teams in a league, for the favourite-team picker
export const getSportsTeams = (sport, league) =>
  handle(api.get("/sports/teams", { params: { sport, league } }));
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
