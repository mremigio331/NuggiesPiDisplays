import React, { useState, useEffect, useCallback, useRef } from "react";
import { forceWifiPortal } from "../../services/API";

const SIGNAL_BARS = (signal) => {
  if (signal >= 75) return "████";
  if (signal >= 50) return "███░";
  if (signal >= 25) return "██░░";
  return "█░░░";
};

// Human-readable age for the cached-scan label. Seconds under a minute,
// otherwise rounded minutes.
const formatAge = (ageSeconds) => {
  if (typeof ageSeconds !== "number" || ageSeconds < 0) return "a moment ago";
  const secs = Math.round(ageSeconds);
  if (secs < 60) return `${secs} second${secs === 1 ? "" : "s"} ago`;
  const mins = Math.round(secs / 60);
  return `${mins} minute${mins === 1 ? "" : "s"} ago`;
};

// The three DEFINITE states the network list load resolves to. Every load ends
// in exactly one of these — there is no generic "something went wrong" fallback.
//   "portal"       200 with a networks object → the device is hosting the setup
//                  AP and we can show the list.
//   "configured"   409 setup_not_needed → the MAIN API answered, so this device
//                  is already connected and setup is not needed.
//   "service-down" transport error or 503 → the setup service is unavailable.
const LOAD_PORTAL = "portal";
const LOAD_CONFIGURED = "configured";
const LOAD_SERVICE_DOWN = "service-down";

function useNetworks() {
  const [networks, setNetworks] = useState([]);
  const [stale, setStale] = useState(false);
  const [ageSeconds, setAgeSeconds] = useState(null);
  const [scanError, setScanError] = useState(null);
  const [loading, setLoading] = useState(true);
  // Definite load state; null only while the first load is in flight.
  const [loadState, setLoadState] = useState(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/wifi/networks");

      // 409 setup_not_needed: the MAIN API answered because this device is
      // already connected. Distinct from a service outage.
      if (res.status === 409) {
        let code = null;
        try {
          const body = await res.json();
          code = body && body.code ? body.code : null;
        } catch {
          // Body might not be JSON; the 409 status alone is enough.
        }
        // Treat any 409 as "already connected"; setup_not_needed is the code.
        setLoadState(LOAD_CONFIGURED);
        return code;
      }

      // 503 (or any other non-ok) means the setup service is unavailable.
      if (!res.ok) {
        setLoadState(LOAD_SERVICE_DOWN);
        return;
      }

      // 200: the captive portal answered with the networks object.
      const data = await res.json();
      setNetworks(Array.isArray(data.networks) ? data.networks : []);
      setStale(Boolean(data.stale));
      setAgeSeconds(typeof data.age_seconds === "number" ? data.age_seconds : null);
      setScanError(data.error || null);
      setLoadState(LOAD_PORTAL);
    } catch {
      // fetch threw → transport failure → the setup service is unreachable.
      setLoadState(LOAD_SERVICE_DOWN);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch_();
  }, [fetch_]);
  return { networks, stale, ageSeconds, scanError, loading, loadState, refresh: fetch_ };
}

