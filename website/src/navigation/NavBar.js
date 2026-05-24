import * as React from "react";
import { StatusIndicator, TopNavigation } from "@cloudscape-design/components";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useApiCheck } from "../providers/APICheckProvider";
import { getUpdateStatus } from "../services/API";

export default function NavBar() {
  const navigate = useNavigate();
  const { apiCheckState } = useApiCheck();
  const { data: updateStatus } = useQuery({
    queryKey: ["updateStatus"],
    queryFn: getUpdateStatus,
    staleTime: 3600000,
    retry: false,
  });
  const updateAvailable = updateStatus?.update_available ?? false;

  return (
    <TopNavigation
      identity={{
        href: "/",
        title: "Nuggies Display",
        onFollow: (e) => {
          e.preventDefault();
          navigate("/");
        },
      }}
      utilities={[
        {
          type: "menu-dropdown",
          text: "Pages",
          iconName: "menu",
          items: [
            { id: "mta", text: "MTA" },
            { id: "stocks", text: "Stocks" },
            { id: "weather", text: "Weather" },
            { id: "clock", text: "Clock" },
          ],
          onItemClick: ({ detail }) => {
            const routes = { mta: "/mta", stocks: "/stocks", weather: "/weather", clock: "/clock" };
            if (routes[detail.id]) navigate(routes[detail.id]);
          },
        },
        {
          type: "menu-dropdown",
          iconName: "status-info",
          ariaLabel: "API status",
          title: "API",
          items: [{ id: "api-status", text: <ApiStatus retries={apiCheckState.apiRetries} /> }],
        },
        {
          type: "button",
          iconName: "settings",
          ariaLabel: "System",
          title: "System",
          badge: updateAvailable,
          onClick: () => navigate("/system"),
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
