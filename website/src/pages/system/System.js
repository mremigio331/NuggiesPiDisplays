import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { DISPLAY_MODES, LOG_LEVELS } from "../../constants/display";
import {
  startDisplay,
  stopDisplay,
  switchDisplay,
  restartPi,
  restartApi,
  restartDisplay,
  restartWebsite,
  factoryReset,
  factoryResetWifi,
  getDevMode,
  forgetWifi,
  updateApp,
  getLogLevel,
  setLogLevel,
  getUpdateStatus,
  checkUpdate,
  getUpdateLog,
  getUpdateStage,
  setUpdateStage,
  getWifiStatus,
} from "../../services/API";
import Modal from "../../components/shared/Modal";

const SETUP_AP_PASSWORD = "SetUpNuggies";
// The address a client uses to reach this device WHILE the setup AP/portal is
// up. DNS is hijacked by the portal in that mode, so the .local name will not
// resolve to the setup page — only the fixed portal IP works. This matches the
// address discipline used on the WiFi setup page.
const PORTAL_ADDRESS = "10.42.0.1";

function useSystem() {
  const qc = useQueryClient();
  const { data: status, isLoading } = useSystemStatus();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["systemStatus"] });
  const startMut = useMutation({ mutationFn: startDisplay, onSuccess: invalidate });
  const stopMut = useMutation({ mutationFn: stopDisplay, onSuccess: invalidate });
  const switchMut = useMutation({ mutationFn: (m) => switchDisplay(m), onSuccess: invalidate });
  const restartMut = useMutation({ mutationFn: restartPi });
  const restartApiMut = useMutation({ mutationFn: restartApi });
  const restartDisplayMut = useMutation({ mutationFn: restartDisplay, onSuccess: invalidate });
  const restartWebsiteMut = useMutation({ mutationFn: restartWebsite });
  const factoryResetMut = useMutation({ mutationFn: factoryReset, onSuccess: invalidate });
  const factoryResetWifiMut = useMutation({ mutationFn: factoryResetWifi });
  const forgetWifiMut = useMutation({ mutationFn: forgetWifi });
  // Accepts an optional { component, force }. No args => full update + reboot
  // (classic behaviour). component scopes to one part; force reinstalls anyway.
  const updateAppMut = useMutation({
    mutationFn: (opts = {}) => updateApp(true, opts.component ?? null, opts.force ?? false),
  });
  const { data: updateStatus, isFetching: updateChecking } = useQuery({
    queryKey: ["updateStatus"],
    queryFn: getUpdateStatus,
    staleTime: 3600000,
    retry: false,
  });
  const checkUpdateMut = useMutation({
    mutationFn: checkUpdate,
    onSuccess: (data) => qc.setQueryData(["updateStatus"], data),
  });
  // Release stage (beta/prod) this device tracks. Changing it re-checks updates
  // so the per-component "behind" counts reflect the newly selected stream.
  const { data: stageData } = useQuery({ queryKey: ["updateStage"], queryFn: getUpdateStage });
  const updateStage = stageData?.stage ?? "prod";
  const setStageMut = useMutation({
    mutationFn: (stage) => setUpdateStage(stage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["updateStage"] });
      checkUpdateMut.mutate();
    },
  });
  const { data: devConfig } = useQuery({ queryKey: ["devMode"], queryFn: getDevMode });
  const devMode = devConfig?.dev_mode ?? false;
  // Derived device address for the post-reboot "your device is on your network"
  // instruction. mdns_name is "<hostname>.local"; ip is the IPv4 fallback for
  // clients that can't resolve .local. Nothing is hardcoded — a device whose
  // hostname is "nuggies" naturally yields that same .local name (preservation
  // 3.9), because the address comes straight from the API.
  const { data: wifiStatus } = useQuery({ queryKey: ["wifiStatus"], queryFn: getWifiStatus });
  const { data: logLevelData, refetch: refetchLogLevel } = useQuery({
    queryKey: ["logLevel"],
    queryFn: getLogLevel,
  });
  const currentLogLevel = logLevelData?.log_level ?? "INFO";
  const setLogLevelMut = useMutation({
    mutationFn: (level) => setLogLevel(level),
    onSuccess: refetchLogLevel,
  });
  const busy = startMut.isPending || stopMut.isPending || switchMut.isPending;
  const running = status?.running ?? false;
  const mode = status?.active_display ?? "—";
  return {
    isLoading,
    running,
    mode,
    busy,
    startMut,
    stopMut,
    switchMut,
    restartMut,
    restartApiMut,
    restartDisplayMut,
    restartWebsiteMut,
    factoryResetMut,
    factoryResetWifiMut,
    forgetWifiMut,
    updateAppMut,
    updateStatus,
    updateChecking,
    checkUpdateMut,
    updateStage,
    setStageMut,
    devMode,
    currentLogLevel,
    setLogLevelMut,
    mdnsName: wifiStatus?.mdns_name ?? null,
    deviceIp: wifiStatus?.ip ?? null,
    // Visible setup-AP SSID, derived server-side from the hostname (never hardcoded).
    setupSsid: wifiStatus?.setup_ssid ?? "NuggiesDisplay",
  };
}

