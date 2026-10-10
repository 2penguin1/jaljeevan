import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TrendPoint } from "@/lib/api/types";

const day = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const clock = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });
const full = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export function TrendChart({ points, color }: { points: TrendPoint[]; color: string }) {
  if (points.length < 2) {
    return <p className="text-[13px] text-text-3">The trend appears after the next pipeline run.</p>;
  }
  const data = points.map((p) => ({ t: new Date(p.at).getTime(), score: Math.round(p.score * 10) / 10 }));
  const tick = data.at(-1)!.t - data[0].t < 2 * 86_400_000 ? clock : day; // short spans label by time of day
  return (
    <figure aria-label={`Score over time, from ${data[0].score} to ${data.at(-1)!.score}`} className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={(t) => tick.format(t)}
            tick={{ fill: "var(--text-3)", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={40} />
          <YAxis domain={[0, 100]} ticks={[0, 60, 100]} tick={{ fill: "var(--text-3)", fontSize: 11 }} axisLine={false} tickLine={false} />
          <ReferenceLine y={60} stroke="var(--text-3)" strokeDasharray="3 3" />
          <Tooltip
            cursor={{ stroke: "var(--hairline-strong)" }}
            contentStyle={{ background: "var(--raised)", border: "1px solid var(--hairline)", borderRadius: 6, fontSize: 12 }}
            labelFormatter={(t) => full.format(Number(t))}
            formatter={(v) => [v, "Score"]}
          />
          <Area type="monotone" dataKey="score" stroke={color} strokeWidth={1.75} fill="url(#trend-fill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
      <figcaption className="sr-only">Dashed line marks 60, the score at which a zone goes live.</figcaption>
    </figure>
  );
}
