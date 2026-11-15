import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { getTimers } from "../services/API";

// Polls so a timer that ends shows as done without a reload. Shared by the
// Timers page and the done-timer banner in AppLayout.
export function useTimers() {
  const { data, dataUpdatedAt, isLoading, isError } = useQuery({
    queryKey: ["timers"],
    queryFn: getTimers,
    refetchInterval: 5000,
  });
  return { data, dataUpdatedAt, isLoading, isError };
}

// Device-clock "now" in epoch seconds, ticking every second. Counts down
// against the Pi's clock (the `now` it sent with the last response) rather
// than the phone's, so a phone with a wrong clock still shows the right time.
export function useDeviceNow(data, dataUpdatedAt) {
  const [tick, setTick] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const offset = data && dataUpdatedAt ? data.now - dataUpdatedAt / 1000 : 0;
  return tick / 1000 + offset;
}

// 3:59 under an hour, 1h 05m from an hour up.
export function formatLeft(seconds) {
  const s = Math.max(0, Math.ceil(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}
