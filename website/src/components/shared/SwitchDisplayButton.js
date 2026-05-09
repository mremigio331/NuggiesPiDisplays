import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { switchDisplay } from "../../services/API";

export default function SwitchDisplayButton({ mode }) {
  const qc = useQueryClient();
  const { data: status } = useSystemStatus({ refetchInterval: 10000 });
  const isActive = status?.active_display === mode;

  const mut = useMutation({
    mutationFn: () => switchDisplay(mode),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["systemStatus"] }),
  });

  if (isActive) return null;

  return (
    <button
      className="m-btn m-btn-primary"
      style={{ fontSize: "0.75rem", padding: "5px 12px", height: "auto", flex: "none" }}
      disabled={mut.isPending}
      onClick={() => mut.mutate()}
    >
      {mut.isPending ? "Switching…" : "▶ Set Display"}
    </button>
  );
}
