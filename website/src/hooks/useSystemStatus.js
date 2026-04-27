import { useQuery } from "@tanstack/react-query";
import { getSystemStatus } from "../services/API";

export function useSystemStatus({ refetchInterval = 5000 } = {}) {
  const { data, isFetching, isError, isLoading, refetch } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: getSystemStatus,
    refetchInterval,
    staleTime: 4000,
  });
  return { data, isFetching, isError, isLoading, refetch };
}
