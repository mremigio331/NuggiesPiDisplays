import axios from "axios";
import { apiEndpoint } from "../configs/apiConfig";

const api = axios.create({ baseURL: apiEndpoint });

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

// Clock
export const getClockSettings = () => handle(api.get("/clock/settings"));
export const updateClockSettings = (body) => handle(api.put("/clock/settings", body));
export const getClockTimezones = (page = 1, search = "") =>
  handle(api.get("/clock/timezones", { params: { page, search } }));
