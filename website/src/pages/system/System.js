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
  const updateAppMut = useMutation({ mutationFn: () => updateApp(true) });
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

function UpdateSection({
  updateStatus,
  updateChecking,
  checkUpdateMut,
  updateAppMut,
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

// Live progress view for an in-flight update. Polls /system/update-log on an
// interval, appending each new chunk. It is reconnect-safe by design: the update
// restarts the API and reboots the Pi mid-run, so poll failures are expected —
// they are shown as "reconnecting" rather than errors, and polling continues
// until the content indicates completion/failure or the user closes the modal.
function UpdateProgressModal({ visible, onClose }) {
  const [lines, setLines] = React.useState("");
  const [phase, setPhase] = React.useState("starting"); // starting | running | reconnecting | failed | rebooting
  const offsetRef = React.useRef(0);
  const preRef = React.useRef(null);

  React.useEffect(() => {
    if (!visible) {
      // Reset for the next run.
      setLines("");
      setPhase("starting");
      offsetRef.current = 0;
      return undefined;
    }

    let cancelled = false;
    let timer = null;

    const poll = async () => {
      try {
        const res = await getUpdateLog(offsetRef.current);
        if (cancelled) return;

        if (res.exists && res.content) {
          offsetRef.current = res.offset;
          setLines((prev) => prev + res.content);
        } else if (res.exists) {
          offsetRef.current = res.offset;
        }

        // Classify progress from the accumulated content.
        setLines((prev) => {
          const all = prev;
          if (all.includes("a password is required")) {
            setPhase("failed");
          } else if (/Rebooting to apply update|Rebooting Pi/i.test(all)) {
            setPhase("rebooting");
          } else if (res.started || all.includes(UPDATE_LOG_START)) {
            setPhase((p) => (p === "reconnecting" ? "running" : p === "starting" ? "running" : p));
          }
          return prev;
        });
      } catch (e) {
        // Poll failed — the API is almost certainly restarting/rebooting as part
        // of the update. Treat as "reconnecting", keep trying.
        if (!cancelled) setPhase((p) => (p === "failed" ? p : "reconnecting"));
      } finally {
        if (!cancelled) timer = setTimeout(poll, 1200);
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [visible]);

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
    failed: { text: "Update failed to start. See the log below.", color: "#e05050" },
  }[phase];

  return (
    <Modal
      visible={visible}
      onDismiss={onClose}
      header="Updating"
      footer={
        <div className="m-btn-row">
          <button className="m-btn m-btn-neutral" onClick={onClose}>
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
