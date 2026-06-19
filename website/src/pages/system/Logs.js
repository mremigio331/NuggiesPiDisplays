import React, { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getLogsList, getLogContent } from "../../services/API";

const LOG_LABELS = {
  application: "Application",
  display: "Display",
  service: "HTTP Access",
  wifi: "WiFi Setup",
};

export default function Logs() {
  const navigate = useNavigate();
  const [activeLog, setActiveLog] = useState("application");
  const [lines, setLines] = useState(100);
  const logRef = useRef(null);

  const { data: logsList } = useQuery({
    queryKey: ["logsList"],
    queryFn: getLogsList,
    staleTime: 30000,
  });

  const {
    data: logContent,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["logContent", activeLog, lines],
    queryFn: () => getLogContent(activeLog, lines),
    staleTime: 0,
    refetchInterval: 5000,
  });

  // Auto-scroll to bottom when content changes
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logContent]);

  const logs = logsList?.logs ?? [];

  return (
    <div>
      <div
        className="m-section-title"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        Logs
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.8rem", padding: "2px 10px" }}
          onClick={() => navigate("/system")}
        >
          ← Back
        </button>
      </div>

      {/* Log selector tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        {logs.map((log) => (
          <button
            key={log.key}
            className={`m-btn ${activeLog === log.key ? "m-btn-active" : "m-btn-neutral"}`}
            style={{ fontSize: "0.8rem", padding: "4px 10px" }}
            onClick={() => setActiveLog(log.key)}
          >
            {LOG_LABELS[log.key] || log.key}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
        }}
      >
        <select
          value={lines}
          onChange={(e) => setLines(Number(e.target.value))}
          style={{
            background: "#1a1a1a",
            color: "#fff",
            border: "1px solid #444",
            borderRadius: 4,
            padding: "3px 8px",
            fontSize: "0.8rem",
          }}
        >
          <option value={50}>50 lines</option>
          <option value={100}>100 lines</option>
          <option value={200}>200 lines</option>
          <option value={500}>500 lines</option>
        </select>
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.75rem", padding: "3px 8px" }}
          onClick={() => refetch()}
        >
          Refresh
        </button>
        {isLoading && <span style={{ color: "#888", fontSize: "0.75rem" }}>Loading…</span>}
      </div>

      {/* Log output */}
      <div
        ref={logRef}
        style={{
          background: "#0a0a0a",
          border: "1px solid #333",
          borderRadius: 6,
          padding: "0.5rem",
          fontFamily: "monospace",
          fontSize: "0.7rem",
          lineHeight: 1.5,
          color: "#ccc",
          maxHeight: "60vh",
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
        }}
      >
        {logContent || "(empty)"}
      </div>
    </div>
  );
}
