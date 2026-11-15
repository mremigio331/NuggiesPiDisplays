import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTimers } from "../hooks/useTimers";
import "./BottomNav.css";

const TABS = [
  { label: "Clock", icon: "🕐", path: "/clock" },
  { label: "MTA", icon: "🚇", path: "/mta" },
  { label: "Sports", icon: "🏀", path: "/sports" },
  { label: "Stocks", icon: "📈", path: "/stocks" },
  { label: "Text", icon: "💬", path: "/text" },
  { label: "Weather", icon: "🌤️", path: "/weather" },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isActive = (path) => (path === "/" ? pathname === "/" : pathname.startsWith(path));

  // Timers live on the Clock page, so the Clock tab flags a done timer.
  const { data: timers } = useTimers();
  const doneCount = (timers?.timers ?? []).filter((t) => t.done).length;

  return (
    <nav className="bottom-nav" role="tablist">
      {TABS.map(({ label, icon, path }) => {
        const timerDone = path === "/clock" && doneCount > 0;
        return (
          <button
            key={path}
            role="tab"
            aria-label={timerDone ? `${label} — timer done` : label}
            aria-selected={isActive(path)}
            className={`bottom-nav-tab${isActive(path) ? " active" : ""}${timerDone ? " timer-done" : ""}`}
            onClick={() => navigate(path)}
          >
            {isActive(path) && <span className="active-pip" />}
            {timerDone && (
              <span className="timer-done-badge">{doneCount > 1 ? doneCount : ""}</span>
            )}
            <span className="tab-icon">{timerDone ? "⏰" : icon}</span>
            <span className="tab-label">{timerDone ? "Time's up" : label}</span>
          </button>
        );
      })}
    </nav>
  );
}
