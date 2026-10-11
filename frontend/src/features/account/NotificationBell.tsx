import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { apiGet, apiPost } from "@/lib/api/client";
import type { Notifications } from "@/lib/api/types";
import { timeAgo } from "@/lib/format";

/** The logged-in user's own notifications: new tenders for vendors, replies for both sides. Checked every 15 s. */
export function NotificationBell() {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const notes = useQuery({
    queryKey: ["notifications"],
    queryFn: ({ signal }) => apiGet<Notifications>("/notifications", undefined, signal),
    refetchInterval: 15_000,
  });
  const markAll = useMutation({
    mutationFn: () => apiPost<void>("/notifications/read", {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !panel.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const unread = notes.data?.unread ?? 0;
  return (
    <div ref={panel} className="relative">
      <button type="button" aria-expanded={open} aria-label={`Notifications, ${unread} unread`} onClick={() => setOpen(!open)}
        className="relative grid h-8 w-8 place-items-center rounded-[6px] text-text-2 hover:bg-raised hover:text-text">
        <Bell size={16} strokeWidth={1.75} aria-hidden />
        {unread > 0 && (
          <span aria-hidden className="num absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-drought px-1 text-[10px] leading-4 text-canvas">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-40 flex w-80 flex-col rounded-[8px] border hairline bg-surface shadow-lg">
          <div className="flex items-center justify-between border-b hairline px-3 py-2">
            <span className="text-[13px] font-medium text-text">Notifications</span>
            <button type="button" className="text-[12px] text-text-2 hover:text-text disabled:opacity-50"
              disabled={unread === 0 || markAll.isPending} onClick={() => markAll.mutate()}>Mark all read</button>
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {(notes.data?.items ?? []).length === 0 && <li className="px-3 py-4 text-[13px] text-text-3">Nothing yet.</li>}
            {(notes.data?.items ?? []).map((n) => (
              <li key={n.id} className="border-b hairline last:border-0">
                <Link to={n.link ?? "/tenders"} onClick={() => setOpen(false)}
                  className={`block px-3 py-2.5 text-[13px] hover:bg-raised ${n.read ? "text-text-3" : "text-text"}`}>
                  {n.text}
                  <span className="mt-0.5 block text-[11px] text-text-3">{timeAgo(n.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
