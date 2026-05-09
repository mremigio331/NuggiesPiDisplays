import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { startDisplay, stopDisplay, switchDisplay, restartPi } from "../../services/API";
import Modal from "../../components/shared/Modal";

function useSystem() {
  const qc = useQueryClient();
  const { data: status, isLoading } = useSystemStatus();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["systemStatus"] });
  const startMut = useMutation({ mutationFn: startDisplay, onSuccess: invalidate });
  const stopMut = useMutation({ mutationFn: stopDisplay, onSuccess: invalidate });
  const switchMut = useMutation({ mutationFn: (m) => switchDisplay(m), onSuccess: invalidate });
  const restartMut = useMutation({ mutationFn: restartPi });
  const busy = startMut.isPending || stopMut.isPending || switchMut.isPending;
  const running = status?.running ?? false;
  const mode = status?.active_display ?? "—";
  return { isLoading, running, mode, busy, startMut, stopMut, switchMut, restartMut };
}

export default function System() {
  const { running, mode, busy, isLoading, startMut, stopMut, switchMut, restartMut } = useSystem();
  const [confirmRestart, setConfirmRestart] = React.useState(false);

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
        <div className="m-btn-row">
          <button
            className={`m-btn ${mode === "mta" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={busy}
            onClick={() => switchMut.mutate("mta")}
          >
            MTA
          </button>
          <button
            className={`m-btn ${mode === "stocks" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={busy}
            onClick={() => switchMut.mutate("stocks")}
          >
            Stocks
          </button>
          <button
            className={`m-btn ${mode === "clock" ? "m-btn-active" : "m-btn-neutral"}`}
            disabled={busy}
            onClick={() => switchMut.mutate("clock")}
          >
            Clock
          </button>
        </div>
      </div>

      <div className="m-card">
        <div className="m-card-title">Pi Actions</div>
        <button
          className="m-btn m-btn-neutral"
          style={{ width: "100%" }}
          onClick={() => setConfirmRestart(true)}
        >
          🔄 Restart Pi
        </button>
      </div>

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
    </div>
  );
}
