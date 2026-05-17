import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useStocksSettings } from "../../hooks/useStocksSettings";
import { useDebounce } from "../../hooks/useDebounce";
import { useNotify } from "../../hooks/useNotify";
import { updateStocksSettings, searchStocks } from "../../services/API";
import SettingsHeader from "../../components/shared/SettingsHeader";
import LoadingSpinner from "../../components/shared/LoadingSpinner";

function useUpdateStocks() {
  const qc = useQueryClient();
  const { start, ok, fail } = useNotify();

  return useMutation({
    mutationFn: updateStocksSettings,
    onMutate: () => ({ id: start() }),
    onSuccess: (_, __, ctx) => {
      ok(ctx.id);
      qc.invalidateQueries({ queryKey: ["stocksSettings"] });
    },
    onError: (err, _, ctx) => fail(ctx.id, err),
  });
}

/* ── Watchlist section ─────────────────────────────────────────── */
function WatchlistSection({ currentSymbols, onSave, saving }) {
  const [symbols, setSymbols] = React.useState(currentSymbols);
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounce(search, 300);

  React.useEffect(() => {
    setSymbols(currentSymbols);
  }, [currentSymbols.join(",")]);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ["stockSearch", debouncedSearch],
    queryFn: () => searchStocks(debouncedSearch),
    enabled: debouncedSearch.length >= 1,
    staleTime: 30000,
  });

  const add = (symbol) => {
    if (!symbols.includes(symbol) && symbols.length < 5) setSymbols((prev) => [...prev, symbol]);
  };
  const remove = (symbol) => setSymbols((prev) => prev.filter((s) => s !== symbol));
  const atLimit = symbols.length >= 5;
  const isDirty = symbols.join(",") !== currentSymbols.join(",");

  return (
    <div className="m-card">
      <div className="m-card-title">Watchlist</div>

      {/* Current symbols */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: "0.75rem", color: "#5a7a9a", marginBottom: 6 }}>
          {symbols.length} / 5 stocks
          {atLimit && <span style={{ color: "#e05050" }}> — limit reached</span>}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {symbols.length === 0 && (
            <span style={{ color: "#5a7a9a", fontSize: "0.85rem" }}>No stocks added yet</span>
          )}
          {symbols.map((s) => (
            <span
              key={s}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "4px 10px",
                borderRadius: 12,
                background: "#1a3a5a",
                color: "#7eb8f7",
                fontSize: "0.85rem",
                fontWeight: 700,
              }}
            >
              {s}
              <button
                onClick={() => remove(s)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#7eb8f7",
                  cursor: "pointer",
                  padding: 0,
                  lineHeight: 1,
                  fontSize: "1rem",
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Search */}
      <input
        className="m-input"
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by name or ticker…"
        style={{ marginBottom: 6 }}
      />
      <div
        style={{
          border: "1px solid #1a2a40",
          borderRadius: 8,
          maxHeight: 240,
          overflowY: "auto",
          background: "#0a1628",
          marginBottom: 14,
        }}
      >
        {debouncedSearch.length === 0 && (
          <div style={{ padding: "10px 12px", color: "#5a7a9a", fontSize: "0.85rem" }}>
            Start typing to search stocks
          </div>
        )}
        {debouncedSearch.length > 0 && isFetching && (
          <div style={{ padding: "10px 12px", color: "#5a7a9a", fontSize: "0.85rem" }}>
            Searching…
          </div>
        )}
        {debouncedSearch.length > 0 && !isFetching && results.length === 0 && (
          <div style={{ padding: "10px 12px", color: "#5a7a9a", fontSize: "0.85rem" }}>
            No results for "{debouncedSearch}"
          </div>
        )}
        {results.map((r) => {
          const already = symbols.includes(r.symbol);
          const disabled = already || atLimit;
          return (
            <div
              key={r.symbol}
              onClick={() => !disabled && add(r.symbol)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "9px 12px",
                borderBottom: "1px solid #1a2a40",
                cursor: disabled ? "default" : "pointer",
                background: already ? "#0a1a3a" : "transparent",
                opacity: !already && atLimit ? 0.45 : 1,
              }}
            >
              <div>
                <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "#e8f0f8" }}>
                  {r.symbol}
                </span>
                {r.name && (
                  <span style={{ marginLeft: 8, color: "#5a7a9a", fontSize: "0.82rem" }}>
                    {r.name}
                  </span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                {r.exchange && (
                  <span style={{ fontSize: "0.75rem", color: "#5a7a9a" }}>{r.exchange}</span>
                )}
                {already ? (
                  <span style={{ fontSize: "0.75rem", color: "#4a9fe8" }}>Added</span>
                ) : (
                  !atLimit && <span style={{ fontSize: "0.8rem", color: "#4a9fe8" }}>+ Add</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {isDirty && (
        <button
          className="m-btn m-btn-primary"
          style={{ width: "100%" }}
          disabled={saving}
          onClick={() => onSave({ stock_abbrs: symbols })}
        >
          {saving ? "Saving…" : "Save Watchlist"}
        </button>
      )}
    </div>
  );
}

/* ── Display settings section ──────────────────────────────────── */
function DisplaySection({ settings, onSave, saving }) {
  const {
    stock_cycles = [],
    interval_seconds = 60,
    display_brightness = 80,
    market_hours_only = false,
  } = settings;
  const [cycles, setCycles] = React.useState(stock_cycles);
  const [interval, setIntervalVal] = React.useState(String(interval_seconds));
  const [brightness, setBrightness] = React.useState(String(display_brightness));
  const [marketHours, setMarketHours] = React.useState(market_hours_only);

  React.useEffect(() => {
    setCycles(stock_cycles);
    setIntervalVal(String(interval_seconds));
    setBrightness(String(display_brightness));
    setMarketHours(market_hours_only);
  }, [settings]);

  const toggleCycle = (key, checked) =>
    setCycles((prev) => prev.map((c) => (c.key === key ? { ...c, enabled: checked } : c)));

  const save = () =>
    onSave({
      stock_cycles: cycles,
      interval_seconds: parseInt(interval, 10) || interval_seconds,
      display_brightness: parseInt(brightness, 10) ?? display_brightness,
      market_hours_only: marketHours,
    });

  return (
    <div className="m-card">
      <div className="m-card-title">Display Settings</div>

      <div style={{ marginBottom: 16 }}>
        <label className="m-form-label">Chart Cycles</label>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {cycles.map((c) => (
            <div key={c.key} className="m-toggle-row">
              <span className="m-toggle-label">{c.label}</span>
              <label className="m-switch">
                <input
                  type="checkbox"
                  checked={c.enabled}
                  onChange={(e) => toggleCycle(c.key, e.target.checked)}
                />
                <span className="m-switch-slider" />
              </label>
            </div>
          ))}
        </div>
      </div>

      <div
        className="m-toggle-row"
        style={{ flexDirection: "column", alignItems: "flex-start", gap: 6 }}
      >
        <label className="m-form-label" style={{ marginBottom: 0 }}>
          Refresh Interval (seconds)
        </label>
        <input
          className="m-input"
          type="number"
          min="10"
          max="300"
          value={interval}
          onChange={(e) => setIntervalVal(e.target.value)}
          style={{ width: 100 }}
        />
      </div>

      <div
        className="m-toggle-row"
        style={{ flexDirection: "column", alignItems: "flex-start", gap: 6, marginTop: 12 }}
      >
        <label className="m-form-label" style={{ marginBottom: 0 }}>
          Display Brightness (0–100)
        </label>
        <input
          className="m-input"
          type="number"
          min="0"
          max="100"
          value={brightness}
          onChange={(e) => setBrightness(e.target.value)}
          style={{ width: 100 }}
        />
      </div>

      <div className="m-toggle-row" style={{ marginTop: 12 }}>
        <span className="m-toggle-label">Market Hours Only</span>
        <label className="m-switch">
          <input
            type="checkbox"
            checked={marketHours}
            onChange={(e) => setMarketHours(e.target.checked)}
          />
          <span className="m-switch-slider" />
        </label>
      </div>

      <button
        className="m-btn m-btn-primary"
        style={{ width: "100%", marginTop: 16 }}
        disabled={saving}
        onClick={save}
      >
        {saving ? "Saving…" : "Save Settings"}
      </button>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function StocksSettings() {
  const { data: settings, isLoading } = useStocksSettings();
  const updateMut = useUpdateStocks();

  return (
    <div>
      <SettingsHeader title="Stocks Settings" backTo="/stocks" />
      <div className="m-section-sub" style={{ marginBottom: 16 }}>
        Watchlist and display configuration
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          <WatchlistSection
            currentSymbols={settings?.stock_abbrs ?? []}
            onSave={(patch) => updateMut.mutate(patch)}
            saving={updateMut.isPending}
          />
          <DisplaySection
            settings={settings ?? {}}
            onSave={(patch) => updateMut.mutate(patch)}
            saving={updateMut.isPending}
          />
        </>
      )}
    </div>
  );
}
