import React from "react";
import BottomNav from "../navigation/BottomNav";
import { getNotificationsContext } from "../services/Notifications";
import { useSystemStatus } from "../hooks/useSystemStatus";
import "./MobileLayout.css";

export default function MobileLayout({ children }) {
  const { notifications } = getNotificationsContext();
  const { data: status } = useSystemStatus({ refetchInterval: 8000 });
  const running = status?.running ?? false;
  const mode = status?.active_display ?? "—";

  return (
    <div className="ml-shell">
      <header className="ml-topbar">
        <span className="ml-brand">Nuggies Display</span>
        <div className="ml-status-chip">
          <span className={`ml-dot ${running ? "on" : "off"}`} />
          <span>{running ? mode.toUpperCase() : "OFF"}</span>
        </div>
      </header>

      {notifications.length > 0 && (
        <div className="m-notifications">
          {notifications.map((n) => (
            <div key={n.id} className={`m-notif m-notif-${n.type || "info"}`}>
              {n.loading && <div className="m-spinner" />}
              <span className="m-notif-msg">{n.content}</span>
              {n.dismissible && (
                <button className="m-notif-dismiss" onClick={n.onDismiss}>
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <main className="ml-content">{children}</main>
      <BottomNav />
    </div>
  );
}
