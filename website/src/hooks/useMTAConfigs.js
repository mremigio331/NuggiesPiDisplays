import { useQuery } from "@tanstack/react-query";
import { getMTAConfigs } from "../services/API";

export function useMTAConfigs() {
  const { data, isFetching, isError, isLoading, refetch } = useQuery({
    queryKey: ["mtaConfigs"],
    queryFn: getMTAConfigs,
    staleTime: 60000,
  });
  return { data, isFetching, isError, isLoading, refetch };
}