export default function WifiSetup() {
  const { networks, stale, ageSeconds, loading, loadState, refresh } = useNetworks();
  const [selectedSsid, setSelectedSsid] = useState(null);
  const [password, setPassword] = useState("");
  // Manual "network not listed?" SSID entry — feeds the same connect path.
  const [manualSsid, setManualSsid] = useState("");
  const [manualPassword, setManualPassword] = useState("");
  // Manual entry is opt-in: nothing renders a text input until the user taps
  // the "Network not listed?" button. This also avoids the browser
  // autofocusing an SSID box on page load.
  const [showManual, setShowManual] = useState(false);
  // "select" | "connecting" | "verified" | "unknown" | "failed"
  const [phase, setPhase] = useState("select");
  const [errorMsg, setErrorMsg] = useState("");
  // Force-portal request state (used on the already-connected card).
  const [forcing, setForcing] = useState(false);
  const [forced, setForced] = useState(false);
  // Derived post-reboot address for this device (from GET /api/wifi/status).
  // mdnsName is "<hostname>.local"; deviceIp is the IPv4 fallback for clients
  // that cannot resolve .local. NOTHING here is hardcoded to nuggies.
  const [mdnsName, setMdnsName] = useState(null);
  const [deviceIp, setDeviceIp] = useState(null);
  // Visible setup-AP SSID, derived server-side from the hostname. Defaults to the
  // documented fallback until the status fetch resolves so instructions read sensibly.
  const [setupSsid, setSetupSsid] = useState("NuggiesDisplay");
  const passwordRef = useRef(null);
  const manualSsidRef = useRef(null);
  const pollRef = useRef(null);

  // Fetch the derived device address once, for the post-reboot instructions.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/wifi/status");
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setMdnsName(data.mdns_name || null);
        setDeviceIp(data.ip || null);
        setSetupSsid(data.setup_ssid || "NuggiesDisplay");
      } catch {
        // Non-fatal: the instruction screens fall back to generic wording.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Clean up any in-flight poll timer on unmount.
  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  // Move focus to the manual SSID input once the user opts into manual entry.
  // Runs after the DOM updates so the just-mounted input exists to focus.
  useEffect(() => {
    if (!showManual) return;
    const id = requestAnimationFrame(() => manualSsidRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [showManual]);

  // Move focus to the password input when a secured network is selected. Runs
  // after the DOM updates (so the just-expanded input is mounted), which the
  // old setTimeout-in-selectNetwork raced against. Open networks have no
  // password field, so there's nothing to focus.
  useEffect(() => {
    if (!selectedSsid) return;
    const net = networks.find((n) => n.ssid === selectedSsid);
    if (net && net.secured) {
      const id = requestAnimationFrame(() => passwordRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
  }, [selectedSsid, networks]);

  // Force the setup portal to come up. This writes the .force_portal marker and
  // restarts the wifi service detached (task 5.1), so the setup AP reappears in
  // ~30s. This is how a connected device is reconfigured. We do NOT reload the
  // page — the AP is on a different network the client must join manually — so
  // instead we report what happened and give the reconnect guidance.
  async function handleForcePortal() {
    setForcing(true);
    try {
      await forceWifiPortal();
      setForced(true);
    } catch {
      // The restart drops this connection, so a transport error here is the
      // expected outcome, not a failure. Show the guidance regardless.
      setForced(true);
    } finally {
      setForcing(false);
    }
  }

  function selectNetwork(net) {
    if (selectedSsid === net.ssid) {
      setSelectedSsid(null);
      setPassword("");
    } else {
      setSelectedSsid(net.ssid);
      setPassword("");
      setPhase("select");
    }
  }

  // Map a terminal server state onto a UI phase.
  // connected_verified → "verified"; failed → "failed"; anything else
  // (unknown_verify, or a transport failure while the AP is dropping) → "unknown".
  function applyTerminalState(state, message) {
    if (state === "connected_verified") {
      setPhase("verified");
    } else if (state === "failed") {
      setPhase("failed");
      setErrorMsg(message || "Connection failed.");
    } else {
      // unknown_verify, or an indeterminate transport outcome. Never success.
      setPhase("unknown");
    }
  }

  const POLL_INTERVAL_MS = 2000;
  const POLL_TIMEOUT_MS = 90000; // bound the polling; on timeout fall to "unknown"

  // Accepts explicit ssid/password so the manual-entry Join can pass its typed
  // values directly, avoiding the stale-state pitfall of calling setState then
  // handleConnect in the same tick. With no args it falls back to the
  // selected-network state (used by the list Join button and Enter key).
  async function handleConnect(ssidArg, passwordArg) {
    const ssid = ssidArg ?? selectedSsid;
    const pw = passwordArg !== undefined ? passwordArg : password;
    if (!ssid) return;
    setPhase("connecting");
    setSelectedSsid(ssid); // so the connecting/verified screens name the target
    setErrorMsg("");
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }

    let jobId = null;
    try {
      const res = await fetch("/api/wifi/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ssid, password: pw || null }),
      });
      // The endpoint answers 202 immediately with { job_id, state } BEFORE the
      // radio moves. If we can read a body, capture the job id to poll.
      try {
        const body = await res.json();
        jobId = body && body.job_id ? body.job_id : null;
      } catch {
        // No/invalid body — poll the latest job below.
      }
    } catch {
      // POST itself failed at the transport layer. The radio may still be
      // handing over; we cannot claim success. Try to poll the latest job,
      // and if that also fails we resolve to "unknown".
      jobId = null;
    }

    pollConnectStatus(jobId, Date.now());
  }

  async function pollConnectStatus(jobId, startedAt) {
    // Give up on the whole flow after POLL_TIMEOUT_MS and report "unknown".
    if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
      applyTerminalState("unknown_verify");
      return;
    }

    const url = jobId
      ? `/api/wifi/connect/status?job_id=${encodeURIComponent(jobId)}`
      : "/api/wifi/connect/status";

    let data;
    try {
      const res = await fetch(url);
      if (res.status === 404) {
        // No job known — treat as indeterminate, keep trying until timeout.
        data = { state: "connecting" };
      } else {
        data = await res.json();
      }
    } catch {
      // Transport error — almost always the setup AP dropping as the radio
      // moves to the target network. This is NOT success. Retry until timeout,
      // then resolve to "unknown".
      pollRef.current = setTimeout(() => pollConnectStatus(jobId, startedAt), POLL_INTERVAL_MS);
      return;
    }

    const state = data && data.state ? data.state : "unknown_verify";
    if (state === "connecting") {
      pollRef.current = setTimeout(() => pollConnectStatus(jobId, startedAt), POLL_INTERVAL_MS);
      return;
    }

    // Terminal state reached.
    applyTerminalState(state, data && data.message);
  }

  function reset() {
    setPhase("select");
    setSelectedSsid(null);
    setPassword("");
    setErrorMsg("");
    refresh();
  }

  // Renders the derived post-reboot address: <hostname>.local with the IPv4 as
  // an explicit fallback for clients that cannot resolve .local. Falls back to
  // generic wording if the status fetch never returned an address.
  function DerivedAddress() {
    if (!mdnsName && !deviceIp) {
      return <strong style={{ color: "#5b9bd5" }}>your device&apos;s address</strong>;
    }
    return (
      <>
        {mdnsName && <strong style={{ color: "#5b9bd5" }}>{mdnsName}</strong>}
        {mdnsName && deviceIp && " "}
        {deviceIp && (
          <span style={{ color: "#aaa" }}>
            (or <strong style={{ color: "#5b9bd5" }}>{deviceIp}</strong> if{" "}
            {mdnsName ? mdnsName : "the .local name"} doesn&apos;t resolve)
          </span>
        )}
      </>
    );
  }

  // Guidance shown after a force-portal request has been fired. The setup AP
  // reappears within ~30s; the user must join it and browse to the portal IP.
  // The address here is ALWAYS http://10.42.0.1 — never the .local name —
  // because while the portal is up its DNS is hijacked and the mdns name will
  // not resolve to the setup page.
  function ForcedGuidance() {
    return (
      <div
        className="m-card"
        style={{ background: "#1a1a2a", textAlign: "left", marginTop: "1rem" }}
      >
        <div className="m-card-title" style={{ color: "#5b9bd5" }}>
          WiFi setup is starting
        </div>
        <ol
          style={{
            margin: 0,
            paddingLeft: "1.2rem",
            color: "#ccc",
            lineHeight: "1.8",
            fontSize: "0.9rem",
          }}
        >
          <li>
            The <strong style={{ color: "#fff" }}>{setupSsid}</strong> WiFi network will appear
            within about 30 seconds.
          </li>
          <li>
            Join it with the password <strong style={{ color: "#fff" }}>SetUpNuggies</strong>.
          </li>
          <li>
            Then open <strong style={{ color: "#5b9bd5" }}>http://10.42.0.1</strong> in your browser
            to reconfigure WiFi.
          </li>
        </ol>
      </div>
    );
  }

  // The "Force WiFi Setup" action button, disabled while the request is in
  // flight and hidden once fired (guidance replaces it).
  function ForcePortalButton() {
    return (
      <button
        className="m-btn m-btn-primary"
        style={{ minWidth: "180px" }}
        disabled={forcing}
        onClick={handleForcePortal}
      >
        {forcing ? "Starting…" : "Force WiFi Setup"}
      </button>
    );
  }

  // ── Already-connected screen ────────────────────────────────────────────
  // 409 setup_not_needed: the MAIN API answered, so this device is already on a
  // network and setup isn't needed. We name the device (via DerivedAddress) so
  // the user knows which one answered, and offer Force WiFi Setup to reconfigure.
  if (loadState === LOAD_CONFIGURED && !loading) {
    return (
      <div>
        <div className="m-section-title">WiFi Setup</div>
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>✓</div>
          <div className="m-card-title">This device is already connected</div>
          <div style={{ color: "#aaa", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            <DerivedAddress /> is already on a network, so WiFi setup isn&apos;t needed. If you want
            to move it to a different network, force WiFi setup to start over.
          </div>
          {forced ? <ForcedGuidance /> : <ForcePortalButton />}
        </div>
      </div>
    );
  }

  // ── Service-unavailable screen ──────────────────────────────────────────
  // Transport error or 503: the setup service isn't answering. Offer a retry
  // and a Force WiFi Setup escape hatch.
  if (loadState === LOAD_SERVICE_DOWN && !loading) {
    return (
      <div>
        <div className="m-section-title">WiFi Setup</div>
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>⚠️</div>
          <div className="m-card-title">The setup service is unavailable</div>
          <div style={{ color: "#aaa", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            We couldn&apos;t reach the WiFi setup service. It may still be starting up, or it may
            have stopped. You can try again, or force WiFi setup to restart it.
          </div>
          {forced ? (
            <ForcedGuidance />
          ) : (
            <div
              style={{ display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap" }}
            >
              <button
                className="m-btn m-btn-neutral"
                style={{ minWidth: "140px" }}
                disabled={loading}
                onClick={refresh}
              >
                Try again
              </button>
              <ForcePortalButton />
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Verified screen ─────────────────────────────────────────────────────
  // The server confirmed the join (connected_verified) and is rebooting into
  // normal operation with the display running. Post-reboot the device answers
  // at its derived address — NOT at the setup AP.
  if (phase === "verified") {
    return (
      <div>
        <div className="m-section-title">WiFi Setup</div>
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>✓</div>
          <div className="m-card-title">Connected!</div>
          <div style={{ color: "#aaa", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            The Pi joined <strong style={{ color: "#fff" }}>{selectedSsid}</strong> and confirmed
            the connection.
          </div>
          <div className="m-card" style={{ background: "#1a2a1a", textAlign: "left" }}>
            <div className="m-card-title" style={{ color: "#5cb85c" }}>
              Next steps
            </div>
            <ol
              style={{
                margin: 0,
                paddingLeft: "1.2rem",
                color: "#ccc",
                lineHeight: "1.8",
                fontSize: "0.9rem",
              }}
            >
              <li>
                The device is <strong style={{ color: "#fff" }}>restarting now</strong> to start the
                display. Give it a minute or two to come back up.
              </li>
              <li>
                Reconnect your phone or computer to{" "}
                <strong style={{ color: "#fff" }}>{selectedSsid}</strong>
              </li>
              <li>
                Then visit <DerivedAddress /> in your browser
              </li>
            </ol>
          </div>
        </div>
      </div>
    );
  }

  // ── Unknown screen ──────────────────────────────────────────────────────
  // We could not confirm the outcome — typically because the setup AP dropped
  // as the radio moved, so the browser never received a definite result. We do
  // NOT claim success; we give the user steps to check for themselves.
  if (phase === "unknown") {
    return (
      <div>
        <div className="m-section-title">WiFi Setup</div>
        <div className="m-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>🤷</div>
          <div className="m-card-title">We couldn&apos;t confirm the result</div>
          <div style={{ color: "#aaa", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            The connection to <strong>{setupSsid}</strong> dropped before we heard back, so we
            can&apos;t be sure whether the Pi joined{" "}
            <strong style={{ color: "#fff" }}>{selectedSsid}</strong>. Here&apos;s how to check.
          </div>
          <div className="m-card" style={{ background: "#2a2a1a", textAlign: "left" }}>
            <div className="m-card-title" style={{ color: "#f0a800" }}>
              How to check
            </div>
            <ol
              style={{
                margin: 0,
                paddingLeft: "1.2rem",
                color: "#ccc",
                lineHeight: "1.8",
                fontSize: "0.9rem",
              }}
            >
              <li>
                Reconnect your phone or computer to{" "}
                <strong style={{ color: "#fff" }}>{selectedSsid}</strong>
              </li>
              <li>
                Visit <DerivedAddress /> in your browser. If it loads, the Pi is connected.
              </li>
              <li>
                If it doesn&apos;t load, rejoin <strong>{setupSsid}</strong> and open{" "}
                <strong style={{ color: "#5b9bd5" }}>http://10.42.0.1</strong> — if the setup page
                is still there, the join didn&apos;t take and you can try again.
              </li>
            </ol>
          </div>
          <button
            className="m-btn m-btn-neutral"
            style={{ marginTop: "1rem", minWidth: "160px" }}
            onClick={reset}
          >
            Try again
          </button>
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
          <div
            style={{ color: "#aaa", fontSize: "0.85rem", lineHeight: "1.6", marginTop: "0.75rem" }}
          >
            This takes up to 30 seconds.
            <br />
            <strong style={{ color: "#f0a800" }}>
              You&apos;ll lose connection to {setupSsid} — that&apos;s normal.
            </strong>
          </div>
          <div
            className="m-card"
            style={{ background: "#1a1a2a", textAlign: "left", marginTop: "1rem" }}
          >
            <div style={{ color: "#aaa", fontSize: "0.85rem", lineHeight: "1.7" }}>
              If this page stops responding, hang tight — we&apos;ll keep checking. If it
              doesn&apos;t recover on its own:
              <ol style={{ margin: "0.4rem 0 0", paddingLeft: "1.2rem" }}>
                <li>
                  Rejoin <strong style={{ color: "#fff" }}>{setupSsid}</strong> and open{" "}
                  <strong style={{ color: "#5b9bd5" }}>http://10.42.0.1</strong> to try again, or
                </li>
                <li>
                  Reconnect to <strong style={{ color: "#fff" }}>{selectedSsid}</strong> and visit{" "}
                  <DerivedAddress /> to see if the Pi is already on your network
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Network list ────────────────────────────────────────────────────────
  return (
    <div>
      <div className="m-section-title">WiFi Setup</div>
      <div className="m-section-sub">Connect your Nuggies display to your home network</div>

      {phase === "failed" && (
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

        {loading && (
          <div
            style={{
              color: "#aaa",
              fontSize: "0.9rem",
              textAlign: "center",
              padding: "0.75rem 0",
            }}
          >
            🔍 Searching for WiFi networks…
          </div>
        )}

        {!loading && stale && (
          <div style={{ color: "#f0a800", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
            Showing cached results from {formatAge(ageSeconds)}.
          </div>
        )}

        {!loading && !stale && networks.length === 0 && (
          <div style={{ color: "#aaa", fontSize: "0.85rem" }}>
            Couldn&apos;t scan for networks right now. Try refreshing.
          </div>
        )}

        {!loading &&
          networks.map((net) => {
            const isSelected = selectedSsid === net.ssid;
            return (
              <div key={net.ssid}>
                <button
                  className={`m-btn ${isSelected ? "m-btn-active" : "m-btn-neutral"}`}
                  style={{
                    width: "100%",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: isSelected ? "0" : "0.4rem",
                    padding: "0.6rem 0.8rem",
                    borderRadius: isSelected ? "8px 8px 0 0" : "8px",
                  }}
                  onClick={() => selectNetwork(net)}
                >
                  <span>
                    {net.secured ? "🔒 " : ""}
                    {net.ssid}
                  </span>
                  <span style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "#aaa" }}>
                    {SIGNAL_BARS(net.signal)}
                  </span>
                </button>

                {isSelected && (
                  <div
                    style={{
                      background: "#1e1e1e",
                      border: "1px solid #444",
                      borderTop: "none",
                      borderRadius: "0 0 8px 8px",
                      padding: "0.75rem 0.8rem",
                      marginBottom: "0.4rem",
                    }}
                  >
                    {net.secured ? (
                      <input
                        ref={passwordRef}
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                        placeholder="Password"
                        style={{
                          width: "100%",
                          padding: "0.5rem 0.6rem",
                          background: "#111",
                          border: "1px solid #555",
                          borderRadius: "6px",
                          color: "#fff",
                          fontSize: "1rem",
                          boxSizing: "border-box",
                          marginBottom: "0.6rem",
                        }}
                      />
                    ) : (
                      <div style={{ color: "#aaa", fontSize: "0.85rem", marginBottom: "0.6rem" }}>
                        Open network — no password needed.
                      </div>
                    )}
                    <button
                      className="m-btn m-btn-primary"
                      style={{ width: "100%" }}
                      disabled={net.secured && !password}
                      onClick={() => handleConnect()}
                    >
                      Join
                    </button>
                  </div>
                )}
              </div>
            );
          })}

        {/* Manual entry for a network that isn't listed (e.g. hidden SSIDs, or
            a scan that missed it). Feeds the typed values straight into
            handleConnect(ssid, password) to avoid stale-state issues. A blank
            password means an open network. */}
        {!loading && (
          <div
            style={{
              marginTop: "0.8rem",
              paddingTop: "0.8rem",
              borderTop: "1px solid #333",
            }}
          >
            {!showManual ? (
              <button
                className="m-btn m-btn-neutral"
                style={{ width: "100%" }}
                onClick={() => setShowManual(true)}
              >
                Network not listed?
              </button>
            ) : (
              <>
                <div style={{ color: "#ccc", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                  Network not listed?
                </div>
                <input
                  ref={manualSsidRef}
                  type="text"
                  value={manualSsid}
                  onChange={(e) => setManualSsid(e.target.value)}
                  placeholder="Network name (SSID)"
                  style={{
                    width: "100%",
                    padding: "0.5rem 0.6rem",
                    background: "#111",
                    border: "1px solid #555",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "1rem",
                    boxSizing: "border-box",
                    marginBottom: "0.5rem",
                  }}
                />
                <input
                  type="password"
                  value={manualPassword}
                  onChange={(e) => setManualPassword(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && manualSsid && handleConnect(manualSsid, manualPassword)
                  }
                  placeholder="Password (leave blank for open network)"
                  style={{
                    width: "100%",
                    padding: "0.5rem 0.6rem",
                    background: "#111",
                    border: "1px solid #555",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "1rem",
                    boxSizing: "border-box",
                    marginBottom: "0.6rem",
                  }}
                />
                <button
                  className="m-btn m-btn-primary"
                  style={{ width: "100%", marginBottom: "0.4rem" }}
                  disabled={!manualSsid}
                  onClick={() => handleConnect(manualSsid, manualPassword)}
                >
                  Join
                </button>
                <button
                  className="m-btn m-btn-neutral"
                  style={{ width: "100%", fontSize: "0.8rem" }}
                  onClick={() => {
                    setShowManual(false);
                    setManualSsid("");
                    setManualPassword("");
                  }}
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
