import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import {
  startDisplay,
  stopDisplay,
  switchDisplay,
  restartPi,
  factoryReset,
  factoryResetWifi,
  getDevMode,
  forgetWifi,
  updateApp,
  getLogLevel,
  setLogLevel,
} from "../../services/API";
import Modal from "../../components/shared/Modal";

function useSystem() {
  const qc = useQueryClient();
  const { data: status, isLoading } = useSystemStatus();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["systemStatus"] });
  const startMut = useMutation({ mutationFn: startDisplay, onSuccess: invalidate });
  const stopMut = useMutation({ mutationFn: stopDisplay, onSuccess: invalidate });
  const switchMut = useMutation({ mutationFn: (m) => switchDisplay(m), onSuccess: invalidate });
  const restartMut = useMutation({ mutationFn: restartPi });
  const factoryResetMut = useMutation({ mutationFn: factoryReset, onSuccess: invalidate });
  const factoryResetWifiMut = useMutation({ mutationFn: factoryResetWifi });
  const forgetWifiMut = useMutation({ mutationFn: forgetWifi });
  const updateAppMut = useMutation({ mutationFn: () => updateApp(true) });
  const { data: devConfig } = useQuery({ queryKey: ["devMode"], queryFn: getDevMode });
  const devMode = devConfig?.dev_mode ?? false;
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
    factoryResetMut,
    factoryResetWifiMut,
    forgetWifiMut,
    updateAppMut,
    devMode,
    currentLogLevel,
    setLogLevelMut,
  };
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
    factoryResetMut,
    factoryResetWifiMut,
    forgetWifiMut,
    updateAppMut,
    devMode,
    currentLogLevel,
    setLogLevelMut,
  } = useSystem();
  const [confirmRestart, setConfirmRestart] = React.useState(false);
  const [confirmReset, setConfirmReset] = React.useState(false);
  const [confirmResetWifi, setConfirmResetWifi] = React.useState(false);
  const [confirmForgetWifi, setConfirmForgetWifi] = React.useState(false);
  const [confirmUpdate, setConfirmUpdate] = React.useState(false);

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
          {[
            { key: "clock", label: "Clock" },
            { key: "mta", label: "MTA" },
            { key: "stocks", label: "Stocks" },
            { key: "weather", label: "Weather" },
          ].map(({ key, label }) => (
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
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%", marginBottom: "0.5rem" }}
          onClick={() => setConfirmUpdate(true)}
          disabled={updateAppMut.isPending || updateAppMut.isSuccess}
        >
          {updateAppMut.isSuccess ? "Rebooting…" : "⬆️ Update & Reboot"}
        </button>
        {updateAppMut.isSuccess && (
          <div style={{ color: "#5cb85c", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
            Update started — Pi will reboot shortly.
          </div>
        )}
        <div className="m-form-desc" style={{ marginBottom: "0.75rem" }}>
          Pulls latest code from git, re-runs setup, then reboots.
        </div>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%" }}
          onClick={() => setConfirmRestart(true)}
        >
          🔄 Restart Pi
        </button>
      </div>

      <div className="m-card">
        <div className="m-card-title">Log Level</div>
        <div className="m-form-desc" style={{ marginBottom: "0.75rem" }}>
          Controls verbosity for API and display logs. DEBUG logs every request and API call.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
          {["DEBUG", "INFO", "WARNING", "ERROR"].map((level) => (
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
              reconnect via the NuggiesSetup network.
            </div>
          </div>
        </div>
      </div>

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
              }}
            >
              Update & Reboot
            </button>
          </div>
        }
      >
        <div>
          Pulls the latest code from git, re-runs <strong>setup.sh</strong> in{" "}
          <strong>{devMode ? "--dev" : "--prod"}</strong> mode, then reboots. The Pi will be offline
          for ~60 seconds.
        </div>
      </Modal>

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
                factoryResetWifiMut.mutate();
                setConfirmResetWifi(false);
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
          After reboot, connect to the <strong style={{ color: "#fff" }}>NuggiesSetup</strong> WiFi
          network to reconfigure.
        </div>
      </Modal>
    </div>
  );
}
