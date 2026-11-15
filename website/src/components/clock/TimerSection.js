import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useClockSettings } from "../../hooks/useClockSettings";
import { useNotify } from "../../hooks/useNotify";
import { formatLeft, useDeviceNow, useTimers } from "../../hooks/useTimers";
import { createTimer, deleteTimer, snoozeTimer } from "../../services/API";

const hint = { color: "#888", fontSize: "0.72rem" };

// Slider snap stops (seconds): fine steps for short timers, coarse for long.
const LENGTH_STOPS = [
  60, 120, 180, 300, 600, 900, 1200, 1800, 2700,
  3600, 5400, 7200, 10800, 14400, 21600, 28800, 43200, 86400,
];
const DEFAULT_STOP = LENGTH_STOPS.indexOf(300);

// Same rule as the API: the panel fonts only have these characters (no emoji).
const boardChar = (ch) => {
  const code = ch.codePointAt(0);
  return (code >= 32 && code <= 126) || (code >= 160 && code <= 255);
};

// Label letters that fit the clock's bottom row next to a countdown like
// "59:59": 12 letters wide in focus view, 16 in multi view (matches the display).
const clockRowFit = (clock) => (clock?.display_mode === "multi" ? 16 : 12) - 6;

// 45 min, 1 hr, 1.5 hr, 24 hr
const lengthLabel = (s) =>
  s < 3600 ? `${s / 60} min` : `${Number((s / 3600).toFixed(1))} hr`;

