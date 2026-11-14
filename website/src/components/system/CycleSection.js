import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DISPLAY_MODES } from "../../constants/display";
import { useNotify } from "../../hooks/useNotify";
import {
  createCycle,
  deleteCycle,
  getCycles,
  startCycle,
  stopCycle,
  updateCycle,
} from "../../services/API";

const labelFor = (mode) => (DISPLAY_MODES.find((d) => d.key === mode) || {}).label || mode;

export default function CycleSection() {
  const qc = useQueryClient();
  const { error: notifyError } = useNotify();
  const { data } = useQuery({ queryKey: ["cycles"], queryFn: getCycles });
  const [draft, setDraft] = React.useState(null);

  const onSaved = (saved) => {
    qc.setQueryData(["cycles"], saved);
    // The schedule's cycle picker and the nav bar label both depend on this.
    qc.invalidateQueries({ queryKey: ["schedule"] });
    qc.invalidateQueries({ queryKey: ["systemStatus"] });
  };
  const options = { onSuccess: onSaved, onError: notifyError };
  const startMut = useMutation({ mutationFn: startCycle, ...options });
  const stopMut = useMutation({ mutationFn: stopCycle, ...options });
  const deleteMut = useMutation({ mutationFn: deleteCycle, ...options });
  const saveMut = useMutation({
    mutationFn: ({ id, ...body }) => (id ? updateCycle(id, body) : createCycle(body)),
    onSuccess: (saved) => {
      onSaved(saved);
      setDraft(null);
    },
    onError: notifyError,
  });

  if (!data) return null;

  const modeOptions = data.mode_options;
  const allOption = data.all_option;
  const optionsFor = (mode) => {
    const opts = modeOptions[mode] || [];
    return opts.length ? [{ key: allOption, label: "All" }, ...opts] : [];
  };
  const optionLabel = (view) =>
    (optionsFor(view.mode).find((o) => o.key === view.option) || {}).label;
  const newView = (mode) => ({
    mode,
    option: optionsFor(mode).length ? allOption : undefined,
  });

  const setView = (i, patch) =>
    setDraft({
      ...draft,
      views: draft.views.map((v, idx) => (idx === i ? { ...v, ...patch } : v)),
    });
  const moveView = (i, delta) => {
    const views = [...draft.views];
    [views[i], views[i + delta]] = [views[i + delta], views[i]];
    setDraft({ ...draft, views });
  };
  const removeView = (i) =>
    setDraft({ ...draft, views: draft.views.filter((_, idx) => idx !== i) });

  const summarize = (cycle) =>
    cycle.views.map((v) => labelFor(v.mode) + (v.option ? ` · ${optionLabel(v)}` : "")).join(" → ");

  return (
    <div className="m-card">
      <div className="m-card-title">Cycle</div>
      <div style={{ color: "#888", fontSize: "0.72rem", marginBottom: "0.6rem" }}>
        Save a named list of views and rotate through them. Picking a mode or pressing a board
        button stops the cycle.
      </div>

      {data.saved.length === 0 && !draft && (
        <div style={{ color: "#888", fontSize: "0.72rem", marginBottom: "0.6rem" }}>
          No cycles saved yet.
        </div>
      )}

      {!draft &&
        data.saved.map((cycle) => {
          const active = data.active_id === cycle.id;
          return (
            <div key={cycle.id} style={{ marginBottom: 12 }}>
              <div className="m-status-row" style={{ marginBottom: 4 }}>
                <span className={`m-badge ${active ? "m-badge-blue" : "m-badge-gray"}`}>
                  {cycle.name}
                </span>
                <span style={{ color: "#888", fontSize: "0.72rem" }}>{cycle.minutes} min each</span>
              </div>
              <div style={{ color: "#888", fontSize: "0.72rem", marginBottom: 6 }}>
                {summarize(cycle)}
              </div>
              <div className="m-btn-row">
                <button
                  className={`m-btn ${active ? "m-btn-active" : "m-btn-neutral"}`}
                  onClick={() => (active ? stopMut.mutate() : startMut.mutate(cycle.id))}
                >
                  {active ? "Stop" : "Start"}
                </button>
                <button
                  className="m-btn m-btn-neutral"
                  onClick={() => setDraft({ ...cycle, views: cycle.views.map((v) => ({ ...v })) })}
                >
                  Edit
                </button>
                <button className="m-btn m-btn-danger" onClick={() => deleteMut.mutate(cycle.id)}>
                  Delete
                </button>
              </div>
            </div>
          );
        })}

      {draft && (
        <div>
          <input
            className="m-input"
            style={{ width: "100%", marginBottom: 8 }}
            placeholder="Cycle name"
            maxLength={data.max_name_length}
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <div className="m-toggle-row">
            <span className="m-label">
              Minutes on each view ({data.minutes.min}–{data.minutes.max})
            </span>
            <input
              type="number"
              className="m-input"
              style={{ width: "5rem" }}
              min={data.minutes.min}
              max={data.minutes.max}
              value={draft.minutes}
              onChange={(e) => setDraft({ ...draft, minutes: Number(e.target.value) })}
            />
          </div>

          {draft.views.map((view, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                alignItems: "center",
                marginBottom: 10,
              }}
            >
              <select
                className="m-input"
                style={{ flex: "1 1 8rem" }}
                value={view.mode}
                onChange={(e) => setView(i, newView(e.target.value))}
              >
                {data.modes.map((m) => (
                  <option key={m} value={m}>
                    {labelFor(m)}
                  </option>
                ))}
              </select>
              {optionsFor(view.mode).length > 0 && (
                <select
                  className="m-input"
                  style={{ flex: "1 1 8rem" }}
                  value={view.option}
                  onChange={(e) => setView(i, { option: e.target.value })}
                >
                  {optionsFor(view.mode).map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label}
                    </option>
                  ))}
                </select>
              )}
              <button
                className="m-btn m-btn-neutral"
                style={{ flex: "0 0 auto" }}
                disabled={i === 0}
                onClick={() => moveView(i, -1)}
                aria-label="Move up"
              >
                ▲
              </button>
              <button
                className="m-btn m-btn-neutral"
                style={{ flex: "0 0 auto" }}
                disabled={i === draft.views.length - 1}
                onClick={() => moveView(i, 1)}
                aria-label="Move down"
              >
                ▼
              </button>
              <button
                className="m-btn m-btn-danger"
                style={{ flex: "0 0 auto" }}
                onClick={() => removeView(i)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="m-btn-row" style={{ marginTop: "0.6rem" }}>
        {draft ? (
          <>
            <button
              className="m-btn m-btn-neutral"
              onClick={() =>
                setDraft({ ...draft, views: [...draft.views, newView(data.modes[0])] })
              }
            >
              Add View
            </button>
            <button
              className="m-btn m-btn-primary"
              disabled={saveMut.isPending}
              onClick={() => saveMut.mutate(draft)}
            >
              Save
            </button>
            <button className="m-btn m-btn-neutral" onClick={() => setDraft(null)}>
              Cancel
            </button>
          </>
        ) : (
          <button
            className="m-btn m-btn-neutral"
            onClick={() =>
              setDraft({ name: "", minutes: data.minutes.min, views: [newView(data.modes[0])] })
            }
          >
            New Cycle
          </button>
        )}
      </div>
    </div>
  );
}
