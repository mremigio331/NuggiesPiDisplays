import React from "react";

/** Hours until an ISO expiry, rounded down; null when unparseable or past. */
function hoursLeft(expiresAt) {
  const ms = new Date(expiresAt).getTime() - Date.now();
  if (!Number.isFinite(ms) || ms <= 0) return null;
  return Math.floor(ms / 3_600_000);
}

function expiryLabel(expiresAt) {
  const hours = hoursLeft(expiresAt);
  if (hours === null) return "expiring";
  if (hours >= 1) return `${hours}h left`;
  const minutes = Math.max(1, Math.round((new Date(expiresAt) - Date.now()) / 60_000));
  return `${minutes}m left`;
}

/**
 * Shows which games are pinned to the matrix, with per-game unlock.
 * Locks not on today's slate are called out rather than silently ignored.
 */
export default function LockedGamesBanner({ locks, games, isPending, onUnlock, onClearAll }) {
  if (!locks.length) return null;

  const byId = new Map(games.map((g) => [g.event_id, g]));

  return (
    <div
      className="m-card"
      style={{ padding: "0.55rem 0.75rem", marginBottom: 12, borderLeft: "3px solid #c47d00" }}
    >
      <div style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
        <div style={{ flex: 1, color: "#ddd", fontSize: "0.78rem", fontWeight: 600 }}>
          {locks.length === 1 ? "Locked on 1 game" : `Locked on ${locks.length} games`}
        </div>
        {locks.length > 1 && (
          <button
            className="m-btn m-btn-neutral"
            style={{ padding: "2px 10px", fontSize: "0.72rem" }}
            disabled={isPending}
            onClick={onClearAll}
          >
            Clear all
          </button>
        )}
      </div>

      <div style={{ color: "#888", fontSize: "0.7rem", marginBottom: 8 }}>
        {locks.length > 1
          ? "The matrix cycles through just these games."
          : "The matrix stays on this game, full screen."}{" "}
        Locks expire automatically after 24 hours.
      </div>

      {locks.map((lock) => {
        const game = byId.get(lock.event_id);
        return (
          <div
            key={lock.event_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "3px 0",
              borderTop: "1px solid #262626",
            }}
          >
            <span style={{ flex: 1, color: game ? "#ccc" : "#777", fontSize: "0.78rem" }}>
              {game ? `${game.away_team} @ ${game.home_team}` : lock.event_id}
              {!game && (
                <span style={{ color: "#777", fontSize: "0.7rem" }}> · not on today's slate</span>
              )}
            </span>
            <span style={{ color: "#777", fontSize: "0.68rem" }}>
              {expiryLabel(lock.expires_at)}
            </span>
            <button
              className="m-btn m-btn-neutral"
              style={{ padding: "1px 8px", fontSize: "0.72rem" }}
              disabled={isPending}
              onClick={() => onUnlock(lock.event_id)}
              title="Unlock this game"
            >
              Unlock
            </button>
          </div>
        );
      })}
    </div>
  );
}