const endsLabel = (endsAt) =>
  new Date(endsAt * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

// Timers section on the Clock page: start a timer, see running and done ones.
export default function TimerSection() {
  const qc = useQueryClient();
  const { error: notifyError } = useNotify();
  const { data, dataUpdatedAt, isLoading } = useTimers();
  const { data: clock } = useClockSettings();
  const now = useDeviceNow(data, dataUpdatedAt);

  // "in" counts down a length; "at" ends at a clock time on the board.
  const [kind, setKind] = React.useState("in");
  const [stop, setStop] = React.useState(DEFAULT_STOP);
  const [at, setAt] = React.useState("");
  const [label, setLabel] = React.useState("");

  const options = {
    onSuccess: (saved) => qc.setQueryData(["timers"], saved),
    onError: (err) => notifyError(new Error(err.response?.data?.detail || err.message)),
  };
  const addMut = useMutation({
    mutationFn: createTimer,
    ...options,
    onSuccess: (saved) => {
      options.onSuccess(saved);
      setLabel("");
    },
  });
  const deleteMut = useMutation({ mutationFn: deleteTimer, ...options });
  const snoozeMut = useMutation({ mutationFn: snoozeTimer, ...options });

  if (isLoading || !data) return null;

  const length = LENGTH_STOPS[stop];
  const full = data.timers.length >= data.max_count;
  const canAdd = !full && !addMut.isPending && (kind === "in" || !!at);

  // Warn when the board can't show the label as typed.
  const labelWarnings = [];
  const badChars = [...new Set(Array.from(label).filter((ch) => !boardChar(ch)))];
  if (badChars.length) {
    labelWarnings.push(`The board can't show ${badChars.join(" ")}. Remove it to save.`);
  }
  const shown = Array.from(label).filter(boardChar).join("").trim() || "Timer";
  const clockFit = clockRowFit(clock);
  if (clock?.show_timers !== false && shown.length > clockFit) {
    labelWarnings.push(`Too long for the clock row. Use ${clockFit} letters or fewer.`);
  }

  const add = () =>
    addMut.mutate(kind === "in" ? { label, seconds: length } : { label, at });

  return (
    <div id="timers" style={{ marginTop: 20 }}>
      <div className="m-section-title" style={{ marginBottom: 4 }}>
        Timers
      </div>
      <div className="m-section-sub">
        When a timer ends it takes over the board until a board button or Dismiss clears it.
      </div>

      <div className="m-card">
        <div className="m-card-title">New Timer</div>
        <div className="m-btn-row" style={{ marginBottom: 10 }}>
          <button
            className={`m-btn ${kind === "in" ? "m-btn-active" : "m-btn-neutral"}`}
            aria-pressed={kind === "in"}
            onClick={() => setKind("in")}
          >
            Length
          </button>
          <button
            className={`m-btn ${kind === "at" ? "m-btn-active" : "m-btn-neutral"}`}
            aria-pressed={kind === "at"}
            onClick={() => setKind("at")}
          >
            Clock time
          </button>
        </div>

        {kind === "in" ? (
          <div style={{ marginBottom: 12 }}>
            <div className="m-timer-readout">{lengthLabel(length)}</div>
            <input
              type="range"
              className="m-range"
              min={0}
              max={LENGTH_STOPS.length - 1}
              step={1}
              value={stop}
              aria-label="Timer length"
              aria-valuetext={lengthLabel(length)}
              onChange={(e) => setStop(Number(e.target.value))}
            />
            <div style={{ ...hint, display: "flex", justifyContent: "space-between" }}>
              <span>1 min</span>
              <span>1 hr</span>
              <span>24 hr</span>
            </div>
          </div>
        ) : (
          <div style={{ marginBottom: 10 }}>
            <input
              type="time"
              className="m-input m-time-input"
              value={at}
              onChange={(e) => setAt(e.target.value)}
            />
            <div style={{ ...hint, marginTop: 4 }}>
              The next time the board's clock reads this. A time already past today means tomorrow.
            </div>
          </div>
        )}

        <input
          className="m-input"
          placeholder="Label (shown on the board)"
          maxLength={data.max_label}
          value={label}
          aria-invalid={labelWarnings.length > 0}
          style={{
            width: "100%",
            marginBottom: 4,
            ...(labelWarnings.length ? { border: "1px solid #e05050" } : {}),
          }}
          onChange={(e) => setLabel(e.target.value)}
        />
        <div style={{ ...hint, display: "flex", gap: 8, marginBottom: 10 }}>
          <div style={{ flex: 1, color: "#e05050" }}>
            {labelWarnings.map((w) => (
              <div key={w}>{w}</div>
            ))}
          </div>
          <span style={label.length >= data.max_label ? { color: "#e05050" } : undefined}>
            {label.length}/{data.max_label}
          </span>
        </div>
        <button
          className="m-btn m-btn-primary"
          disabled={!canAdd || labelWarnings.length > 0}
          onClick={add}
        >
          Start Timer
        </button>
        {full && (
          <div style={{ ...hint, marginTop: 6 }}>
            You can have up to {data.max_count} timers. Remove one to add another.
          </div>
        )}
      </div>

      <div className="m-card">
        <div className="m-card-title">Your Timers</div>
        {data.timers.length === 0 && <div style={hint}>No timers yet.</div>}
        {data.timers.map((t) => {
          const done = t.done || t.ends_at <= now;
          return (
            <div key={t.id} style={{ marginBottom: 12 }}>
              <div className="m-status-row" style={{ marginBottom: 4 }}>
                <span className={`m-badge ${done ? "m-badge-red" : "m-badge-blue"}`}>
                  {done ? "Done" : formatLeft(t.ends_at - now)}
                </span>
                <span style={{ fontWeight: 600 }}>{t.label}</span>
              </div>
              <div style={{ ...hint, marginBottom: 6 }}>
                {done
                  ? `Ended ${endsLabel(t.ends_at)} · ${formatLeft(now - t.ends_at)} ago`
                  : `Ends ${endsLabel(t.ends_at)}`}
              </div>
              <div className="m-btn-row">
                {done && (
                  <button
                    className="m-btn m-btn-neutral"
                    onClick={() => snoozeMut.mutate(t.id)}
                  >
                    +{Math.round(data.snooze_seconds / 60)} min
                  </button>
                )}
                <button className="m-btn m-btn-danger" onClick={() => deleteMut.mutate(t.id)}>
                  {done ? "Dismiss" : "Cancel"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
