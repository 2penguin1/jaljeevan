import { Droplet, Sun, Thermometer, Waves, type LucideIcon } from "lucide-react";
import type { Hazard } from "@/lib/api/types";

export const HAZARDS: Record<Hazard, { label: string; color: string; rgb: [number, number, number]; icon: LucideIcon }> =
  {
    drought: { label: "Drought", color: "var(--drought)", rgb: [232, 163, 61], icon: Sun },
    flood: { label: "Flood", color: "var(--flood)", rgb: [63, 182, 216], icon: Waves },
    heat: { label: "Heat", color: "var(--heat)", rgb: [240, 83, 58], icon: Thermometer },
    water: { label: "Water supply", color: "var(--water)", rgb: [157, 140, 242], icon: Droplet },
  };

export const HAZARD_LIST = Object.keys(HAZARDS) as Hazard[];

export const isHazard = (value: string | null | undefined): value is Hazard =>
  HAZARD_LIST.includes(value as Hazard);

export const STATUS_LABEL: Record<string, string> = {
  watch: "Watch",
  active: "Active",
  approved: "Approved",
  resolving: "Resolving",
};
