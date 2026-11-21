import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getDeviceName, setDeviceName } from "../../services/API";

// Mirror of the server rule (wifi_setup/device_name.normalize_name). The server
// re-validates; this only drives the inline hint and the Save button.
function cleanName(raw) {
  const n = (raw || "").trim().toLowerCase().replace(/\s+/g, "-");
  return /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/.test(n) ? n : "";
}

export default function DeviceNameSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["deviceName"], queryFn: getDeviceName });
  const [draft, setDraft] = React.useState("");
  const [renamedTo, setRenamedTo] = React.useState(null);

  const mut = useMutation({
    mutationFn: (name) => setDeviceName(name),
    onSuccess: (res) => {
      queryClient.setQueryData(["deviceName"], res);
      if (res.changed) setRenamedTo(res.mdns_name);
      setDraft("");
    },
  });

  const current = data?.hostname || "";
  const clean = cleanName(draft);
  const invalid = draft.trim() !== "" && !clean;
  const errorMsg = mut.error?.response?.data?.error || (mut.isError ? "Rename failed." : "");

  return (
    <div className="m-card">
      <div className="m-card-title">Device Name</div>
      <div style={{ color: "#888", fontSize: "0.72rem", marginBottom: "0.6rem" }}>
        This is the address you open in your browser:{" "}
        <strong style={{ color: "#5b9bd5" }}>{current ? `${current}.local` : "…"}</strong>
      </div>
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={current || "kitchen"}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        style={{
          width: "100%",
          padding: "0.5rem 0.6rem",
          background: "#111",
          border: "1px solid #555",
          borderRadius: "6px",
          color: "#fff",
          fontSize: "1rem",
          boxSizing: "border-box",
          marginBottom: "0.5rem",
        }}
      />
      {invalid && (
        <div style={{ color: "#d9534f", fontSize: "0.75rem", marginBottom: "0.5rem" }}>
          Use letters, numbers and dashes only (no dash at the start or end).
        </div>
      )}
      <button
        className="m-btn m-btn-primary"
        style={{ width: "100%" }}
        disabled={!clean || clean === current || mut.isPending}
        onClick={() => mut.mutate(clean)}
      >
        {mut.isPending ? "Renaming…" : clean ? `Rename to ${clean}.local` : "Rename"}
      </button>
      {errorMsg && (
        <div style={{ color: "#d9534f", fontSize: "0.75rem", marginTop: "0.5rem" }}>{errorMsg}</div>
      )}
      {renamedTo && (
        <div
          style={{
            marginTop: "0.6rem",
            padding: "0.6rem",
            borderRadius: 6,
            background: "#12301a",
            border: "1px solid #2f7a44",
            color: "#9be7a9",
            fontSize: "0.82rem",
          }}
        >
          Renamed. The old address stops working now. Open{" "}
          <a href={`http://${renamedTo}`} style={{ color: "#5b9bd5" }}>
            http://{renamedTo}
          </a>
          .
        </div>
      )}
    </div>
  );
}
