import * as React from "react";
import {
  Box,
  Button,
  Cards,
  ContentLayout,
  FormField,
  Header,
  Input,
  Modal,
  SpaceBetween,
  Spinner,
  Toggle,
} from "@cloudscape-design/components";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useIsMobile } from "../../hooks/useIsMobile";
import { useStocksSettings } from "../../hooks/useStocksSettings";
import { updateStocksSettings } from "../../services/API";
import { getNotificationsContext, N } from "../../services/Notifications";
import { v4 as uuidv4 } from "uuid";

/* ── Shared logic ──────────────────────────────────────────────── */
function useStocks() {
  const qc = useQueryClient();
  const { pushNotification, dismissNotification, modifyNotificationContent } =
    getNotificationsContext();

  const { data: settings, isLoading } = useStocksSettings();

  const updateMut = useMutation({
    mutationFn: updateStocksSettings,
    onMutate: () => {
      const id = uuidv4();
      pushNotification({
        id,
        type: N.INFO,
        content: "Saving…",
        loading: true,
        dismissible: false,
        onDismiss: () => dismissNotification(id),
      });
      return { id };
    },
    onSuccess: (_, __, ctx) => {
      modifyNotificationContent(ctx.id, {
        content: "Saved.",
        type: N.SUCCESS,
        loading: false,
        dismissible: true,
        onDismiss: () => dismissNotification(ctx.id),
      });
      qc.invalidateQueries({ queryKey: ["stocksSettings"] });
    },
    onError: (err, _, ctx) => {
      modifyNotificationContent(ctx.id, {
        content: `Failed: ${err.message}`,
        type: N.ERROR,
        loading: false,
        dismissible: true,
        onDismiss: () => dismissNotification(ctx.id),
      });
    },
  });

  return { settings, isLoading, updateMut };
}

export default function Stocks() {
  const isMobile = useIsMobile();
  return isMobile ? <MobileStocks /> : <DesktopStocks />;
}

/* ── Mobile ────────────────────────────────────────────────────── */
function MobileStocks() {
  const { settings, isLoading, updateMut } = useStocks();
  const [editingSymbols, setEditingSymbols] = React.useState(false);
  const [symbolInput, setSymbolInput] = React.useState("");

  if (isLoading) return <div style={{ padding: 20, color: "#5a7a9a" }}>Loading…</div>;

  const {
    stock_abbrs = [],
    stock_cycles = [],
    interval_seconds,
    display_brightness,
    market_hours_only,
  } = settings || {};

  const saveSymbols = () => {
    const abbrs = symbolInput
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    updateMut.mutate({ stock_abbrs: abbrs });
    setEditingSymbols(false);
  };

  return (
    <div>
      <div className="m-section-title">Stocks</div>
      <div className="m-section-sub">Manage your stock display settings</div>

      {/* Watchlist */}
      <div className="m-card">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
          }}
        >
          <div className="m-card-title" style={{ marginBottom: 0 }}>
            Watchlist
          </div>
          <button
            className="m-btn m-btn-neutral"
            style={{ flex: "0 0 auto", width: "70px", height: "36px", fontSize: "0.8rem" }}
            onClick={() => {
              setSymbolInput(stock_abbrs.join(", "));
              setEditingSymbols(true);
            }}
          >
            Edit
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {stock_abbrs.map((s) => (
            <span key={s} className="m-badge m-badge-blue" style={{ fontSize: "0.9rem" }}>
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Chart cycles */}
      <div className="m-card">
        <div className="m-card-title">Chart Cycles</div>
        {stock_cycles.map((cycle) => (
          <div key={cycle.key} className="m-toggle-row">
            <div className="m-toggle-label">{cycle.label}</div>
            <Toggle
              checked={cycle.enabled}
              onChange={({ detail }) =>
                updateMut.mutate({
                  stock_cycles: stock_cycles.map((c) =>
                    c.key === cycle.key ? { ...c, enabled: detail.checked } : c
                  ),
                })
              }
            />
          </div>
        ))}
      </div>

      {/* Display settings */}
      <div className="m-card">
        <div className="m-card-title">Display Settings</div>
        <div className="m-status-row">
          <span className="m-label">Refresh Interval</span>
          <span className="m-badge m-badge-gray">{interval_seconds}s</span>
        </div>
        <div className="m-status-row">
          <span className="m-label">Brightness</span>
          <span className="m-badge m-badge-gray">{display_brightness}%</span>
        </div>
        <div className="m-status-row">
          <span className="m-label">Market Hours Only</span>
          <span className={`m-badge ${market_hours_only ? "m-badge-green" : "m-badge-gray"}`}>
            {market_hours_only ? "Yes" : "No"}
          </span>
        </div>
      </div>

      {editingSymbols && (
        <SymbolModal
          symbolInput={symbolInput}
          setSymbolInput={setSymbolInput}
          onSave={saveSymbols}
          onClose={() => setEditingSymbols(false)}
          saving={updateMut.isPending}
        />
      )}
    </div>
  );
}

