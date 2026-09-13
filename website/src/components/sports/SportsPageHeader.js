import React from "react";
import SwitchDisplayButton from "../shared/SwitchDisplayButton";

export default function SportsPageHeader({ sport, isPending, onSportChange, onOpenSettings }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 8,
      }}
    >
      <select
        value={sport}
        disabled={isPending}
        onChange={(e) => onSportChange(e.target.value)}
        style={{
          background: "#1a1a1a",
          color: "#fff",
          border: "1px solid #444",
          borderRadius: 6,
          padding: "5px 10px",
          fontSize: "0.9rem",
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        <option value="mlb">MLB</option>
        <option value="nba">NBA</option>
        <option value="nfl">NFL</option>
        <option value="nhl">NHL</option>
        <option value="soccer">Soccer</option>
      </select>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <SwitchDisplayButton mode="sports" />
        <button
          className="m-btn m-btn-neutral"
          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
          onClick={onOpenSettings}
        >
          Settings
        </button>
      </div>
    </div>
  );
}
