import { useQuery } from "@tanstack/react-query";
import { getEnabledStations } from "../services/API";

export function useEnabledStations() {
  return useQuery({
    queryKey: ["enabledStations"],
    queryFn: getEnabledStations,
    staleTime: 30000,
  });
}
