import { useQuery } from "@tanstack/react-query";
import { getStocksSettings } from "../services/API";

export function useStocksSettings() {
  const { data, isFetching, isError, isLoading, refetch } = useQuery({
    queryKey: ["stocksSettings"],
    queryFn: getStocksSettings,
    staleTime: 60000,
  });
  return { data, isFetching, isError, isLoading, refetch };
}
