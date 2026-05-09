import { useQuery } from "@tanstack/react-query";
import { getStockChart } from "../services/API";

export function useStockChart(symbol, cycleKey) {
  return useQuery({
    queryKey: ["stockChart", symbol, cycleKey],
    queryFn: () => getStockChart(symbol, cycleKey),
    staleTime: 60000,
    enabled: Boolean(symbol && cycleKey),
  });
}