/* ── Desktop ───────────────────────────────────────────────────── */
function DesktopStocks() {
  const { settings, isLoading, updateMut } = useStocks();
  const [editingSymbols, setEditingSymbols] = React.useState(false);
  const [symbolInput, setSymbolInput] = React.useState("");

  if (isLoading)
    return (
      <ContentLayout header={<Header variant="h1">Stocks</Header>}>
        <Spinner />
      </ContentLayout>
    );

  const {
    stock_abbrs = [],
    stock_cycles = [],
    interval_seconds,
    display_brightness,
    market_hours_only,
  } = settings || {};

  const saveSymbols = () => {
    const abbrs = symbolInput
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    updateMut.mutate({ stock_abbrs: abbrs });
    setEditingSymbols(false);
  };

  return (
    <ContentLayout header={<Header variant="h1">Stocks</Header>}>
      <SpaceBetween size="l">
        <Cards
          cardDefinition={{
            header: () => (
              <Header
                variant="h3"
                actions={
                  <Button
                    onClick={() => {
                      setSymbolInput(stock_abbrs.join(", "));
                      setEditingSymbols(true);
                    }}
                  >
                    Edit Watchlist
                  </Button>
                }
              >
                Watchlist
              </Header>
            ),
            sections: [
              {
                id: "symbols",
                content: () => (
                  <SpaceBetween direction="horizontal" size="s">
                    {stock_abbrs.map((s) => (
                      <Box key={s} fontSize="heading-m" fontWeight="bold">
                        {s}
                      </Box>
                    ))}
                  </SpaceBetween>
                ),
              },
            ],
          }}
          items={[{}]}
          cardsPerRow={[{ cards: 1 }]}
        />

        <Cards
          cardDefinition={{
            header: (c) => <Header variant="h4">{c.label}</Header>,
            sections: [
              {
                id: "toggle",
                content: (c) => (
                  <Toggle
                    checked={c.enabled}
                    onChange={({ detail }) =>
                      updateMut.mutate({
                        stock_cycles: stock_cycles.map((x) =>
                          x.key === c.key ? { ...x, enabled: detail.checked } : x
                        ),
                      })
                    }
                  >
                    {c.enabled ? "Enabled" : "Disabled"}
                  </Toggle>
                ),
              },
            ],
          }}
          cardsPerRow={[{ cards: 2 }, { minWidth: 500, cards: 4 }]}
          items={stock_cycles}
          header={<Header>Chart Cycles</Header>}
        />

        <Cards
          cardDefinition={{
            header: (item) => <Header variant="h4">{item.label}</Header>,
            sections: [{ id: "val", content: (item) => String(item.value) }],
          }}
          cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 3 }]}
          items={[
            { label: "Refresh Interval", value: `${interval_seconds}s` },
            { label: "Brightness", value: `${display_brightness}%` },
            { label: "Market Hours Only", value: market_hours_only ? "Yes" : "No" },
          ]}
          header={<Header>Display Settings</Header>}
        />
      </SpaceBetween>

      {editingSymbols && (
        <SymbolModal
          symbolInput={symbolInput}
          setSymbolInput={setSymbolInput}
          onSave={saveSymbols}
          onClose={() => setEditingSymbols(false)}
          saving={updateMut.isPending}
        />
      )}
    </ContentLayout>
  );
}

/* ── Shared symbol modal ───────────────────────────────────────── */
function SymbolModal({ symbolInput, setSymbolInput, onSave, onClose, saving }) {
  return (
    <Modal
      visible
      onDismiss={onClose}
      header={<Header>Edit Watchlist</Header>}
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" loading={saving} onClick={onSave}>
              Save
            </Button>
          </SpaceBetween>
        </Box>
      }
    >
      <FormField
        label="Stock Symbols"
        description="Comma-separated, up to 5 tickers (e.g. AAPL, MSFT, GOOG)"
      >
        <Input
          value={symbolInput}
          onChange={({ detail }) => setSymbolInput(detail.value)}
          placeholder="AAPL, MSFT"
          autoFocus
        />
      </FormField>
    </Modal>
  );
}
