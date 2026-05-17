import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useSystemStatus } from "../../hooks/useSystemStatus";
import { DISPLAY_MODES } from "../../constants/display";
import LoadingSpinner from "../../components/shared/LoadingSpinner";

export default function Home() {
  const navigate = useNavigate();
  const { data: status, isLoading } = useSystemStatus();

  React.useEffect(() => {
    if (isLoading) return;
    const mode = status?.active_display;
    const match = DISPLAY_MODES.find((m) => m.key === mode);
    if (match) navigate(`/${match.key}`, { replace: true });
  }, [isLoading, status?.active_display]);

  return <LoadingSpinner />;
}
