import { useQuery } from "@tanstack/react-query";
import { getStockInfo } from "../services/API";

export function useStockInfo(symbol) {
  return useQuery({
    queryKey: ["stockInfo", symbol],
    queryFn: () => getStockInfo(symbol),
    staleTime: Infinity,
    enabled: Boolean(symbol),
  });
}
