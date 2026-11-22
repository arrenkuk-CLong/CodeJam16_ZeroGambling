'use client';
import { Link } from "@/lib/router";
import { useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/query";
import { useState } from "react";
import { toast } from "sonner";
import { Flag, Gem, LoaderCircle, Play, RotateCcw, Target, Trophy, Wind, Zap } from "lucide-react";
import { finishSlideRun, startSlideRun } from "@/lib/world.functions";
import { getToken, newRequestId, worldQuery } from "@/lib/player";
import type { RunResult, SlideRun, WorldData } from "@/lib/world-types";
import { Button } from "@/components/ui/button";
import { SlideGame, type SlideEnd } from "@/components/slide/SlideGame";

type Phase = "idle" | "starting" | "playing" | "saving" | "done";
const plural = (n: number) => `${n} gem${n === 1 ? "" : "s"}`;

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-2xl border border-border bg-card p-5 shadow-card"><h2 className="mb-4 text-lg font-bold">{title}</h2>{children}</section>;
}

export function Slide() {
  const { data } = useQuery(worldQuery); const world = data as WorldData | undefined;
  const qc = useQueryClient();
  const [run, setRun] = useState<SlideRun | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [outcome, setOutcome] = useState<RunResult | null>(null);
  if (!world) return <p className="text-muted-foreground">Preparing the slide…</p>;
  const g = world.game;
  const rewardsLeft = Math.max(0, g.rewardedRunsPerDay - g.rewardedRunsToday);
  const gemsAt = (m: number) => g.checkpoints.find((c) => c.m === m)?.gems ?? 0;
  const expectedCheckpoint = Math.floor(g.expectedM / 50) * 50;
  const refresh = () => { qc.invalidateQueries({ queryKey: ["world"] }); qc.invalidateQueries({ queryKey: ["summary"] }); };

  async function start() {
    setPhase("starting"); setOutcome(null);
    try { setRun(await startSlideRun({ data: { token: getToken(), requestId: newRequestId() } })); setPhase("playing"); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Could not start a run"); setPhase(run ? "done" : "idle"); }
  }
  async function end(e: SlideEnd) {
    setPhase("saving");
    try { setOutcome(await finishSlideRun({ data: { token: getToken(), runId: e.runId, result: e.result, distanceM: e.distanceM } })); refresh(); }
    catch (err) { toast.error(err instanceof Error ? err.message : "Run not saved"); setOutcome(null); }
    setPhase("done");
  }
  function resultText(o: RunResult) {
    const how = o.status === "survived" ? `You finished all ${o.distanceM} m!` : `Crashed at ${o.distanceM} m.`;
    if (!o.checkpointM) return `${how} That’s before the first checkpoint (50 m), so this run pays nothing.`;
    if (!o.gems) return `${how} Highest checkpoint: ${o.checkpointM} m (${plural(gemsAt(o.checkpointM))}), but today’s ${g.rewardedRunsPerDay} paying runs are used up.`;
    return `${how} Highest checkpoint: ${o.checkpointM} m, so +${plural(o.gems)}.`;
  }
  const message = phase === "saving" ? "Saving your run…"
    : phase === "done" && outcome ? resultText(outcome)
    : phase === "done" ? "This run wasn’t counted. Start a new one."
    : phase === "playing" ? "Dodge the cards, tokens and dice. When the open lane jumps to the other side, start steering early."
    : `With your glider you should average about ${g.expectedM} m. Only the highest checkpoint you pass pays: ${expectedCheckpoint ? `${expectedCheckpoint} m = ${plural(gemsAt(expectedCheckpoint))}` : "50 m = 1 gem"}.`;

  return <div className="space-y-6">
    <div><p className="font-mono text-xs uppercase tracking-widest text-perception">Synthwave downhill · 1000 m</p><h1 className="mt-2 text-4xl font-extrabold">Slide game</h1>
      <p className="mt-2 max-w-3xl text-muted-foreground">A synthwave downhill run hosted inside ZeroGambling. The track is the same for everyone; your glider decides how fast you can steer, and its levels can be staked in the casino, so the consequences are real here.</p></div>
    <Panel title={`Run · ${g.trackM} m · ${g.gliderLevel === null ? "no glider" : `glider level ${g.gliderLevel}`} · steering ${g.steerPct}%`}>
      <SlideGame run={run} checkpoints={g.checkpoints} onEnd={(e) => void end(e)} />
      <p className="mt-3 text-sm text-muted-foreground" role="status">{message}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={() => void start()} disabled={phase === "starting" || phase === "playing" || phase === "saving"}>
          {phase === "starting" ? <LoaderCircle className="animate-spin" /> : run ? <RotateCcw /> : <Play />}{run ? "Run again" : "Start run"}
        </Button>
        <span className="text-xs text-muted-foreground">{rewardsLeft ? `${rewardsLeft} of ${g.rewardedRunsPerDay} paying runs left today` : "No paying runs left today; you can still play for your best."}</span>
      </div>
      {g.reserved && <p className="mt-3 text-xs text-destructive">Some of your glider levels are staked in an open casino round. You can still play.</p>}
    </Panel>
    <div className="grid gap-6 md:grid-cols-2">
      <Panel title="Your glider">
        <ul className="space-y-2 text-sm">
          <li className="flex items-center gap-2"><Wind size={16} className="shrink-0 text-primary" />{g.gliderLevel === null ? `No glider: steering ${g.steerPct}% (very slow)` : `Level ${g.gliderLevel} of ${g.maxLevel}: steering ${g.steerPct}% of the top glider`}</li>
          <li className="flex items-center gap-2"><Target size={16} className="shrink-0 text-primary" />Expected reach: about {g.expectedM} m</li>
          {g.nextSteerPct !== null && <li className="flex items-center gap-2"><Zap size={16} className="shrink-0 text-primary" />
            {g.gliderLevel === null ? `Buy one (${g.gliderPrice} gems)` : `Next level (${g.upgradeCost} gems)`}: steering {g.nextSteerPct}%, about {g.nextExpectedM} m</li>}
        </ul>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button asChild variant="outline"><Link to="/shop">{g.gliderLevel === null ? "Buy a glider" : "Upgrade in the shop"}</Link></Button>
          <Button asChild variant="link" className="px-0"><Link to="/casino">Stake glider levels</Link></Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Lose a casino round with glider levels staked and your glider drops that many levels, so it steers slower. Lose the glider itself and you steer like a beginner again.</p>
      </Panel>
      <Panel title="Recent runs">
        <p className="mb-3 flex items-center gap-2 text-sm"><Trophy size={16} className="text-primary" />Best distance: {g.best} m</p>
        {g.runs.length ? <ul className="space-y-1 text-sm">{g.runs.map((r) => <li key={r.id} className="flex justify-between gap-3">
          <span className={r.status === "survived" ? "text-primary" : "text-muted-foreground"}>{r.status === "survived" ? "Finished" : r.status === "crashed" ? "Crashed" : "Abandoned"} · {r.distanceM} m{r.checkpointM ? ` · checkpoint ${r.checkpointM} m` : ""}</span>
          <span className="text-muted-foreground">{r.gems ? `+${r.gems}` : "—"}</span></li>)}</ul>
          : <p className="text-sm text-muted-foreground">No runs yet.</p>}
      </Panel>
    </div>
    <Panel title="Checkpoints">
      <p className="mb-4 flex items-center gap-2 text-sm text-muted-foreground"><Flag size={16} className="shrink-0 text-primary" />Every 50 m is a checkpoint. When a run ends, only the highest one you passed pays; they don’t add up. Crashing before 50 m pays nothing.</p>
      <ol className="grid grid-cols-5 gap-2 text-center font-mono text-xs sm:grid-cols-10">
        {g.checkpoints.map((c) => <li key={c.m} className={`rounded border px-1 py-1.5 ${c.m === expectedCheckpoint ? "border-primary bg-primary/15" : c.m <= g.best ? "border-primary/40" : "border-border/30"}`}>
          <span className="block text-muted-foreground">{c.m} m</span>
          <span className="inline-flex items-center gap-0.5 text-foreground"><Gem size={11} />{c.gems}</span>
        </li>)}
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">Highlighted: the checkpoint you should usually reach with your glider. Outlined: checkpoints you have passed before.</p>
    </Panel>
  </div>;
}
