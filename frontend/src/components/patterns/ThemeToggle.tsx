import { Monitor, Moon, Sun } from "lucide-react";
import { useState } from "react";

type Theme = "system" | "light" | "dark";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<Theme, string> = { system: "Theme: follows your device", light: "Theme: light", dark: "Theme: dark" };

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

/** Cycles device → light → dark. The choice is saved in this browser and applied before paint (index.html). */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(readTheme);
  const choose = () => {
    const next = NEXT[theme];
    setTheme(next);
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
    try {
      if (next === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", next);
    } catch {
      // private mode: the choice lasts for this visit only
    }
  };
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <button type="button" onClick={choose} aria-label={`${LABEL[theme]}. Click to change`} title={LABEL[theme]}
      className={`grid h-8 w-8 place-items-center rounded-[6px] text-text-2 hover:bg-raised hover:text-text ${className}`}>
      <Icon size={16} strokeWidth={1.75} aria-hidden />
    </button>
  );
}
