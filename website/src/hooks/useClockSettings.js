import { useQuery } from "@tanstack/react-query";
import { getClockSettings } from "../services/API";

export function useClockSettings() {
  const { data, isFetching, isError, isLoading } = useQuery({
    queryKey: ["clockSettings"],
    queryFn: getClockSettings,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  return { data, isFetching, isError, isLoading };
}
