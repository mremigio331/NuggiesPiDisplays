import * as React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@cloudscape-design/global-styles/index.css";
import { NotificationsProvider } from "./services/Notifications";
import { APICheckProvider } from "./providers/APICheckProvider";
import NuggiesDisplay from "./NuggiesDisplay";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 3, retryDelay: (i) => Math.min(1000 * 2 ** i, 15000) } },
});

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <QueryClientProvider client={queryClient}>
      <NotificationsProvider>
        <APICheckProvider>
          <NuggiesDisplay />
        </APICheckProvider>
      </NotificationsProvider>
    </QueryClientProvider>
  </BrowserRouter>
);
