import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { BUTTON, Field, INPUT, PRIMARY } from "@/features/tenders/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api/client";
import type { Campaign, Me, VolunteerTask } from "@/lib/api/types";
import { useMe } from "@/lib/hooks/session";

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const day = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const errorText = (e: unknown) => (e instanceof ApiError ? e.detail : "That did not work. Try again.");

export const useCampaigns = (zoneId?: string) =>
  useQuery({ queryKey: ["campaigns", zoneId ?? "all"], queryFn: ({ signal }) => apiGet<Campaign[]>("/campaigns", { zone_id: zoneId }, signal) });

export const useTasks = (zoneId?: string, viewer?: string) =>
  useQuery({ queryKey: ["tasks", zoneId ?? "all", viewer ?? "public"], queryFn: ({ signal }) => apiGet<VolunteerTask[]>("/volunteer-tasks", { zone_id: zoneId }, signal) });

/** NGO campaigns (pledges only: no money is taken) and volunteer tasks. Anyone can read; logged-in people pledge and
 *  sign up; NGO accounts start campaigns and post tasks. */
export function CommunityPage() {
  const me = useMe();
  const campaigns = useCampaigns();
  const tasks = useTasks(undefined, me.data?.id);
  if (campaigns.isPending || tasks.isPending) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><SkeletonRows rows={6} /></div>;
  if (campaigns.isError) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><ErrorState error={campaigns.error} onRetry={() => campaigns.refetch()} /></div>;
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-6 md:px-8 md:py-8">
      <header className="flex flex-col gap-2">
        <h1 className="font-display text-[34px] text-text">Community help</h1>
        <p className="max-w-[70ch] text-[13px] text-text-2">
          NGOs raise support for drought-hit areas and ask for volunteers. Pledges are promises, not payments: no money is taken here.
        </p>
      </header>
      {me.data?.role === "ngo" && <NgoForms />}
      <section aria-labelledby="campaigns-title" className="flex flex-col gap-3">
        <h2 id="campaigns-title" className="text-[15px] font-medium text-text">Campaigns</h2>
        {campaigns.data.length === 0 && <EmptyState title="No campaigns yet" body="NGO accounts can start one for a drought-hit zone." />}
        {campaigns.data.map((c) => <CampaignCard key={c.id} campaign={c} me={me.data ?? null} />)}
      </section>
      <section aria-labelledby="tasks-title" className="flex flex-col gap-3">
        <h2 id="tasks-title" className="text-[15px] font-medium text-text">Volunteer tasks</h2>
        {(tasks.data ?? []).length === 0 && <EmptyState title="No tasks yet" body="NGO accounts can post tasks that need hands on the ground." />}
        {(tasks.data ?? []).map((t) => <TaskCard key={t.id} task={t} me={me.data ?? null} />)}
      </section>
    </div>
  );
}

export function CampaignCard({ campaign: c, me }: { campaign: Campaign; me: Me | null }) {
  const client = useQueryClient();
  const [amount, setAmount] = useState(1000);
  const [done, setDone] = useState(false);
  const pledge = useMutation({
    mutationFn: () => apiPost<void>(`/campaigns/${c.id}/pledges`, { amount_inr: amount, message: null }),
    onSuccess: () => { setDone(true); client.invalidateQueries({ queryKey: ["campaigns"] }); },
  });
  const share = Math.min(1, c.pledged_inr / c.goal_inr);
  return (
    <article aria-label={c.title} className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-medium text-text">{c.title}</h3>
        <span className="text-[12px] text-text-3">
          {c.ngo_name}{c.zone_name && <> · <Link to={`/zones/${c.zone_id}`} className="underline hover:text-text">{c.zone_name}</Link></>}
        </span>
      </div>
      {c.story && <p className="text-[13px] text-text-2">{c.story}</p>}
      <div className="h-2 overflow-hidden rounded-full bg-raised" role="progressbar" aria-label="Pledged"
        aria-valuemin={0} aria-valuemax={c.goal_inr} aria-valuenow={c.pledged_inr}>
        <span className="block h-full rounded-full bg-success" style={{ width: `${share * 100}%` }} />
      </div>
      <p className="num text-[12px] text-text-2">{`${inr(c.pledged_inr)} pledged of ${inr(c.goal_inr)} by ${c.pledges} ${c.pledges === 1 ? "person" : "people"}`}</p>
      {!me ? (
        <p className="text-[12px] text-text-2"><Link to="/login?next=/community" className="underline hover:text-text">Log in</Link> or make a citizen account to pledge.</p>
      ) : done ? (
        <p className="text-[12px] text-success">Thank you. Your pledge is recorded; the NGO will contact you.</p>
      ) : (
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); pledge.mutate(); }}>
          <div className="w-40"><Field label="Pledge amount (₹)"><input type="number" min={1} max={10000000} className={INPUT} value={amount} onChange={(e) => setAmount(Number(e.target.value))} /></Field></div>
          <button type="submit" className={PRIMARY} disabled={pledge.isPending}>Pledge</button>
          {pledge.error && <p role="alert" className="text-[12px] text-heat">{errorText(pledge.error)}</p>}
        </form>
      )}
    </article>
  );
}

