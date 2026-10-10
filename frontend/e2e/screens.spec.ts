import { test } from "@playwright/test";

// Screenshots for the visual review loop (not assertions). Output: e2e/screens/<page>-<width>.png
const PAGES = [
  { name: "landing", path: "/", wait: 9000 },
  { name: "map", path: "/map", wait: 12000 },
  { name: "zones", path: "/zones", wait: 1000 },
  { name: "zone", path: "/zones", wait: 1500, open: true },
  { name: "ops", path: "/ops", wait: 1000 },
];
const SIZES = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];

for (const size of SIZES) {
  for (const p of PAGES) {
    test(`screenshot ${p.name} at ${size.width}`, async ({ page }) => {
      test.skip(!process.env.SCREENS, "set SCREENS=1 to capture screenshots");
      await page.setViewportSize(size);
      await page.goto(p.path);
      if (p.open) await page.getByRole("row", { name: /Mohol, Solapur/ }).click();
      await page.waitForTimeout(p.wait);
      await page.screenshot({ path: `e2e/screens/${p.name}-${size.width}.png`, fullPage: p.name !== "map" && p.name !== "landing" });
    });
  }
}
