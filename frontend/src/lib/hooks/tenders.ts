import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiGet, apiPost } from "@/lib/api/client";
import type { Inbox, ReliefNeed, TenderDetail, TenderSummary } from "@/lib/api/types";

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
    refetchInterval: 8_000, // the other side may have answered (same 8 s poll as the reference CRM inbox)
  });

export const useInbox = (enabled: boolean) =>
  useQuery({ queryKey: ["inbox"], queryFn: ({ signal }) => apiGet<Inbox>("/inbox", undefined, signal), enabled,
    refetchInterval: 8_000 });

export type TenderDraft = { zone_id: string; qty_per_day: number; duration_days: number; price_per_unit: number; radius_km: number };

export const useCreateTender = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (draft: TenderDraft) => apiPost<{ id: string }>("/tenders", draft),
    onSuccess: () => client.invalidateQueries({ queryKey: ["tenders"] }),
  });
};

export type BidAction =
  | { action: "accept" | "decline"; expected_version: number; note?: string }
  | { action: "counter"; expected_version: number; price_per_unit: number; qty_per_day: number; note?: string }
  | { action: "message"; body: string };

export const useBidAction = (tenderId: string) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ bidId, action }: { bidId: string; action: BidAction }) =>
      apiPost<TenderDetail>(`/tenders/${tenderId}/bids/${bidId}/actions`, action),
    onSuccess: (data) => {
      client.setQueryData(["tender", tenderId], data);
      client.invalidateQueries({ queryKey: ["inbox"] });
      client.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) client.invalidateQueries({ queryKey: ["tender", tenderId] });
    },
  });
};

export const useRaisePrice = (tenderId: string) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (price_per_unit: number) => apiPost<TenderDetail>(`/tenders/${tenderId}/raise-price`, { price_per_unit }),
    onSuccess: (data) => client.setQueryData(["tender", tenderId], data),
  });
};
