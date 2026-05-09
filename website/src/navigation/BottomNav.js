import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import "./BottomNav.css";

const TABS = [
  { label: "Home", icon: "🏠", path: "/" },
  { label: "MTA", icon: "🚇", path: "/mta" },
  { label: "Stocks", icon: "📈", path: "/stocks" },
  { label: "Clock", icon: "🕐", path: "/clock" },
  { label: "System", icon: "⚙️", path: "/system" },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isActive = (path) => (path === "/" ? pathname === "/" : pathname.startsWith(path));

  return (
    <nav className="bottom-nav" role="tablist">
      {TABS.map(({ label, icon, path }) => (
        <button
          key={path}
          role="tab"
          aria-label={label}
          aria-selected={isActive(path)}
          className={`bottom-nav-tab${isActive(path) ? " active" : ""}`}
          onClick={() => navigate(path)}
        >
          {isActive(path) && <span className="active-pip" />}
          <span className="tab-icon">{icon}</span>
          <span className="tab-label">{label}</span>
        </button>
      ))}
    </nav>
  );
}