export function TaskCard({ task: t, me }: { task: VolunteerTask; me: Me | null }) {
  const client = useQueryClient();
  const join = useMutation({
    mutationFn: () => apiPost<void>(`/volunteer-tasks/${t.id}/signups`, {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["tasks"] }),
  });
  const left = Math.max(0, t.slots - t.taken);
  return (
    <article aria-label={t.title} className="flex flex-col gap-2 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-medium text-text">{t.title}</h3>
        <span className="text-[12px] text-text-3">{t.task_date ? day.format(new Date(`${t.task_date}T00:00:00`)) : "Any day"} · {t.ngo_name}</span>
      </div>
      {t.description && <p className="text-[13px] text-text-2">{t.description}</p>}
      <p className="num text-[12px] text-text-2">{`${left} of ${t.slots} places left`}{t.zone_name ? ` · ${t.zone_name}` : ""}</p>
      {t.signed_up ? (
        <p className="text-[12px] text-success">You are signed up.</p>
      ) : !me ? (
        <p className="text-[12px] text-text-2"><Link to="/login?next=/community" className="underline hover:text-text">Log in</Link> to sign up.</p>
      ) : (
        <div className="flex items-center gap-2">
          <button type="button" className={BUTTON} disabled={left === 0 || join.isPending} onClick={() => join.mutate()}>
            {left === 0 ? "Full" : "Sign up"}
          </button>
          {join.error && <p role="alert" className="text-[12px] text-heat">{errorText(join.error)}</p>}
        </div>
      )}
    </article>
  );
}

function NgoForms() {
  const client = useQueryClient();
  const [c, setC] = useState({ title: "", story: "", goal_inr: 100000 });
  const [t, setT] = useState({ title: "", description: "", task_date: "", slots: 10 });
  const startCampaign = useMutation({
    mutationFn: () => apiPost<{ id: string }>("/campaigns", c),
    onSuccess: () => { setC({ title: "", story: "", goal_inr: 100000 }); client.invalidateQueries({ queryKey: ["campaigns"] }); },
  });
  const postTask = useMutation({
    mutationFn: () => apiPost<{ id: string }>("/volunteer-tasks", { ...t, task_date: t.task_date || null }),
    onSuccess: () => { setT({ title: "", description: "", task_date: "", slots: 10 }); client.invalidateQueries({ queryKey: ["tasks"] }); },
  });
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <form aria-label="Start a campaign" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4"
        onSubmit={(e) => { e.preventDefault(); startCampaign.mutate(); }}>
        <h2 className="text-[13px] font-medium text-text">Start a campaign</h2>
        <Field label="Title"><input required minLength={3} maxLength={300} className={INPUT} value={c.title} onChange={(e) => setC({ ...c, title: e.target.value })} /></Field>
        <Field label="Story"><textarea maxLength={4000} rows={3} className={`${INPUT} h-auto py-1.5`} value={c.story} onChange={(e) => setC({ ...c, story: e.target.value })} /></Field>
        <Field label="Goal (₹)"><input type="number" min={1} className={INPUT} value={c.goal_inr} onChange={(e) => setC({ ...c, goal_inr: Number(e.target.value) })} /></Field>
        {startCampaign.error && <p role="alert" className="text-[12px] text-heat">{errorText(startCampaign.error)}</p>}
        <button type="submit" className={PRIMARY} disabled={startCampaign.isPending}>Start campaign</button>
      </form>
      <form aria-label="Post a volunteer task" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4"
        onSubmit={(e) => { e.preventDefault(); postTask.mutate(); }}>
        <h2 className="text-[13px] font-medium text-text">Post a volunteer task</h2>
        <Field label="Title"><input required minLength={3} maxLength={300} className={INPUT} value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} /></Field>
        <Field label="What volunteers will do"><input maxLength={2000} className={INPUT} value={t.description} onChange={(e) => setT({ ...t, description: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date"><input type="date" className={INPUT} value={t.task_date} onChange={(e) => setT({ ...t, task_date: e.target.value })} /></Field>
          <Field label="Places"><input type="number" min={1} max={1000} className={INPUT} value={t.slots} onChange={(e) => setT({ ...t, slots: Number(e.target.value) })} /></Field>
        </div>
        {postTask.error && <p role="alert" className="text-[12px] text-heat">{errorText(postTask.error)}</p>}
        <button type="submit" className={PRIMARY} disabled={postTask.isPending}>Post task</button>
      </form>
    </div>
  );
}
