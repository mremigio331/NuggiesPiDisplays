import { useQuery } from "@tanstack/react-query";
import { getTextSettings } from "../services/API";

export function useTextSettings() {
  const { data, isFetching, isError, isLoading } = useQuery({
    queryKey: ["textSettings"],
    queryFn: getTextSettings,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  return { data, isFetching, isError, isLoading };
}
