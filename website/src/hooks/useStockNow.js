import { useQuery } from "@tanstack/react-query";
import { getStockNow } from "../services/API";

export function useStockNow() {
  return useQuery({
    queryKey: ["stockNow"],
    queryFn: getStockNow,
    refetchInterval: 5000,
    staleTime: 0,
  });
}
