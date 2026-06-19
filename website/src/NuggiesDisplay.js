import React from "react";
import { Routes, Route } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";

import Home from "./pages/home/Home";
import MTA from "./pages/mta/MTA";
import MTASettings from "./pages/mta/MTASettings";
import Stocks from "./pages/stocks/Stocks";
import StocksSettings from "./pages/stocks/StocksSettings";
import Clock from "./pages/clock/Clock";
import ClockSettings from "./pages/clock/ClockSettings";
import System from "./pages/system/System";
import Logs from "./pages/system/Logs";
import Sports from "./pages/sports/Sports";
import SportsSettings from "./pages/sports/SportsSettings";
import Weather from "./pages/weather/Weather";
import WeatherSettings from "./pages/weather/WeatherSettings";
import WifiSetup from "./pages/wifi-setup/WifiSetup";
import PageNotFound from "./pages/PageNotFound";

export default function NuggiesDisplay() {
  document.title = "Nuggies Display";
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/mta" element={<MTA />} />
        <Route path="/mta/settings" element={<MTASettings />} />
        <Route path="/stocks" element={<Stocks />} />
        <Route path="/stocks/settings" element={<StocksSettings />} />
        <Route path="/clock" element={<Clock />} />
        <Route path="/clock/settings" element={<ClockSettings />} />
        <Route path="/sports" element={<Sports />} />
        <Route path="/sports/settings" element={<SportsSettings />} />
        <Route path="/system" element={<System />} />
        <Route path="/system/logs" element={<Logs />} />
        <Route path="/weather" element={<Weather />} />
        <Route path="/weather/settings" element={<WeatherSettings />} />
        <Route path="/wifi-setup" element={<WifiSetup />} />
        <Route path="*" element={<PageNotFound />} />
      </Routes>
    </AppLayout>
  );
}
