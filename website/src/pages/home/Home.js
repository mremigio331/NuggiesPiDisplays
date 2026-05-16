import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useSystemStatus } from "../../hooks/useSystemStatus";

export default function Home() {
  const navigate = useNavigate();
  const { data: status, isLoading } = useSystemStatus();

  React.useEffect(() => {
    if (isLoading) return;
    const mode = status?.active_display;
    if (mode === "mta") navigate("/mta", { replace: true });
    else if (mode === "stocks") navigate("/stocks", { replace: true });
    else if (mode === "clock") navigate("/clock", { replace: true });
    else if (mode === "weather") navigate("/weather", { replace: true });
  }, [isLoading, status?.active_display]);

  return (
    <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
      <div className="m-spinner m-spinner-lg" />
    </div>
  );
}
