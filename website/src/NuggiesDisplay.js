import React from "react";
import { Routes, Route } from "react-router-dom";
import MobileLayout from "./layouts/MobileLayout";

import Home from "./pages/home/Home";
import MTA from "./pages/mta/MTA";
import MTASettings from "./pages/mta/MTASettings";
import Stocks from "./pages/stocks/Stocks";
import StocksSettings from "./pages/stocks/StocksSettings";
import Clock from "./pages/clock/Clock";
import ClockSettings from "./pages/clock/ClockSettings";
import System from "./pages/system/System";
import PageNotFound from "./pages/PageNotFound";

export default function NuggiesDisplay() {
  document.title = "Nuggies Display";
  return (
    <MobileLayout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/mta" element={<MTA />} />
        <Route path="/mta/settings" element={<MTASettings />} />
        <Route path="/stocks" element={<Stocks />} />
        <Route path="/stocks/settings" element={<StocksSettings />} />
        <Route path="/clock" element={<Clock />} />
        <Route path="/clock/settings" element={<ClockSettings />} />
        <Route path="/system" element={<System />} />
        <Route path="*" element={<PageNotFound />} />
      </Routes>
    </MobileLayout>
  );
}
