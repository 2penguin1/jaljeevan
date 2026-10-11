/** The demo access code (the site is public, so every write needs it). Kept for this browser tab only. */
const KEY = "demo-access-code";

export function getDemoCode(): string {
  try {
    return sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setDemoCode(code: string): void {
  try {
    sessionStorage.setItem(KEY, code);
  } catch {
    // private mode: the code is simply asked again next time
  }
}
