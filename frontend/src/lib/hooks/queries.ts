import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api/client";
import type {
  DistrictProps,
  FeatureCollection,
  FeedPage,
  Hazard,
  OpsSummary,
  SignalProps,
  StatsOverview,
  ZoneDetail,
  ZoneProps,
  ZoneStatus,
  ZoneSummary,
} from "@/lib/api/types";

// Query keys are shared with useLiveEvents, which invalidates them when the server pushes news.
export const useMapZones = (hazard: Hazard) =>
  useQuery({
    queryKey: ["map", "zones", hazard],
    queryFn: ({ signal }) => apiGet<FeatureCollection<ZoneProps>>("/map/zones", { hazard }, signal),
    placeholderData: keepPreviousData,
  });

export const useMapDistricts = (hazard: Hazard) =>
  useQuery({
    queryKey: ["map", "districts", hazard],
    queryFn: ({ signal }) => apiGet<FeatureCollection<DistrictProps>>("/map/districts", { hazard }, signal),
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  });

export const useMapSignals = (hazard: Hazard, hours = 48) =>
  useQuery({
    queryKey: ["map", "signals", hazard, hours],
    queryFn: ({ signal }) => apiGet<FeatureCollection<SignalProps>>("/map/signals", { hazard, hours }, signal),
    placeholderData: keepPreviousData,
  });

export const useFeed = () =>
  useInfiniteQuery({
    queryKey: ["feed"],
    queryFn: ({ pageParam, signal }) => apiGet<FeedPage>("/feed", { cursor: pageParam, limit: 30 }, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

export const useZones = (filters: { hazard?: Hazard; status?: ZoneStatus }) =>
  useQuery({
    queryKey: ["zones", filters],
    queryFn: ({ signal }) => apiGet<ZoneSummary[]>("/zones", filters, signal),
  });

export const useZone = (id: string | undefined) =>
  useQuery({
    queryKey: ["zones", "detail", id],
    queryFn: ({ signal }) => apiGet<ZoneDetail>(`/zones/${encodeURIComponent(id!)}`, undefined, signal),
    enabled: Boolean(id),
    retry: (count, err) => (err as { status?: number }).status === 0 && count < 2, // never retry a 404/422
  });

export const useStats = () =>
  useQuery({ queryKey: ["stats"], queryFn: ({ signal }) => apiGet<StatsOverview>("/stats/overview", undefined, signal) });

export const useOps = () =>
  useQuery({
    queryKey: ["ops"],
    queryFn: ({ signal }) => apiGet<OpsSummary>("/ops/summary", undefined, signal),
    refetchInterval: 60_000,
  });