// Renders this device's post-reboot address: <hostname>.local with the IPv4 as
// an explicit fallback for clients that cannot resolve .local. Falls back to
// generic wording while the wifi-status query hasn't resolved or returned null.
function DerivedAddress({ mdnsName, deviceIp }) {
  if (!mdnsName && !deviceIp) {
    return <strong style={{ color: "#fff" }}>your device&apos;s address</strong>;
  }
  return (
    <>
      {mdnsName && <strong style={{ color: "#fff" }}>{mdnsName}</strong>}
      {mdnsName && deviceIp && " "}
      {deviceIp && (
        <span style={{ color: "#aaa" }}>
          (or <strong style={{ color: "#fff" }}>{deviceIp}</strong> if{" "}
          {mdnsName ? mdnsName : "the .local name"} doesn&apos;t resolve)
        </span>
      )}
    </>
  );
}

function formatChecked(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// Order + labels for the per-component update rows. Keys match the API's
// updateStatus.components and setup.sh's --update-<component> flags.
const UPDATE_COMPONENTS = [
  { key: "website", label: "Website" },
  { key: "api", label: "API" },
  { key: "display", label: "Display" },
  { key: "system", label: "System" },
];

// Per-component update controls. Reads updateStatus.components (added by the API)
// and renders one row per component: a badge (up to date / N behind) and, when
// behind, a scoped "Update" button that updates only that part. Always offers a
// "Force full reinstall" that reinstalls everything regardless of the diff.
function ComponentUpdates({ updateStatus, updateAppMut }) {
  const components = updateStatus?.components ?? null;
  const pending = updateAppMut.isPending || updateAppMut.isSuccess;
  // Older API with no per-component data: render nothing (the full button above
  // still works). This keeps the UI functional mid-deploy before the API ships.
  if (!components) return null;

  const behindKeys = UPDATE_COMPONENTS.filter((c) => (components[c.key]?.behind ?? 0) > 0).map(
    (c) => c.key
  );
  const multiple = behindKeys.length > 1;

  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 8,
        padding: "0.5rem 0.65rem",
        margin: "0.25rem 0 0.6rem",
        background: "#161616",
      }}
    >
      <div style={{ color: "#aaa", fontSize: "0.75rem", marginBottom: 6, fontWeight: 600 }}>
        By component
      </div>
      {UPDATE_COMPONENTS.map(({ key, label }) => {
        const behind = components[key]?.behind ?? 0;
        const isBehind = behind > 0;
        return (
          <div
            key={key}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              padding: "3px 0",
            }}
          >
            <span style={{ color: "#ddd", fontSize: "0.82rem" }}>
              {label}{" "}
              <span style={{ color: isBehind ? "#f0a800" : "#6a6a6a", fontSize: "0.75rem" }}>
                {isBehind ? `· ${behind} behind` : "· up to date"}
              </span>
            </span>
            <button
              className={isBehind ? "m-btn m-btn-primary" : "m-btn m-btn-neutral"}
              style={{
                padding: "2px 10px",
                fontSize: "0.75rem",
                opacity: isBehind ? 1 : 0.5,
                ...(isBehind ? { background: "#c47d00", borderColor: "#c47d00" } : {}),
              }}
              disabled={!isBehind || pending}
              onClick={() => updateAppMut.mutate({ component: key })}
            >
              Update
            </button>
          </div>
        );
      })}

      {multiple && (
        <div style={{ color: "#f0a800", fontSize: "0.72rem", marginTop: 6, lineHeight: 1.4 }}>
          ⚠️ {behindKeys.length} components changed in this release. Updating one alone can leave
          parts out of sync (e.g. the website calling an API endpoint that isn&apos;t updated yet).
          Updating together is recommended.
        </div>
      )}

      <button
        className="m-btn m-btn-neutral"
        style={{ width: "100%", marginTop: 8, padding: "4px 10px", fontSize: "0.75rem" }}
        disabled={pending}
        onClick={() => updateAppMut.mutate({ component: "all", force: true })}
        title="Pull latest and reinstall every component, even ones that did not change."
      >
        ♻️ Force full reinstall
      </button>
    </div>
  );
}

