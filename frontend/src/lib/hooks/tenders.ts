import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api/client";
import type { ReliefNeed, TenderDetail, TenderSummary } from "@/lib/api/types";

export const useReliefNeed = (zoneId: string, share: number) =>
  useQuery({
    queryKey: ["relief-need", zoneId, share],
    queryFn: ({ signal }) => apiGet<ReliefNeed>(`/zones/${zoneId}/relief-need`, { share }, signal),
  });

export const useTenders = () =>
  useQuery({ queryKey: ["tenders"], queryFn: ({ signal }) => apiGet<TenderSummary[]>("/tenders", undefined, signal) });

export const useTender = (tenderId: string) =>
  useQuery({
    queryKey: ["tender", tenderId],
    queryFn: ({ signal }) => apiGet<TenderDetail>(`/tenders/${tenderId}`, undefined, signal),
    refetchInterval: 15_000, // the other side may have answered
  });

export type TenderDraft = { zone_id: string; qty_per_day: number; duration_days: number; price_per_unit: number; radius_km: number };

export const useCreateTender = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ draft, code }: { draft: TenderDraft; code: string }) => apiPost<{ id: string }>("/tenders", draft, code),
    onSuccess: () => client.invalidateQueries({ queryKey: ["tenders"] }),
  });
};

export type BidAction = { side: "gov" | "vendor"; action: "accept" | "counter" | "decline"; price_per_unit?: number; qty_per_day?: number; note?: string };

export const useBidAction = (tenderId: string) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ bidId, action, code }: { bidId: string; action: BidAction; code: string }) =>
      apiPost<TenderDetail>(`/tenders/${tenderId}/bids/${bidId}/actions`, action, code),
    onSuccess: (data) => client.setQueryData(["tender", tenderId], data),
  });
};
