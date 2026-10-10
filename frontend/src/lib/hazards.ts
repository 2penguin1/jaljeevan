import { Sun, Thermometer, Waves, type LucideIcon } from "lucide-react";
import type { Hazard } from "@/lib/api/types";

export const HAZARDS: Record<Hazard, { label: string; color: string; rgb: [number, number, number]; icon: LucideIcon }> =
  {
    drought: { label: "Drought", color: "var(--drought)", rgb: [232, 163, 61], icon: Sun },
    flood: { label: "Flood", color: "var(--flood)", rgb: [63, 182, 216], icon: Waves },
    heat: { label: "Heat", color: "var(--heat)", rgb: [240, 83, 58], icon: Thermometer },
  };

export const HAZARD_LIST: Hazard[] = ["drought", "flood", "heat"];

export const isHazard = (value: string | null | undefined): value is Hazard =>
  value === "drought" || value === "flood" || value === "heat";

export const STATUS_LABEL: Record<string, string> = {
  watch: "Watch",
  active: "Active",
  approved: "Approved",
  resolving: "Resolving",
};
