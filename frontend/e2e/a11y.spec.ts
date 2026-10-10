import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = [
  { path: "/", ready: "heading" },
  { path: "/map", ready: "[data-zone-count]" },
  { path: "/zones", ready: "table" },
  { path: "/zones/00000000-0000-0000-0000-000000000000", ready: "text=Zone not found" },
  { path: "/ops", ready: "table" },
];

for (const { path, ready } of PAGES) {
  test(`no serious accessibility problems on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.locator(ready === "heading" ? "h1" : ready).first().waitFor();
    await page.waitForTimeout(500);
    const results = await new AxeBuilder({ page })
      .exclude("canvas") // WebGL surfaces are covered by text alternatives (/zones, the feed)
      .exclude(".maplibregl-ctrl-attrib")
      .analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
  });
}