function UpdateSection({
  updateStatus,
  updateChecking,
  checkUpdateMut,
  updateAppMut,
  updateStage,
  setStageMut,
  onConfirmUpdate,
}) {
  const updateAvailable = updateStatus?.update_available ?? false;
  const commitsBehind = updateStatus?.commits_behind ?? 0;
  const commits = updateStatus?.commits ?? [];
  const lastChecked = formatChecked(updateStatus?.last_checked);
  const checking = updateChecking || checkUpdateMut.isPending;
  const [showCommits, setShowCommits] = React.useState(false);

  return (
    <div>
      {updateStage && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: "0.6rem",
            padding: "0.4rem 0.55rem",
            border: "1px solid #333",
            borderRadius: 8,
            background: "#161616",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ color: "#ddd", fontSize: "0.78rem", fontWeight: 600 }}>
              Get beta updates
            </span>
            <span style={{ color: "#888", fontSize: "0.68rem" }}>
              Early builds, before they're approved for everyone.
            </span>
          </div>
          <label
            style={{
              marginLeft: "auto",
              display: "inline-flex",
              alignItems: "center",
              cursor: setStageMut.isPending ? "default" : "pointer",
            }}
            title="On = beta (early builds). Off = prod (approved updates only)."
          >
            <input
              type="checkbox"
              checked={updateStage === "beta"}
              disabled={setStageMut.isPending}
              onChange={(e) => setStageMut.mutate(e.target.checked ? "beta" : "prod")}
              style={{ width: 18, height: 18, cursor: "inherit", accentColor: "#2f6f3e" }}
            />
          </label>
        </div>
      )}
      {updateStage === "beta" && (
        <div
          style={{ color: "#f0a800", fontSize: "0.72rem", marginBottom: "0.5rem", lineHeight: 1.4 }}
        >
          You're on <strong>beta</strong> — you get each build right away, before it's approved for
          everyone. Turn this off for approved-only updates.
        </div>
      )}
      {updateAvailable ? (
        <>
          <button
            className="m-btn m-btn-primary"
            style={{
              width: "100%",
              marginBottom: "0.5rem",
              background: "#c47d00",
              borderColor: "#c47d00",
            }}
            onClick={onConfirmUpdate}
            disabled={updateAppMut.isPending || updateAppMut.isSuccess}
          >
            {updateAppMut.isSuccess ? "Rebooting…" : `⬆️ Update Available — Install & Reboot`}
          </button>
          <div style={{ color: "#f0a800", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
            {commitsBehind} commit{commitsBehind !== 1 ? "s" : ""} behind •{" "}
            {updateStatus?.current_sha} → {updateStatus?.latest_sha}
          </div>
          {commits.length > 0 && (
            <div style={{ marginBottom: "0.5rem" }}>
              <button
                type="button"
                onClick={() => setShowCommits((v) => !v)}
                aria-expanded={showCommits}
                style={{
                  background: "none",
                  border: "none",
                  color: "#f0a800",
                  fontSize: "0.8rem",
                  cursor: "pointer",
                  padding: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    transform: showCommits ? "rotate(90deg)" : "rotate(0deg)",
                    transition: "transform 0.15s ease",
                  }}
                >
                  ▶
                </span>
                {showCommits ? "Hide" : "What's included"} ({commits.length})
              </button>
              {showCommits && (
                <ul
                  style={{
                    listStyle: "disc",
                    paddingLeft: 22,
                    margin: "0.4rem 0 0",
                    maxHeight: 180,
                    overflowY: "auto",
                    color: "#ddd",
                    fontSize: "0.8rem",
                    lineHeight: 1.6,
                    background: "#1a1a1a",
                    borderRadius: 6,
                    padding: "0.5rem 0.5rem 0.5rem 1.4rem",
                  }}
                >
                  {commits.map((msg, i) => (
                    <li key={i} style={{ wordBreak: "break-word" }}>
                      {msg}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      ) : (
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginBottom: "0.5rem", opacity: updateStatus ? 0.6 : 1 }}
          onClick={onConfirmUpdate}
          disabled={updateAppMut.isPending || updateAppMut.isSuccess}
        >
          {updateAppMut.isSuccess ? "Rebooting…" : "⬆️ Update & Reboot"}
        </button>
      )}
      {updateAppMut.isSuccess && (
        <div style={{ color: "#5cb85c", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
          Update started — Pi will reboot shortly.
        </div>
      )}
      <ComponentUpdates updateStatus={updateStatus} updateAppMut={updateAppMut} />
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "0.25rem" }}>
        <button
          className="m-btn m-btn-neutral"
          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
          disabled={checking}
          onClick={() => checkUpdateMut.mutate()}
        >
          {checking ? "Checking…" : "Check for Update"}
        </button>
        {lastChecked && !checking && (
          <span style={{ color: "#888", fontSize: "0.75rem" }}>
            {updateStatus?.error
              ? "Check failed"
              : updateAvailable
                ? "Update available"
                : "Up to date"}{" "}
            · checked {lastChecked}
          </span>
        )}
      </div>
      <div className="m-form-desc">Pulls latest code from git, re-runs setup, then reboots.</div>
    </div>
  );
}

const UPDATE_LOG_START = "=== NUGGIES UPDATE START ===";
const UPDATE_LOG_COMPLETE = "=== NUGGIES UPDATE COMPLETE ===";
const UPDATE_LOG_FAILED = "=== NUGGIES UPDATE FAILED ===";

// Live progress view for an in-flight update. Polls /system/update-log on an
// interval, appending each new chunk. It is reconnect-safe by design: the update
// restarts the API and reboots the Pi mid-run, so poll failures are expected —
// they are shown as "reconnecting" rather than errors, and polling continues
// until the content indicates completion/failure or the user closes the modal.
function UpdateProgressModal({ visible, onClose, runId = "", alreadyRunning = false }) {
  const [lines, setLines] = React.useState("");
  // starting | running | reconnecting | failed | rebooting | complete
  const [phase, setPhase] = React.useState("starting");
  const offsetRef = React.useRef(0);
  const textRef = React.useRef(""); // full accumulated log, for classification
  const matchedRef = React.useRef(false); // have we locked onto THIS run's log yet?
  const preRef = React.useRef(null);

  React.useEffect(() => {
    if (!visible) {
      // Reset for the next run.
      setLines("");
      setPhase("starting");
      offsetRef.current = 0;
      textRef.current = "";
      matchedRef.current = false;
      return undefined;
    }

    let cancelled = false;
    let timer = null;

    // Derive phase from the full accumulated log. A terminal phase
    // (complete/failed) is sticky — once reached we stop polling.
    const classify = (all) => {
      if (all.includes(UPDATE_LOG_FAILED) || all.includes("a password is required")) {
        return "failed";
      }
      if (all.includes(UPDATE_LOG_COMPLETE)) return "complete";
      if (/--reboot requested|Rebooting to apply update|Rebooting Pi/i.test(all)) {
        return "rebooting";
      }
      if (all.includes(UPDATE_LOG_START)) return "running";
      return "starting";
    };

    const poll = async () => {
      try {
        const res = await getUpdateLog(offsetRef.current, runId);
        if (cancelled) return;

        // Only show THIS run. Until the log on disk is our run_id, the file may
        // still hold a PREVIOUS update's output — ignore it and keep showing
        // "starting" so the user never sees the last run before their own.
        // (When runId is empty, res.match is true and we attach to whatever's
        // there — the legacy attach-to-latest behaviour.)
        if (res.exists && res.match) {
          if (!matchedRef.current) {
            // First poll that matched: start fresh from the top of this run.
            matchedRef.current = true;
            offsetRef.current = 0;
            textRef.current = "";
            const full = await getUpdateLog(0, runId);
            if (!cancelled && full.match) {
              textRef.current = full.content || "";
              offsetRef.current = full.offset;
              setLines(textRef.current);
            }
          } else if (res.content) {
            offsetRef.current = res.offset;
            textRef.current += res.content;
            setLines(textRef.current);
          } else {
            offsetRef.current = res.offset;
          }

          const next = classify(textRef.current);
          setPhase(next);
          if (next === "complete" || next === "failed") {
            return; // terminal — stop polling
          }
        } else {
          // Our run hasn't stamped the log yet (the detached setup.sh is still
          // spinning up) — stay in "starting".
          setPhase((p) => (p === "running" || p === "rebooting" ? p : "starting"));
        }
      } catch (e) {
        // Poll failed — the API is almost certainly restarting/rebooting as part
        // of the update. Treat as "reconnecting" unless we already saw a
        // terminal/rebooting state, and keep trying.
        if (!cancelled) {
          setPhase((p) =>
            p === "failed" || p === "complete" || p === "rebooting" ? p : "reconnecting"
          );
        }
      }
      if (!cancelled) timer = setTimeout(poll, 1200);
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [visible, runId]);

  // Keep the log scrolled to the bottom as new lines arrive.
  React.useEffect(() => {
    if (preRef.current) preRef.current.scrollTop = preRef.current.scrollHeight;
  }, [lines]);

  const statusLine = {
    starting: { text: "Starting update…", color: "#f0a800" },
    running: { text: "Updating…", color: "#f0a800" },
    reconnecting: { text: "Pi is restarting — reconnecting…", color: "#f0a800" },
    rebooting: {
      text: "Update applied — Pi is rebooting. This page will reconnect shortly.",
      color: "#5cb85c",
    },
    complete: {
      text: "✓ Update complete — you can close this window.",
      color: "#5cb85c",
    },
    failed: { text: "Update failed. See the log below.", color: "#e05050" },
  }[phase];

  const done = phase === "complete" || phase === "failed";

  return (
    <Modal
      visible={visible}
      onDismiss={onClose}
      header={done ? (phase === "complete" ? "Update Complete" : "Update Failed") : "Updating"}
      footer={
        <div className="m-btn-row">
          <button className={`m-btn ${done ? "m-btn-primary" : "m-btn-neutral"}`} onClick={onClose}>
            Close
          </button>
        </div>
      }
    >
      <div style={{ color: statusLine.color, fontSize: "0.9rem", marginBottom: 8 }}>
        {statusLine.text}
      </div>
      <pre
        ref={preRef}
        style={{
          background: "#0e0e0e",
          color: "#cfe3cf",
          fontSize: "0.75rem",
          lineHeight: 1.5,
          padding: "0.6rem",
          borderRadius: 6,
          maxHeight: 300,
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          margin: 0,
        }}
      >
        {lines || "Waiting for output…"}
      </pre>
    </Modal>
  );
}

export default function System() {
  const {
    running,
    mode,
    busy,
    isLoading,
    startMut,
    stopMut,
    switchMut,
    restartMut,
    restartApiMut,
    restartDisplayMut,
    restartWebsiteMut,
    factoryResetMut,
    factoryResetWifiMut,
    forgetWifiMut,
    updateAppMut,
    updateStatus,
    updateChecking,
    checkUpdateMut,
    updateStage,
    setStageMut,
    devMode,
    currentLogLevel,
    setLogLevelMut,
    mdnsName,
    deviceIp,
    setupSsid,
  } = useSystem();
  const navigate = useNavigate();
  const [confirmRestart, setConfirmRestart] = React.useState(false);
  const [confirmReset, setConfirmReset] = React.useState(false);
  const [confirmResetWifi, setConfirmResetWifi] = React.useState(false);
  const [confirmForgetWifi, setConfirmForgetWifi] = React.useState(false);
  const [confirmUpdate, setConfirmUpdate] = React.useState(false);
  const [showUpdateProgress, setShowUpdateProgress] = React.useState(false);
  const [showResetWifiInstructions, setShowResetWifiInstructions] = React.useState(false);

  return (
    <div>
      <div className="m-section-title">System</div>
      <div className="m-section-sub">Display power and Pi management</div>

      <div className="m-card">
        <div className="m-card-title">Status</div>
        <div className="m-status-row">
          <span className="m-label">Display</span>
          {isLoading ? (
            <span className="m-badge m-badge-gray">Checking…</span>
          ) : running ? (
            <span className="m-badge m-badge-green">Running</span>
          ) : (
            <span className="m-badge m-badge-red">Stopped</span>
          )}
        </div>
        <div className="m-status-row">
          <span className="m-label">Mode</span>
          <span className="m-badge m-badge-blue">{mode.toUpperCase()}</span>
        </div>
      </div>

      <div className="m-card">
        <div className="m-card-title">Power</div>
        <div className="m-btn-row">
          <button
            className="m-btn m-btn-primary"
            disabled={busy || running}
            onClick={() => startMut.mutate()}
          >
            Turn On
          </button>
          <button
            className="m-btn m-btn-danger"
            disabled={busy || !running}
            onClick={() => stopMut.mutate()}
          >
            Turn Off
          </button>
        </div>
      </div>

      <div className="m-card">
        <div className="m-card-title">Switch Mode</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {DISPLAY_MODES.map(({ key, label }) => (
            <button
              key={key}
              className={`m-btn ${mode === key ? "m-btn-active" : "m-btn-neutral"}`}
              disabled={busy}
              onClick={() => switchMut.mutate(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="m-card">
        <div className="m-card-title">Pi Actions</div>

        <UpdateSection
          updateStatus={updateStatus}
          updateChecking={updateChecking}
          checkUpdateMut={checkUpdateMut}
          updateAppMut={updateAppMut}
          updateStage={updateStage}
          setStageMut={setStageMut}
          onConfirmUpdate={() => setConfirmUpdate(true)}
        />

        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginTop: "0.75rem" }}
          onClick={() => setConfirmRestart(true)}
        >
          🔄 Restart Pi
        </button>
      </div>

      <div className="m-card">
        <div className="m-card-title">Restart Services</div>
        <div className="m-form-desc" style={{ marginBottom: "0.75rem" }}>
          Restart an individual service without rebooting the whole Pi.
        </div>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%" }}
          disabled={restartApiMut.isPending}
          onClick={() => restartApiMut.mutate()}
        >
          {restartApiMut.isPending ? "Restarting…" : "Restart API Service"}
        </button>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginTop: 8 }}
          disabled={restartDisplayMut.isPending}
          onClick={() => restartDisplayMut.mutate()}
        >
          {restartDisplayMut.isPending ? "Restarting…" : "Restart Display Service"}
        </button>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginTop: 8 }}
          disabled={restartWebsiteMut.isPending}
          onClick={() => restartWebsiteMut.mutate()}
        >
          {restartWebsiteMut.isPending ? "Restarting…" : "Restart Website Service"}
        </button>
        {(restartApiMut.isSuccess ||
          restartDisplayMut.isSuccess ||
          restartWebsiteMut.isSuccess) && (
          <div style={{ color: "#5cb85c", fontSize: "0.8rem", marginTop: 8 }}>
            Restart triggered.
          </div>
        )}
        {(restartApiMut.isError || restartDisplayMut.isError || restartWebsiteMut.isError) && (
          <div style={{ color: "#e05050", fontSize: "0.8rem", marginTop: 8 }}>
            Restart failed. Check the service logs.
          </div>
        )}
      </div>

      <div className="m-card">
        <div className="m-card-title">Log Level</div>
        <div className="m-form-desc" style={{ marginBottom: "0.75rem" }}>
          Controls verbosity for API and display logs. DEBUG logs every request and API call.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
          {LOG_LEVELS.map((level) => (
            <button
              key={level}
              className={`m-btn ${currentLogLevel === level ? "m-btn-active" : "m-btn-neutral"}`}
              disabled={setLogLevelMut.isPending}
              onClick={() => setLogLevelMut.mutate(level)}
            >
              {level}
            </button>
          ))}
        </div>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginTop: "0.75rem" }}
          onClick={() => navigate("/system/logs")}
        >
          📋 View Logs
        </button>
      </div>

      <div className="m-card">
        <div className="m-card-title">Help</div>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%" }}
          onClick={() => navigate("/system/user-guide")}
        >
          📖 User Manual
        </button>
      </div>

      {devMode && (
        <div className="m-card" style={{ borderColor: "#4a3000" }}>
          <div className="m-card-title" style={{ color: "#f0a800" }}>
            Dev Mode
          </div>
          <button
            className="m-btn m-btn-neutral"
            style={{ width: "100%" }}
            disabled={forgetWifiMut.isPending}
            onClick={() => setConfirmForgetWifi(true)}
          >
            {forgetWifiMut.isPending ? "Clearing…" : "Forget WiFi"}
          </button>
          {forgetWifiMut.isSuccess && (
            <div style={{ color: "#5cb85c", fontSize: "0.8rem", marginTop: 8 }}>
              WiFi cleared. Use Restart Pi to re-run setup.
            </div>
          )}
          <div className="m-form-desc" style={{ marginTop: 8 }}>
            Removes saved WiFi connections and resets the setup flag. Settings untouched. Reboot to
            trigger the captive portal.
          </div>
        </div>
      )}

      <div className="m-card" style={{ borderColor: "#4a1a1a" }}>
        <div className="m-card-title" style={{ color: "#e05050" }}>
          Danger Zone
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <button
              className="m-btn m-btn-danger"
              style={{ width: "100%" }}
              onClick={() => setConfirmReset(true)}
            >
              Reset Settings
            </button>
            <div className="m-form-desc" style={{ marginTop: 6 }}>
              Restores all settings to factory defaults. WiFi and display stay on.
            </div>
          </div>
          <div>
            <button
              className="m-btn m-btn-danger"
              style={{ width: "100%", background: "#5a0a0a" }}
              onClick={() => setConfirmResetWifi(true)}
            >
              Factory Reset + WiFi Wipe
            </button>
            <div className="m-form-desc" style={{ marginTop: 6 }}>
              Resets all settings, removes all saved WiFi networks, and reboots. You'll need to
              reconnect via the {setupSsid} network.
            </div>
          </div>
        </div>
      </div>

      {factoryResetWifiMut.isSuccess && (
        <div
          className="m-card"
          style={{ borderColor: "#4a3000", background: "#1f1a10", marginTop: "0.75rem" }}
        >
          <div className="m-card-title" style={{ color: "#f0a800" }}>
            Reboot in progress
          </div>
          <div style={{ color: "#ddd", fontSize: "0.88rem", lineHeight: 1.7 }}>
            This page will disconnect shortly. Reconnect to <strong>{setupSsid}</strong> and open{" "}
            <strong>http://{PORTAL_ADDRESS}</strong> to continue setup. Once it&apos;s back on your
            network, reach it at <DerivedAddress mdnsName={mdnsName} deviceIp={deviceIp} />.
          </div>
        </div>
      )}

      <Modal
        visible={confirmUpdate}
        onDismiss={() => setConfirmUpdate(false)}
        header="Update & Reboot?"
        footer={
          <div className="m-btn-row">
            <button className="m-btn m-btn-neutral" onClick={() => setConfirmUpdate(false)}>
              Cancel
            </button>
            <button
              className="m-btn m-btn-primary"
              onClick={() => {
                updateAppMut.mutate();
                setConfirmUpdate(false);
                setShowUpdateProgress(true);
              }}
            >
              Update & Reboot
            </button>
          </div>
        }
      >
        <div style={{ color: "#f0a800", fontSize: "0.9rem" }}>
          Pulls the latest code from git, re-runs <strong>setup.sh --update</strong> (reinstall
          deps, rebuild the frontend, reapply permissions), then reboots. The Pi will be offline for
          ~60 seconds.
        </div>
      </Modal>

      <UpdateProgressModal
        visible={showUpdateProgress}
        runId={updateAppMut.data?.run_id ?? ""}
        alreadyRunning={updateAppMut.data?.already_running ?? false}
        onClose={() => setShowUpdateProgress(false)}
      />

      <Modal
        visible={confirmRestart}
        onDismiss={() => setConfirmRestart(false)}
        header="Restart Raspberry Pi?"
        footer={
          <div className="m-btn-row">
            <button className="m-btn m-btn-neutral" onClick={() => setConfirmRestart(false)}>
              Cancel
            </button>
            <button
              className="m-btn m-btn-danger"
              disabled={restartMut.isPending}
              onClick={() => {
                restartMut.mutate();
                setConfirmRestart(false);
              }}
            >
              {restartMut.isPending ? "Restarting…" : "Restart"}
            </button>
          </div>
        }
      >
        <div style={{ color: "#f0a800", fontSize: "0.9rem" }}>
          The Pi will reboot. Display and API will be offline for ~30 seconds.
        </div>
      </Modal>

      <Modal
        visible={confirmReset}
        onDismiss={() => setConfirmReset(false)}
        header="Reset Settings to Factory Defaults?"
        footer={
          <div className="m-btn-row">
            <button className="m-btn m-btn-neutral" onClick={() => setConfirmReset(false)}>
              Cancel
            </button>
            <button
              className="m-btn m-btn-danger"
              disabled={factoryResetMut.isPending}
              onClick={() => {
                factoryResetMut.mutate();
                setConfirmReset(false);
              }}
            >
              {factoryResetMut.isPending ? "Resetting…" : "Reset Settings"}
            </button>
          </div>
        }
      >
        <div style={{ color: "#f0a800", fontSize: "0.9rem" }}>
          All settings (stocks, weather, clock, MTA) will be wiped and restored to defaults. WiFi
          and the display connection are not affected.
        </div>
      </Modal>

      <Modal
        visible={confirmForgetWifi}
        onDismiss={() => setConfirmForgetWifi(false)}
        header="Forget WiFi?"
        footer={
          <div className="m-btn-row">
            <button className="m-btn m-btn-neutral" onClick={() => setConfirmForgetWifi(false)}>
              Cancel
            </button>
            <button
              className="m-btn m-btn-danger"
              disabled={forgetWifiMut.isPending}
              onClick={() => {
                forgetWifiMut.mutate();
                setConfirmForgetWifi(false);
              }}
            >
              Forget WiFi
            </button>
          </div>
        }
      >
        <div style={{ color: "#f0a800", fontSize: "0.9rem" }}>
          Saved WiFi connections will be removed and the setup flag cleared. Your settings stay
          intact. Use Restart Pi afterward to re-run the captive portal.
        </div>
      </Modal>

      <Modal
        visible={confirmResetWifi}
        onDismiss={() => setConfirmResetWifi(false)}
        header="Full Factory Reset?"
        footer={
          <div className="m-btn-row">
            <button className="m-btn m-btn-neutral" onClick={() => setConfirmResetWifi(false)}>
              Cancel
            </button>
            <button
              className="m-btn m-btn-danger"
              style={{ background: "#5a0a0a" }}
              disabled={factoryResetWifiMut.isPending}
              onClick={() => {
                factoryResetWifiMut.mutate(undefined, {
                  onSuccess: () => {
                    setConfirmResetWifi(false);
                    setShowResetWifiInstructions(true);
                  },
                  onError: () => {
                    setConfirmResetWifi(false);
                  },
                });
              }}
            >
              {factoryResetWifiMut.isPending ? "Wiping…" : "Factory Reset"}
            </button>
          </div>
        }
      >
        <div style={{ color: "#e05050", fontSize: "0.9rem", marginBottom: 8 }}>This will:</div>
        <ul
          style={{
            color: "#f0a800",
            fontSize: "0.85rem",
            paddingLeft: 18,
            margin: 0,
            lineHeight: 1.8,
          }}
        >
          <li>Reset all settings to factory defaults</li>
          <li>Remove all saved WiFi networks</li>
          <li>Reboot the Pi</li>
        </ul>
        <div style={{ color: "#aaa", fontSize: "0.8rem", marginTop: 10 }}>
          After reboot, connect to the <strong style={{ color: "#fff" }}>{setupSsid}</strong> WiFi
          network to reconfigure.
        </div>
      </Modal>

      <Modal
        visible={showResetWifiInstructions}
        onDismiss={() => setShowResetWifiInstructions(false)}
        header="Factory Reset Started"
        footer={
          <div className="m-btn-row">
            <button
              className="m-btn m-btn-primary"
              onClick={() => setShowResetWifiInstructions(false)}
            >
              Got It
            </button>
          </div>
        }
      >
        <div style={{ color: "#e05050", fontSize: "0.9rem", marginBottom: 8 }}>
          The Pi is rebooting now. This page will lose connection.
        </div>
        <ol
          style={{
            color: "#f0a800",
            fontSize: "0.85rem",
            paddingLeft: 18,
            margin: 0,
            lineHeight: 1.8,
          }}
        >
          <li>Open your phone/laptop WiFi list</li>
          <li>
            Join <strong style={{ color: "#fff" }}>{setupSsid}</strong>
          </li>
          <li>
            Password: <strong style={{ color: "#fff" }}>{SETUP_AP_PASSWORD}</strong>
          </li>
          <li>
            Open <strong style={{ color: "#fff" }}>http://{PORTAL_ADDRESS}</strong> to reconfigure
            WiFi
          </li>
        </ol>
        <div style={{ color: "#aaa", fontSize: "0.8rem", marginTop: 10, lineHeight: 1.7 }}>
          Once it&apos;s back on your network, reach it at{" "}
          <DerivedAddress mdnsName={mdnsName} deviceIp={deviceIp} />.
        </div>
      </Modal>
    </div>
  );
}
