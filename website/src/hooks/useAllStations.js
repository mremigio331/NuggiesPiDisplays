import { useQuery } from "@tanstack/react-query";
import { getAllStations } from "../services/API";

export function useAllStations() {
  const { data, isFetching, isError, isLoading, refetch } = useQuery({
    queryKey: ["allStations"],
    queryFn: getAllStations,
    staleTime: 5 * 60 * 1000,
  });
  return { data, isFetching, isError, isLoading, refetch };
}
