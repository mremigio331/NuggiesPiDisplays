import * as React from "react";
import {
  Badge,
  Box,
  Button,
  ColumnLayout,
  Container,
  ContentLayout,
  Header,
  SpaceBetween,
  StatusIndicator,
} from "@cloudscape-design/components";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useIsMobile } from "../../hooks/useIsMobile";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { startDisplay, stopDisplay, switchDisplay } from "../../services/API";

export default function Home() {
  const isMobile = useIsMobile();
  return isMobile ? <MobileHome /> : <DesktopHome />;
}

/* ── Shared hook ───────────────────────────────────────────────── */
function useDisplayControl() {
  const qc = useQueryClient();
  const { data: status, isLoading } = useSystemStatus();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["systemStatus"] });
  const startMut = useMutation({ mutationFn: startDisplay, onSuccess: invalidate });
  const stopMut = useMutation({ mutationFn: stopDisplay, onSuccess: invalidate });
  const switchMut = useMutation({ mutationFn: (m) => switchDisplay(m), onSuccess: invalidate });
  const busy = startMut.isPending || stopMut.isPending || switchMut.isPending;
  const running = status?.running ?? false;
  const mode = status?.active_display ?? "—";
  return { status, isLoading, running, mode, busy, startMut, stopMut, switchMut };
}

/* ── Mobile ────────────────────────────────────────────────────── */
function MobileHome() {
  const { running, mode, busy, isLoading, startMut, stopMut, switchMut } = useDisplayControl();
  const navigate = useNavigate();

  return (
    <div>
      <div className="m-section-title">Dashboard</div>
      <div className="m-section-sub">Nuggies Pi Display Controller</div>

      {/* Status */}
      <div className="m-card">
        <div className="m-card-title">Display Status</div>
        <div className="m-status-row">
          <span className="m-label">State</span>
          {isLoading ? (
            <span className="m-badge m-badge-gray">Checking…</span>
          ) : running ? (
            <span className="m-badge m-badge-green">Running</span>
          ) : (
            <span className="m-badge m-badge-red">Stopped</span>
          )}
        </div>
        <div className="m-status-row">
          <span className="m-label">Active Mode</span>
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

      {/* Quick nav */}
      <div className="m-card">
        <div className="m-card-title">Quick Links</div>
        <div className="m-btn-row" style={{ flexWrap: "wrap" }}>
          {[
            { label: "🚇 MTA Trains", path: "/mta" },
            { label: "📊 Stock Info", path: "/stocks" },
            { label: "⚙️ MTA Settings", path: "/mta/settings" },
            { label: "🔧 System", path: "/system" },
          ].map(({ label, path }) => (
            <button
              key={path}
              className="m-btn m-btn-neutral"
              style={{ flex: "1 1 calc(50% - 5px)", marginBottom: 0 }}
              onClick={() => navigate(path)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Desktop ───────────────────────────────────────────────────── */
function DesktopHome() {
  const { running, mode, busy, isLoading, startMut, stopMut, switchMut } = useDisplayControl();
  const navigate = useNavigate();

  return (
    <ContentLayout header={<Header variant="h1">Dashboard</Header>}>
      <SpaceBetween size="l">
        <ColumnLayout columns={2} variant="text-grid">
          {/* Status */}
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
                <Box variant="awsui-key-label">Active Mode</Box>
                <Badge color={mode === "mta" ? "blue" : "green"}>{mode.toUpperCase()}</Badge>
              </Box>
            </SpaceBetween>
          </Container>

          {/* Controls */}
          <Container header={<Header variant="h2">Controls</Header>}>
            <SpaceBetween size="m">
              <Box>
                <Box variant="awsui-key-label">Power</Box>
                <SpaceBetween direction="horizontal" size="s">
                  <Button
                    variant="primary"
                    disabled={busy || running}
                    onClick={() => startMut.mutate()}
                  >
                    Turn On
                  </Button>
                  <Button disabled={busy || !running} onClick={() => stopMut.mutate()}>
                    Turn Off
                  </Button>
                </SpaceBetween>
              </Box>
              <Box>
                <Box variant="awsui-key-label">Switch Mode</Box>
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
              </Box>
            </SpaceBetween>
          </Container>
        </ColumnLayout>

        {/* Quick nav */}
        <Container header={<Header variant="h2">Navigate</Header>}>
          <SpaceBetween direction="horizontal" size="s">
            <Button onClick={() => navigate("/mta")}>🚇 MTA Trains</Button>
            <Button onClick={() => navigate("/stocks")}>📈 Stocks</Button>
            <Button onClick={() => navigate("/mta/settings")}>⚙️ MTA Settings</Button>
            <Button onClick={() => navigate("/system")}>🔧 System</Button>
          </SpaceBetween>
        </Container>
      </SpaceBetween>
    </ContentLayout>
  );
}
