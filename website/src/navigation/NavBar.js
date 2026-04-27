import * as React from "react";
import { StatusIndicator, TopNavigation } from "@cloudscape-design/components";
import { useNavigate } from "react-router-dom";
import { useApiCheck } from "../providers/APICheckProvider";

export default function NavBar() {
  const navigate = useNavigate();
  const { apiCheckState } = useApiCheck();

  const go = (href) => (e) => {
    e.preventDefault();
    navigate(href);
  };

  return (
    <TopNavigation
      identity={{ href: "/", title: "Nuggies Display", onFollow: go("/") }}
      utilities={[
        { type: "button", text: "MTA", href: "/mta", onClick: go("/mta") },
        { type: "button", text: "Stocks", href: "/stocks", onClick: go("/stocks") },
        { type: "button", text: "System", href: "/system", onClick: go("/system") },
        {
          type: "menu-dropdown",
          iconName: "status-info",
          ariaLabel: "API status",
          title: "API",
          items: [{ id: "status", text: <ApiStatus retries={apiCheckState.apiRetries} /> }],
        },
      ]}
    />
  );
}

function ApiStatus({ retries }) {
  if (retries === 0) return <StatusIndicator>Connected</StatusIndicator>;
  if (retries < 5) return <StatusIndicator type="warning">Degraded</StatusIndicator>;
  return <StatusIndicator type="error">Unreachable</StatusIndicator>;
}
