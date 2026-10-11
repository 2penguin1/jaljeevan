import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError } from "@/lib/api/client";
import { useMe } from "@/lib/hooks/session";
import { useCreateTender, useReliefNeed } from "@/lib/hooks/tenders";
import { BUTTON, Field, INPUT, PRIMARY } from "./ui";

const SHARES = [0.05, 0.1, 0.2, 0.3];

/** How much drinking water this zone needs from tankers (computed on the server, formula shown), and a prefilled
 *  tender to ask nearby vendors for it. */
export function ReliefNeedCard({ zoneId }: { zoneId: string }) {
  const [share, setShare] = useState(0.1);
  const [open, setOpen] = useState(false);
  const need = useReliefNeed(zoneId, share);
  const create = useCreateTender();
  const me = useMe();
  const officer = me.data?.role === "gov_admin";
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const [radius, setRadius] = useState(100);
  const [qty, setQty] = useState<number | null>(null);
  const [price, setPrice] = useState<number | null>(null);

  if (!need.data) return null;
  const n = need.data;
  const publish = async (e: React.FormEvent) => {
    e.preventDefault();
    const draft = { zone_id: zoneId, qty_per_day: qty ?? n.kl_per_day, duration_days: days,
      price_per_unit: price ?? n.suggested_price, radius_km: radius };
    try {
      const { id } = await create.mutateAsync(draft);
      navigate(`/tenders/${id}`);
    } catch {
      // shown below from create.error
    }
  };

  return (
    <section aria-label="Relief need" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[13px] font-medium text-text">Drinking water needed from tankers</h3>
        <select aria-label="Share of rural people on tankers" value={share} onChange={(e) => setShare(Number(e.target.value))}
          className="h-7 rounded-[6px] border hairline bg-canvas px-1 text-[12px] text-text">
          {SHARES.map((s) => <option key={s} value={s}>{Math.round(s * 100)}% on tankers</option>)}
        </select>
      </div>
      <p className="num text-[22px] leading-none text-text">
        {n.kl_per_day.toLocaleString("en-IN")} kL <span className="text-[13px] text-text-2">a day</span>
      </p>
      <p className="text-[12px] leading-relaxed text-text-3">{n.formula}</p>
      {!officer ? (
        <p className="text-[12px] text-text-2">
          <Link to="/login" className="underline hover:text-text">Log in as a relief officer</Link> to ask nearby tanker vendors for this water.
        </p>
      ) : !open ? (
        <button type="button" className={PRIMARY} onClick={() => setOpen(true)}>Create tanker tender</button>
      ) : (
        <form onSubmit={publish} className="flex flex-col gap-3 border-t hairline pt-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="kL a day"><input type="number" min={1} className={INPUT} value={qty ?? n.kl_per_day} onChange={(e) => setQty(Number(e.target.value))} /></Field>
            <Field label="Days"><input type="number" min={1} max={180} className={INPUT} value={days} onChange={(e) => setDays(Number(e.target.value))} /></Field>
            <Field label="Price ₹/kL (nearby median)"><input type="number" min={1} className={INPUT} value={price ?? n.suggested_price} onChange={(e) => setPrice(Number(e.target.value))} /></Field>
            <Field label="Vendors within km"><input type="number" min={10} max={500} className={INPUT} value={radius} onChange={(e) => setRadius(Number(e.target.value))} /></Field>
          </div>
          {create.error && <p role="alert" className="text-[12px] text-heat">{(create.error as ApiError).detail ?? "Could not publish."}</p>}
          <div className="flex gap-2">
            <button type="submit" className={PRIMARY} disabled={create.isPending}>Publish tender</button>
            <button type="button" className={BUTTON} onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </form>
      )}
    </section>
  );
}
