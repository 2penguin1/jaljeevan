import { http, HttpResponse } from "msw";
import { server } from "@/test/msw";
import { ApiError, apiGet } from "./client";

test("returns JSON and builds query strings, skipping undefined params", async () => {
  server.use(
    http.get("/api/v1/zones", ({ request }) => {
      const params = new URL(request.url).searchParams;
      return HttpResponse.json([{ id: params.get("hazard"), status: params.has("status") }]);
    }),
  );
  expect(await apiGet<{ id: string; status: boolean }[]>("/zones", { hazard: "flood", status: undefined })).toEqual([
    { id: "flood", status: false },
  ]);
});

test("throws ApiError with the server's detail", async () => {
  server.use(http.get("/api/v1/zones/x", () => HttpResponse.json({ detail: "zone x not found" }, { status: 404 })));
  await expect(apiGet("/zones/x")).rejects.toEqual(new ApiError(404, "zone x not found"));
});

test("422 validation lists become a readable detail", async () => {
  server.use(
    http.get("/api/v1/zones/abc", () =>
      HttpResponse.json({ detail: [{ msg: "Input should be a valid UUID" }] }, { status: 422 }),
    ),
  );
  await expect(apiGet("/zones/abc")).rejects.toMatchObject({ status: 422, detail: "Input should be a valid UUID" });
});

test("network failure becomes ApiError status 0", async () => {
  server.use(http.get("/api/v1/stats/overview", () => HttpResponse.error()));
  await expect(apiGet("/stats/overview")).rejects.toMatchObject({ status: 0 });
});
