import * as React from "react";
import {
  Alert,
  Box,
  Button,
  ColumnLayout,
  Container,
  ContentLayout,
  Header,
  Modal,
  SpaceBetween,
  StatusIndicator,
} from "@cloudscape-design/components";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useIsMobile } from "../../hooks/useIsMobile";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { startDisplay, stopDisplay, switchDisplay, restartPi } from "../../services/API";

/* ── Shared logic ──────────────────────────────────────────────── */
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
  const isMobile = useIsMobile();
  return isMobile ? <MobileSystem /> : <DesktopSystem />;
}

/* ── Mobile ────────────────────────────────────────────────────── */
function MobileSystem() {
  const { running, mode, busy, isLoading, startMut, stopMut, switchMut, restartMut } = useSystem();
  const [confirmRestart, setConfirmRestart] = React.useState(false);

  return (
    <div>
      <div className="m-section-title">System</div>
      <div className="m-section-sub">Display power and Pi management</div>

      {/* Status */}
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

      {/* Power */}
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

      {/* Mode */}
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
        </div>
      </div>

      {/* Pi actions */}
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

      {confirmRestart && (
        <Modal
          visible
          onDismiss={() => setConfirmRestart(false)}
          header="Restart Raspberry Pi?"
          footer={
            <Box float="right">
              <SpaceBetween direction="horizontal" size="xs">
                <Button variant="link" onClick={() => setConfirmRestart(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  loading={restartMut.isPending}
                  onClick={() => {
                    restartMut.mutate();
                    setConfirmRestart(false);
                  }}
                >
                  Restart
                </Button>
              </SpaceBetween>
            </Box>
          }
        >
          <Alert type="warning">
            The Pi will reboot. Display and API will be offline for ~30 seconds.
          </Alert>
        </Modal>
      )}
    </div>
  );
}

/* ── Desktop ───────────────────────────────────────────────────── */
function DesktopSystem() {
  const { running, mode, busy, isLoading, startMut, stopMut, switchMut, restartMut } = useSystem();
  const [confirmRestart, setConfirmRestart] = React.useState(false);

  return (
    <ContentLayout header={<Header variant="h1">System</Header>}>
      <SpaceBetween size="l">
        <ColumnLayout columns={2} variant="text-grid">
          <Container header={<Header variant="h2">Display Status</Header>}>
            <SpaceBetween size="m">
              <Box>
                <Box variant="awsui-key-label">State</Box>
                {isLoading ? (
                  <StatusIndicator type="loading">Loading</StatusIndicator>
                ) : running ? (
                  <StatusIndicator type="success">Running</StatusIndicator>
                ) : (
                  <StatusIndicator type="stopped">Stopped</StatusIndicator>
                )}
              </Box>
              <Box>
                <Box variant="awsui-key-label">Mode</Box>
                <Box fontWeight="bold">{mode.toUpperCase()}</Box>
              </Box>
            </SpaceBetween>
          </Container>

          <Container header={<Header variant="h2">Power</Header>}>
            <SpaceBetween direction="horizontal" size="s">
              <Button
                variant="primary"
                disabled={busy || running}
                loading={startMut.isPending}
                onClick={() => startMut.mutate()}
              >
                Turn On
              </Button>
              <Button
                disabled={busy || !running}
                loading={stopMut.isPending}
                onClick={() => stopMut.mutate()}
              >
                Turn Off
              </Button>
            </SpaceBetween>
          </Container>
        </ColumnLayout>

        <Container header={<Header variant="h2">Switch Mode</Header>}>
          <SpaceBetween direction="horizontal" size="s">
            <Button
              variant={mode === "mta" ? "primary" : "normal"}
              disabled={busy}
              onClick={() => switchMut.mutate("mta")}
            >
              MTA
            </Button>
            <Button
              variant={mode === "stocks" ? "primary" : "normal"}
              disabled={busy}
              onClick={() => switchMut.mutate("stocks")}
            >
              Stocks
            </Button>
          </SpaceBetween>
        </Container>

        <Container header={<Header variant="h2">Pi Actions</Header>}>
          <Button iconName="undo" onClick={() => setConfirmRestart(true)}>
            Restart Pi
          </Button>
        </Container>
      </SpaceBetween>

      <Modal
        visible={confirmRestart}
        onDismiss={() => setConfirmRestart(false)}
        header="Restart Raspberry Pi?"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setConfirmRestart(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={restartMut.isPending}
                onClick={() => {
                  restartMut.mutate();
                  setConfirmRestart(false);
                }}
              >
                Restart
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Alert type="warning">
          The Pi will reboot. Display and API will be offline for ~30 seconds.
        </Alert>
      </Modal>
    </ContentLayout>
  );
}
