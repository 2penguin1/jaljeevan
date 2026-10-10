import { NavLink, Outlet } from "react-router";

const NAV = [
  { to: "/map", label: "Map" },
  { to: "/zones", label: "Zones" },
  { to: "/ops", label: "Ops" },
];

export function AppShell() {
  return (
    <div className="flex min-h-dvh">
      <nav aria-label="Main" className="flex w-16 flex-col items-center gap-2 border-r hairline py-4">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
