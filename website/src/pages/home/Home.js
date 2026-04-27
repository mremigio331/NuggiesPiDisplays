import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Spinner } from "@cloudscape-design/components";
import { useSystemStatus } from "../../hooks/useSystemStatus";

export default function Home() {
  const navigate = useNavigate();
  const { data: status, isLoading } = useSystemStatus();

  React.useEffect(() => {
    if (isLoading) return;
    const mode = status?.active_display;
    if (mode === "mta") navigate("/mta", { replace: true });
    else if (mode === "stocks") navigate("/stocks", { replace: true });
  }, [isLoading, status?.active_display]);

  return (
    <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
      <Spinner size="large" />
    </div>
  );
}
