import React, { useState, useEffect, useCallback } from "react";

const SIGNAL_BARS = (signal) => {
  if (signal >= 75) return "████";
  if (signal >= 50) return "███░";
  if (signal >= 25) return "██░░";
  return "█░░░";
};

function useNetworks() {
  const [networks, setNetworks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/wifi/networks");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setNetworks(await res.json());
    } catch (e) {
      setError("Could not load networks. Is the Pi in setup mode?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);
  return { networks, loading, error, refresh: fetch_ };
}

export default function WifiSetup() {
  const { networks, loading, error, refresh } = useNetworks();
  const [selectedSsid, setSelectedSsid] = useState(null);
  const [password, setPassword] = useState("");
  const [phase, setPhase] = useState("select"); // "select" | "connecting" | "success" | "error"
  const [errorMsg, setErrorMsg] = useState("");

  const selectedNetwork = networks.find((n) => n.ssid === selectedSsid);

  async function handleConnect() {
    if (!selectedSsid) return;
    setPhase("connecting");
    setErrorMsg("");

    let result;
    try {
      const res = await fetch("/api/wifi/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ssid: selectedSsid, password: password || null }),
      });
      result = await res.json();
    } catch {
      // A network error likely means the AP dropped — treat as success.
      result = { success: true, message: "Connected (connection to setup AP dropped)." };
    }

    if (result.success) {
      setPhase("success");
    } else {
      setPhase("error");
      setErrorMsg(result.message || "Connection failed.");
    }
  }

  function reset() {
    setPhase("select");
    setSelectedSsid(null);
    setPassword("");
    setErrorMsg("");
    refresh();
  }

  // ── Success screen ──────────────────────────────────────────────────────
  if (phase === "success") {
    return (
      <div>
        <div className="m-section-title">WiFi Setup</div>
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>✓</div>
          <div className="m-card-title">Connected!</div>
          <div style={{ color: "#aaa", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            The Pi joined <strong style={{ color: "#fff" }}>{selectedSsid}</strong>.
          </div>
          <div className="m-card" style={{ background: "#1a2a1a", textAlign: "left" }}>
            <div className="m-card-title" style={{ color: "#5cb85c" }}>Next steps</div>
            <ol style={{ margin: 0, paddingLeft: "1.2rem", color: "#ccc", lineHeight: "1.8", fontSize: "0.9rem" }}>
              <li>Disconnect from <strong>NuggiesSetup</strong></li>
              <li>
                Reconnect to <strong style={{ color: "#fff" }}>{selectedSsid}</strong>
              </li>
              <li>
                Visit{" "}
                <strong style={{ color: "#5b9bd5" }}>nuggies.local</strong> in your browser
              </li>
            </ol>
          </div>
        </div>
      </div>
    );
  }

  // ── Connecting screen ───────────────────────────────────────────────────
  if (phase === "connecting") {
    return (
      <div>
        <div className="m-section-title">WiFi Setup</div>
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>⏳</div>
          <div className="m-card-title">Connecting to {selectedSsid}…</div>
          <div style={{ color: "#aaa", fontSize: "0.85rem", lineHeight: "1.6", marginTop: "0.75rem" }}>
            This takes up to 30 seconds.
            <br />
            <strong style={{ color: "#f0a800" }}>
              You&apos;ll lose connection to NuggiesSetup — that&apos;s normal.
            </strong>
          </div>
          <div className="m-card" style={{ background: "#1a1a2a", textAlign: "left", marginTop: "1rem" }}>
            <div style={{ color: "#aaa", fontSize: "0.85rem", lineHeight: "1.7" }}>
              If this page stops responding:
              <ol style={{ margin: "0.4rem 0 0", paddingLeft: "1.2rem" }}>
                <li>Connect your device to <strong style={{ color: "#fff" }}>{selectedSsid}</strong></li>
                <li>Visit <strong style={{ color: "#5b9bd5" }}>nuggies.local</strong></li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Select / error screen ───────────────────────────────────────────────
  return (
    <div>
      <div className="m-section-title">WiFi Setup</div>
      <div className="m-section-sub">Connect your Nuggies display to your home network</div>

      {phase === "error" && (
        <div className="m-card" style={{ background: "#2a1a1a", borderLeft: "3px solid #d9534f" }}>
          <div style={{ color: "#d9534f", fontWeight: 600, marginBottom: "0.25rem" }}>
            Connection failed
          </div>
          <div style={{ color: "#ccc", fontSize: "0.85rem" }}>{errorMsg}</div>
        </div>
      )}

      <div className="m-card">
        <div className="m-card-title">
          Available Networks
          <button
            className="m-btn m-btn-neutral"
            style={{ float: "right", padding: "2px 10px", fontSize: "0.8rem" }}
            disabled={loading}
            onClick={refresh}
          >
            {loading ? "Scanning…" : "Refresh"}
          </button>
        </div>

        {error && <div style={{ color: "#d9534f", fontSize: "0.85rem" }}>{error}</div>}

        {!loading && !error && networks.length === 0 && (
          <div style={{ color: "#aaa", fontSize: "0.85rem" }}>No networks found. Try refreshing.</div>
        )}

        {networks.map((net) => (
          <button
            key={net.ssid}
            className={`m-btn ${selectedSsid === net.ssid ? "m-btn-active" : "m-btn-neutral"}`}
            style={{
              width: "100%",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.4rem",
              padding: "0.6rem 0.8rem",
            }}
            onClick={() => { setSelectedSsid(net.ssid); setPassword(""); setPhase("select"); }}
          >
            <span>
              {net.secured ? "🔒 " : ""}
              {net.ssid}
            </span>
            <span style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "#aaa" }}>
              {SIGNAL_BARS(net.signal)}
            </span>
          </button>
        ))}
      </div>

      {selectedSsid && (
        <div className="m-card">
          <div className="m-card-title">Connect to {selectedSsid}</div>

          {selectedNetwork?.secured ? (
            <div style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", color: "#aaa", fontSize: "0.85rem", marginBottom: "0.3rem" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                placeholder="Enter WiFi password"
                style={{
                  width: "100%",
                  padding: "0.5rem 0.6rem",
                  background: "#1e1e1e",
                  border: "1px solid #444",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "1rem",
                  boxSizing: "border-box",
                }}
              />
            </div>
          ) : (
            <div style={{ color: "#aaa", fontSize: "0.85rem", marginBottom: "1rem" }}>
              Open network — no password needed.
            </div>
          )}

          <div className="m-btn-row">
            <button className="m-btn m-btn-neutral" onClick={reset}>
              Back
            </button>
            <button
              className="m-btn m-btn-primary"
              disabled={selectedNetwork?.secured && !password}
              onClick={handleConnect}
            >
              Connect
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
