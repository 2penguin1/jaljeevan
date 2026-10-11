import { Link } from "react-router";
import { useMe } from "@/lib/hooks/session";
import { CampaignCard, TaskCard, useCampaigns, useTasks } from "./CommunityPage";

/** NGO campaigns and volunteer tasks for one zone (shown only when there are some). */
export function ZoneCommunity({ zoneId }: { zoneId: string }) {
  const me = useMe();
  const campaigns = useCampaigns(zoneId);
  const tasks = useTasks(zoneId, me.data?.id);
  const items = (campaigns.data?.length ?? 0) + (tasks.data?.length ?? 0);
  if (items === 0) return null;
  return (
    <section aria-labelledby="community-title" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 id="community-title" className="font-display text-[28px] text-text">Community help</h2>
        <Link to="/community" className="text-[13px] text-text-2 hover:text-text">All campaigns</Link>
      </div>
      {(campaigns.data ?? []).map((c) => <CampaignCard key={c.id} campaign={c} me={me.data ?? null} />)}
      {(tasks.data ?? []).map((t) => <TaskCard key={t.id} task={t} me={me.data ?? null} />)}
    </section>
  );
}
