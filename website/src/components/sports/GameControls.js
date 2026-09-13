import React from "react";

/**
 * Per-game matrix controls, shared by every sport.
 *
 * Show — jump the matrix to this game now, then let it keep cycling.
 * Lock — pin the matrix to this game until unlocked (renders full-screen).
 */
export default function GameControls({
  isLocked,
  isOnMatrix,
  isPending,
  onShow,
  onLock,
  onUnlock,
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        alignItems: "center",
        margin: "-4px 0 8px",
        paddingLeft: 2,
      }}
    >
      <button
        className="m-btn m-btn-neutral"
        style={{ padding: "2px 10px", fontSize: "0.72rem" }}
        disabled={isPending}
        onClick={onShow}
        title="Show this game on the matrix now"
      >
        Show
      </button>

      <button
        className={`m-btn ${isLocked ? "m-btn-active" : "m-btn-neutral"}`}
        style={{ padding: "2px 10px", fontSize: "0.72rem" }}
        disabled={isPending}
        onClick={isLocked ? onUnlock : onLock}
        title={isLocked ? "Stop pinning this game" : "Keep this game on the matrix"}
      >
        {isLocked ? "Locked" : "Lock"}
      </button>

      {isOnMatrix && !isLocked && (
        <span style={{ color: "#2196f3", fontSize: "0.68rem" }}>on matrix</span>
      )}
    </div>
  );
}
