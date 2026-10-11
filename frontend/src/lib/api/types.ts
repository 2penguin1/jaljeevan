import type { components } from "./schema";

type S = components["schemas"];

export type Hazard = S["ZoneSummary"]["hazard"]; // generated from the backend: one source of truth
export type ZoneStatus = "watch" | "active" | "approved" | "resolving";

export type FeedItem = S["FeedItem"];
export type FeedPage = S["FeedPage"];
export type ZoneSummary = S["ZoneSummary"];
export type ZoneDetail = S["ZoneDetail"];
export type EvidenceItem = S["EvidenceItem"];
export type ScoreBreakdown = S["ScoreBreakdown"];
export type TrendPoint = S["TrendPoint"];
export type StatsOverview = S["StatsOverview"];
export type OpsSummary = S["OpsSummary"];
export type OpsRun = S["OpsRun"];
export type DeclarationWatchInfo = S["DeclarationWatchInfo"];
export type DroughtPanel = S["DroughtPanel"];
export type IndicatorFreshness = S["IndicatorFreshness"];

// Map endpoints return GeoJSON passthrough (typed here, not in OpenAPI).
export type Geometry = { type: string; coordinates: unknown };
export type Feature<P> = { type: "Feature"; id: string | number; geometry: Geometry | null; properties: P };
export type FeatureCollection<P> = { type: "FeatureCollection"; features: Feature<P>[] };

export type ZoneProps = {
  name: string;
  hazard: Hazard;
  zone_type: string;
  status: ZoneStatus;
  score: number;
  trend: string;
  population_est: number | null;
  independent_sources: number;
  centroid: [number, number] | null;
};
export type DistrictProps = {
  id: number;
  name: string;
  state_code: string;
  indicator_value: number | null;
  indicator_label: string;
  band: "none" | "moderate" | "severe";
};
export type SignalProps = {
  id: string;
  severity: number | null;
  source: string;
  title: string;
  published_at: string;
  zone_id: string | null;
};
export type FootprintProps = {
  id: number;
  name: string;
  district: string | null;
  level: "watch" | "moderate" | "severe";
  spi_18p: number | null;
  people: number | null;
  declared: boolean;
};
export type ReliefNeed = S["ReliefNeedOut"];
export type TenderSummary = S["TenderSummary"];
export type TenderDetail = S["TenderDetail"];
export type BidOut = S["BidOut"];
export type VendorOut = S["VendorOut"];
export type Me = S["MeOut"];
export type Inbox = S["InboxOut"];
export type InboxBid = S["InboxBid"];
