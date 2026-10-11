import { Activity, ClipboardCheck, Globe2, Inbox, Rows3, Truck, type LucideIcon } from "lucide-react";
import { Link, NavLink, Outlet, useMatches, useNavigate } from "react-router";
import { LiveDot } from "@/components/patterns/LiveDot";
import { NotificationBell } from "@/features/account/NotificationBell";
import { APP_NAME } from "@/lib/config";
import { cn } from "@/lib/format";
import { ROLE_NAME, useLogout, useMe } from "@/lib/hooks/session";
import { LiveProvider, useLiveStatus } from "@/lib/live/LiveContext";

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/map", label: "Map", icon: Globe2 },
  { to: "/zones", label: "Zones", icon: Rows3 },
  { to: "/tenders", label: "Tenders", icon: Truck },
  { to: "/ops", label: "Ops", icon: Activity },
];

const INBOX = { to: "/inbox", label: "Inbox", icon: Inbox };
const BRIEFS = { to: "/briefs", label: "Briefs", icon: ClipboardCheck };

function NavItems({ compact }: { compact?: boolean }) {
  const me = useMe();
  const extra = me.data?.role === "vendor" ? [INBOX] : me.data?.role === "gov_admin" ? [BRIEFS] : [];
  const items = [...NAV.slice(0, 3), ...extra, ...NAV.slice(3)];
  return items.map(({ to, label, icon: Icon }) => (
    <NavLink
      key={to}
      to={to}
      className={({ isActive }) =>
        cn(
          "flex flex-col items-center justify-center gap-1 rounded-[6px] text-[11px] transition-colors duration-[var(--dur-1)]",
          compact ? "h-full flex-1" : "h-12 w-12",
          isActive ? "bg-raised text-text" : "text-text-3 hover:text-text",
        )
      }
    >
      <Icon size={18} strokeWidth={1.75} aria-hidden />
      {label}
    </NavLink>
  ));
}

function TopBar() {
  const title = useMatches().findLast((m) => (m.handle as { title?: string } | undefined)?.title)?.handle as
    | { title: string }
    | undefined;
  const status = useLiveStatus();
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b hairline px-4 md:px-6">
      <span className="text-[14px] font-medium text-text">{title?.title ?? APP_NAME}</span>
      <div className="flex items-center gap-4">
        <Account />
        <LiveDot status={status} />
      </div>
    </header>
  );
}

function Account() {
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  if (me.isPending) return null;
  if (!me.data) return <Link to="/login" className="text-[13px] text-text-2 hover:text-text">Log in</Link>;
  return (
    <div className="flex items-center gap-3 text-[13px]">
      <NotificationBell />
      <span className="hidden text-text-2 sm:inline">
        {me.data.name} <span className="text-text-3">· {ROLE_NAME[me.data.role] ?? me.data.role}</span>
      </span>
      <button type="button" className="text-text-2 hover:text-text"
        onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/map") })}>
        Log out
      </button>
    </div>
  );
}

export function AppShell() {
  return (
    <LiveProvider>
      <div className="flex h-dvh overflow-hidden bg-canvas">
        <nav aria-label="Main" className="hidden w-16 shrink-0 flex-col items-center gap-1 border-r hairline py-3 md:flex">
          <Link to="/" className="mb-3 grid h-10 w-10 place-items-center font-display text-[22px] text-text" title={APP_NAME}>
            <span aria-hidden>{APP_NAME.charAt(0)}</span>
            <span className="sr-only">{APP_NAME} home</span>
          </Link>
          <NavItems />
        </nav>
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="relative min-h-0 flex-1 overflow-y-auto pb-14 md:pb-0">
            <Outlet />
          </main>
        </div>
        <nav aria-label="Main mobile" className="fixed inset-x-0 bottom-0 z-30 flex h-14 border-t hairline bg-surface px-2 md:hidden">
          <NavItems compact />
        </nav>
      </div>
    </LiveProvider>
  );
}
