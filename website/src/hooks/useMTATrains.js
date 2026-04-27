import { useQuery } from "@tanstack/react-query";
import { getNextFourTrains } from "../services/API";

export function useMTATrains() {
  const { data, isFetching, isError, isLoading, refetch } = useQuery({
    queryKey: ["nextFourTrains"],
    queryFn: getNextFourTrains,
    refetchInterval: 30000,
    staleTime: 25000,
  });
  return { data, isFetching, isError, isLoading, refetch };
}
