import { expect, test } from "@playwright/test";

test("landing: one headline, live numbers, and the way into the map", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("See every water crisis in India, as it happens.");
  await expect(page.getByText("posts read and checked in the last seven days")).toBeVisible();
  await expect(page.getByRole("term")).toHaveCount(3);
  await page.getByRole("link", { name: "Open the live map" }).click();
  await expect(page).toHaveURL(/\/map$/);
});

test("map: zones load, the hazard switch changes the layer, a zone can be opened from the feed", async ({ page }) => {
  await page.goto("/map");
  await expect(page.locator("[data-zone-count]")).toHaveAttribute("data-zone-count", "1");
  await expect(page.getByText("1 active and 0 on watch")).toBeVisible();
  await page.getByRole("button", { name: "Flood" }).click();
  await expect(page).toHaveURL(/hazard=flood/);
  await expect(page.locator("[data-zone-count]")).toHaveAttribute("data-zone-count", "1");
  await page.getByRole("button", { name: "Heat" }).click();
  await expect(page.getByText("0 active and 1 on watch")).toBeVisible();
  await page.getByRole("button", { name: "Water supply" }).click();
  await expect(page).toHaveURL(/hazard=water/);
  await expect(page.getByText("1 active and 0 on watch")).toBeVisible();
  const feed = page.getByRole("complementary", { name: "Live feed" });
  await expect(feed.getByText("Water entered houses in Danapur, families moving to roofs")).toBeVisible();
  await feed.getByText("No tanker has come for nine days in Mohol").click();
  await expect(page.getByRole("heading", { level: 1, name: "Mohol, Solapur" })).toBeVisible();
});

test("zones list → zone page shows the evidence and the arithmetic", async ({ page }) => {
  await page.goto("/zones");
  await expect(page.getByRole("row")).toHaveCount(5); // header + one zone per hazard
  await page.getByRole("button", { name: "Drought" }).click();
  await expect(page).toHaveURL(/hazard=drought/);
  await page.getByRole("row", { name: /Mohol, Solapur/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Mohol, Solapur" })).toBeVisible();
  await expect(page.getByText("“Our taps are dry since last week”")).toBeVisible();
  await expect(page.getByText("<b>Our taps are dry</b> in Mohol", { exact: false })).toHaveCount(0); // title not shown as HTML
  await expect(page.getByRole("region", { name: "How the score adds up" })).toContainText("Confirmed by 3 independent sources.");
});

test("a zone that does not exist says so and links back", async ({ page }) => {
  await page.goto("/zones/00000000-0000-0000-0000-000000000000");
  await expect(page.getByText("Zone not found")).toBeVisible();
  await page.goto("/zones/not-a-zone");
  await expect(page.getByText("Zone not found")).toBeVisible();
  await page.getByRole("link", { name: "Back to all zones" }).click();
  await expect(page).toHaveURL(/\/zones$/);
});

test("ops shows pipeline health", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.getByText("Posts collected")).toBeVisible();
  await expect(page.getByRole("region", { name: "Why posts were set aside" })).toContainText("No water or heat words");
  await expect(page.getByText("1 source failed")).toBeVisible();
});

test("live: the status dot goes live", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.getByRole("status").filter({ hasText: "Live" })).toBeVisible();
});
