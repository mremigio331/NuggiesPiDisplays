import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTextSettings } from "../../hooks/useTextSettings";
import { useNotify } from "../../hooks/useNotify";
import { updateTextSettings } from "../../services/API";
import SettingsHeader from "../../components/shared/SettingsHeader";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import LedPreview, { TEXT_LAYOUTS } from "../../components/text/LedPreview";

const MAX_LENGTH = 100;
const LED_W = 64;
const ROW_COUNTS = [1, 2, 3, 4, 5];
const SCROLL_SECONDS = [1, 2, 3, 4, 5];

// Anything outside these is missing from the board's fonts (emoji, for one).
const UNSUPPORTED_CHARS = /[^\x20-\x7E\xA0-\xFF]/g;

const COLOR_PRESETS = [
  { label: "Blue", value: "0,0,255" },
  { label: "Cyan", value: "0,255,255" },
  { label: "Green", value: "0,255,0" },
  { label: "Magenta", value: "255,0,255" },
  { label: "Orange", value: "255,165,0" },
  { label: "Red", value: "255,0,0" },
  { label: "White", value: "255,255,255" },
  { label: "Yellow", value: "255,255,0" },
];

const COLOR_OPTIONS = [
  ...COLOR_PRESETS.map((p) => ({ label: p.label, value: p.value, sortKey: p.label })),
  { label: "🌈 Caitlin Mode", value: "rainbow", sortKey: "Caitlin Mode" },
].sort((a, b) => a.sortKey.localeCompare(b.sortKey));

function colorValue(row) {
  return row.color_mode === "rainbow" ? "rainbow" : row.color.join(",");
}

function RowEditor({ index, row, charWidth, onChange }) {
  const overflows = row.text.length * charWidth > LED_W;

  const handleColor = (value) => {
    if (value === "rainbow") onChange({ color_mode: "rainbow" });
    else onChange({ color_mode: "solid", color: value.split(",").map(Number) });
  };

  return (
    <div className="m-card">
      <div className="m-card-title">Row {index + 1}</div>
      <input
        className="m-input"
        style={{ width: "100%" }}
        value={row.text}
        maxLength={MAX_LENGTH}
        placeholder="Leave empty for a blank row"
        onChange={(e) => onChange({ text: e.target.value.replace(UNSUPPORTED_CHARS, "") })}
      />
      <div style={{ color: "#5a7a9a", fontSize: "0.75rem", marginTop: 4 }}>
        {row.text.length}/{MAX_LENGTH}
        {overflows && (row.scroll ? " · This row will scroll" : " · This row will be cut off")}
      </div>

      <div className="m-toggle-row">
        <span className="m-label">Scroll if too long</span>
        <label className="m-switch">
          <input
            type="checkbox"
            checked={row.scroll}
            onChange={(e) => onChange({ scroll: e.target.checked })}
          />
          <span className="m-switch-slider" />
        </label>
      </div>

      <div className="m-toggle-row">
        <span className="m-label">Color</span>
        <select
          className="m-select"
          style={{ width: "auto" }}
          value={colorValue(row)}
          onChange={(e) => handleColor(e.target.value)}
        >
          {COLOR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="m-toggle-row">
        <span className="m-label">Align</span>
        <div className="m-btn-row">
          {["left", "center", "right"].map((align) => (
            <button
              key={align}
              className={`m-btn ${row.align === align ? "m-btn-active" : "m-btn-neutral"}`}
              onClick={() => onChange({ align })}
            >
              {align[0].toUpperCase() + align.slice(1)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function TextSettings() {
  const qc = useQueryClient();
  const { error: notifyError } = useNotify();
  const { data: settings, isLoading } = useTextSettings();

  const [rowCount, setRowCount] = React.useState(1);
  const [rows, setRows] = React.useState([]);
  const [scrollSeconds, setScrollSeconds] = React.useState(2);
  const [dirty, setDirty] = React.useState(false);
  const [saved, setSaved] = React.useState(false);

  // Load the saved text, without overwriting anything being typed.
  React.useEffect(() => {
    if (settings && !dirty) {
      setRowCount(settings.row_count);
      setRows(settings.rows);
      setScrollSeconds(settings.scroll_seconds);
    }
  }, [settings, dirty]);

  const saveMut = useMutation({
    mutationFn: updateTextSettings,
    onSuccess: (data) => {
      qc.setQueryData(["textSettings"], data);
      setDirty(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
    onError: notifyError,
  });

  const handleRowCount = (count) => {
    setRowCount(count);
    setDirty(true);
    setSaved(false);
  };

  const handleScrollSeconds = (value) => {
    setScrollSeconds(value);
    setDirty(true);
    setSaved(false);
  };

  const updateRow = (index, changes) => {
    setRows((current) => current.map((r, i) => (i === index ? { ...r, ...changes } : r)));
    setDirty(true);
    setSaved(false);
  };

  if (isLoading || rows.length === 0) return <LoadingSpinner />;

  const layout = TEXT_LAYOUTS[rowCount];

  return (
    <div>
      <SettingsHeader title="Text Settings" backTo="/text" />
      <div className="m-section-sub" style={{ marginBottom: 16 }}>
        The board changes when you save
      </div>

      <div className="m-card" style={{ textAlign: "center" }}>
        <div className="m-card-title">Preview</div>
        <LedPreview rowCount={rowCount} rows={rows} scrollSeconds={scrollSeconds} />
      </div>

      <div className="m-card">
        <div className="m-card-title">Rows</div>
        <div className="m-btn-row">
          {ROW_COUNTS.map((count) => (
            <button
              key={count}
              className={`m-btn ${rowCount === count ? "m-btn-active" : "m-btn-neutral"}`}
              onClick={() => handleRowCount(count)}
            >
              {count}
            </button>
          ))}
        </div>
        <div style={{ color: "#5a7a9a", fontSize: "0.8rem", marginTop: 8 }}>
          Fewer rows use bigger letters.
        </div>
      </div>

      <div className="m-card">
        <div className="m-toggle-row">
          <span className="m-label">Scroll speed</span>
          <select
            className="m-select"
            style={{ width: "auto" }}
            value={scrollSeconds}
            onChange={(e) => handleScrollSeconds(Number(e.target.value))}
          >
            {SCROLL_SECONDS.map((s) => (
              <option key={s} value={s}>
                {s}s per letter
              </option>
            ))}
          </select>
        </div>
      </div>

      {rows.slice(0, rowCount).map((row, i) => (
        <RowEditor
          key={i}
          index={i}
          row={row}
          charWidth={layout.charWidth}
          onChange={(changes) => updateRow(i, changes)}
        />
      ))}

      <button
        className="m-btn m-btn-primary"
        style={{ width: "100%", marginTop: 8 }}
        disabled={!dirty || saveMut.isPending}
        onClick={() => saveMut.mutate({ row_count: rowCount, scroll_seconds: scrollSeconds, rows })}
      >
        {saveMut.isPending ? "Saving…" : saved ? "Saved ✓" : "Save to Board"}
      </button>
    </div>
  );
}
