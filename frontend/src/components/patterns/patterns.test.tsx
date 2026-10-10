import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api/client";
import { formatPeople } from "@/lib/format";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { EvidenceQuote } from "./EvidenceQuote";
import { HazardBadge } from "./HazardBadge";
import { ScoreMeter } from "./ScoreMeter";

test("HazardBadge names the hazard in text, not colour alone", () => {
  render(<HazardBadge hazard="flood" status="watch" />);
  expect(screen.getByText("Flood")).toBeInTheDocument();
  expect(screen.getByText("watch", { exact: false })).toBeInTheDocument();
});

test("ScoreMeter exposes its value to assistive tech", () => {
  render(<ScoreMeter score={72.6} hazard="drought" />);
  const meter = screen.getByRole("meter");
  expect(meter).toHaveAttribute("aria-valuenow", "72.6");
  expect(meter).toHaveAttribute("aria-valuemax", "100");
  expect(screen.getByText("73")).toBeInTheDocument();
});

test("EvidenceQuote renders untrusted HTML as literal text", () => {
  const nasty = "<script>alert(1)</script><img src=x onerror=alert(2)>";
  const { container } = render(
    <EvidenceQuote quote={nasty} title={nasty} domain="x.com" source="x" credibility={0.4}
      url="javascript:alert(3)" publishedAt="2026-10-10T10:00:00Z" />,
  );
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getAllByText(nasty, { exact: false }).length).toBeGreaterThan(0);
  expect(container.querySelector('a[href^="javascript"]')).toBeNull(); // unsafe links are dropped
});

test("EmptyState and ErrorState give direction", async () => {
  const retry = vi.fn();
  render(
    <>
      <EmptyState title="No active heat zones right now" body="Heat zones appear when posts and temperatures agree." />
      <ErrorState error={new ApiError(0, "Can't reach the server. Check your connection.")} onRetry={retry} />
    </>,
  );
  expect(screen.getByText("No active heat zones right now")).toBeInTheDocument();
  expect(screen.getByText("Can't reach the server. Check your connection.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalled();
});

test("DataTable sorts by a column when its header is clicked", async () => {
  const rows = [
    { id: "a", name: "Alpha", score: 10 },
    { id: "b", name: "Beta", score: 90 },
  ];
  render(
    <DataTable caption="Zones" rows={rows} rowKey={(r) => r.id}
      columns={[
        { key: "name", header: "Name", cell: (r) => r.name, sortValue: (r) => r.name },
        { key: "score", header: "Score", cell: (r) => r.score, sortValue: (r) => r.score, numeric: true },
      ]} />,
  );
  const firstCell = () => within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0].textContent;
  expect(firstCell()).toBe("Alpha");
  await userEvent.click(screen.getByRole("button", { name: /Score/ }));
  expect(firstCell()).toBe("Beta"); // numbers sort high to low first
  expect(screen.getByRole("columnheader", { name: /Score/ })).toHaveAttribute("aria-sort", "descending");
});

test("people counts read the Indian way", () => {
  expect(formatPeople(3980116)).toBe("39.8 lakh");
  expect(formatPeople(25331130)).toBe("2.5 crore");
  expect(formatPeople(12000)).toBe("12,000");
  expect(formatPeople(null)).toBe("—");
});

test("map legend describes watch zones without claiming a source count", async () => {
  const { Legend } = await import("@/features/map/Legend");
  render(<Legend hazard="drought" />);
  expect(screen.getByText("Watch: not confirmed yet")).toBeInTheDocument();
  expect(screen.queryByText(/one source/)).toBeNull();
});
