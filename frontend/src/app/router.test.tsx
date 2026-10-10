import { render, screen, within } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { AppProviders } from "./providers";
import { routes } from "./router";

test("app routes render inside the shell with navigation", async () => {
  const router = createMemoryRouter(routes, { initialEntries: ["/ops"] });
  render(<AppProviders><RouterProvider router={router} /></AppProviders>);
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(nav).toBeInTheDocument();
  expect(within(nav).getByRole("link", { name: "Map" })).toHaveAttribute("href", "/map");
});
