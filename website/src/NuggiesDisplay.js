import * as React from "react";
import { AppLayout, Flashbar } from "@cloudscape-design/components";
import { Routes, Route } from "react-router-dom";
import { useIsMobile } from "./hooks/useIsMobile";
import NavBar from "./navigation/NavBar";
import MobileLayout from "./layouts/MobileLayout";
import { getNotificationsContext } from "./services/Notifications";

import Home from "./pages/home/Home";
import MTA from "./pages/mta/MTA";
import MTASettings from "./pages/mta/MTASettings";
import Stocks from "./pages/stocks/Stocks";
import System from "./pages/system/System";
import PageNotFound from "./pages/PageNotFound";

const PageRoutes = () => (
  <Routes>
    <Route path="/" element={<Home />} />
    <Route path="/mta" element={<MTA />} />
    <Route path="/mta/settings" element={<MTASettings />} />
    <Route path="/stocks" element={<Stocks />} />
    <Route path="/system" element={<System />} />
    <Route path="*" element={<PageNotFound />} />
  </Routes>
);

export default function NuggiesDisplay() {
  document.title = "Nuggies Display";
  const isMobile = useIsMobile();
  const { notifications } = getNotificationsContext();

  if (isMobile) {
    return (
      <MobileLayout>
        <PageRoutes />
      </MobileLayout>
    );
  }

  return (
    <div>
      <div style={{ position: "sticky", top: 0, zIndex: 1002 }}>
        <NavBar />
      </div>
      <AppLayout
        notifications={<Flashbar items={notifications} stackItems />}
        content={<PageRoutes />}
        navigationHide
        toolsHide
        maxContentWidth={Number.MAX_VALUE}
      />
    </div>
  );
}
