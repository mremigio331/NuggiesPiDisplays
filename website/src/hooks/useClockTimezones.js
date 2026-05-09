import { useQuery } from "@tanstack/react-query";
import { getClockTimezones } from "../services/API";

export function useClockTimezones(page, search = "") {
  return useQuery({
    queryKey: ["clockTimezones", page, search],
    queryFn: () => getClockTimezones(page, search),
    staleTime: Infinity,
    keepPreviousData: true,
  });
}
