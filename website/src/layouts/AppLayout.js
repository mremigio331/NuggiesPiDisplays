import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import BottomNav from "../navigation/BottomNav";
import { getNotificationsContext } from "../services/Notifications";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { useTimers } from "../hooks/useTimers";
import { dismissDoneTimers, getUpdateStatus } from "../services/API";
import "./AppLayout.css";

export default function AppLayout({ children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { notifications } = getNotificationsContext();
  const { data: status } = useSystemStatus({ refetchInterval: 8000 });
  const running = status?.running ?? false;
  const mode = status?.active_display ?? null;

  // Shares the ["updateStatus"] cache with the System page. Poll every 5 min so
  // the amber indicator appears without needing a reload.
  const { data: updateStatus } = useQuery({
    queryKey: ["updateStatus"],
    queryFn: getUpdateStatus,
    staleTime: 3600000,
    refetchInterval: 300000,
    retry: false,
  });
  const updateAvailable = updateStatus?.update_available ?? false;

  const qc = useQueryClient();
  const { data: timers } = useTimers();
  const doneTimers = (timers?.timers ?? []).filter((t) => t.done);
  const dismissMut = useMutation({
    mutationFn: dismissDoneTimers,
    onSuccess: (saved) => qc.setQueryData(["timers"], saved),
  });

  const goHome = () => navigate(mode ? `/${mode}` : "/");

  return (
    <div className="ml-shell">
      <header className="ml-topbar">
        <button className="ml-brand" onClick={goHome}>
          Nuggies Display
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {pathname !== "/system" ? (
            <button
              className="ml-settings-btn"
              aria-label={
                updateAvailable ? "System settings — update available" : "System settings"
              }
              onClick={() => navigate("/system")}
            >
              ⚙{updateAvailable && <span className="ml-update-badge" title="Update available" />}
            </button>
          ) : (
            updateAvailable && (
              <span
                className="ml-dot update"
                title="Update available"
                aria-label="Update available"
              />
            )
          )}
          <div className="ml-status-chip">
            <span className={`ml-dot ${running ? "on" : "off"}`} />
            <span>{running ? mode.toUpperCase() : "OFF"}</span>
          </div>
        </div>
      </header>

      {doneTimers.length > 0 && pathname !== "/clock" && (
        <div className="ml-timer-banner" role="alert">
          <span onClick={() => navigate("/clock")}>
            ⏰ {doneTimers.length === 1 ? `${doneTimers[0].label} is done` : `${doneTimers.length} timers are done`}
          </span>
          <button
            className="m-btn m-btn-danger"
            style={{ flex: "0 0 auto", height: 30, padding: "0 12px" }}
            disabled={dismissMut.isPending}
            onClick={() => dismissMut.mutate()}
          >
            Dismiss{doneTimers.length > 1 ? " all" : ""}
          </button>
        </div>
      )}

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
