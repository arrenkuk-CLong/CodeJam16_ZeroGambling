'use client';
import { Link } from "@/lib/router";
import { useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/query";
import { useState, type ComponentType } from "react";
import { toast } from "sonner";
import { ArrowLeft, Lightbulb, SkipForward, Trophy, Gem, RotateCw, Dices } from "lucide-react";
import { getEntry, bandFor } from "@/lib/catalog";
import { issueRun, runAction } from "@/lib/zg.functions";
import { getToken, newRequestId } from "@/lib/player";
import type { RunView } from "@/lib/engine/types";
import { ECONOMY } from "@/lib/engine/economy";
import { Button } from "@/components/ui/button";
import { Panel, Countdown } from "@/components/games/common";
import type { GameProps, ActFn } from "@/components/games/types";
import { MathChain, Pattern, Cipher, Wordle, Vocab, Typing, Mastermind, LightsOut, BaseConvert } from "@/components/games/logic";
import { SequenceMemory, Rotation, OddColor } from "@/components/games/memory";
import { DotCount, Trajectory, AngleMatch, Tempo, LineSplit, TimeEstimate, PitchMatch } from "@/components/games/perception";

const UIS: Record<number, ComponentType<GameProps>> = {
  1: MathChain, 2: Pattern, 3: Cipher, 4: Wordle, 5: Vocab, 6: Typing, 7: Mastermind, 8: LightsOut, 10: BaseConvert,
  11: SequenceMemory, 12: Rotation, 13: OddColor, 14: DotCount, 15: Trajectory, 16: AngleMatch, 17: Tempo, 18: LineSplit, 19: TimeEstimate, 20: PitchMatch,
};
const HINTABLE = new Set([1, 2, 3, 4]);

export function Play({ gameId }: { gameId: number }) {
  const entry = getEntry(gameId)!; // app/play/[gameId]/page.tsx 404s unknown IDs before this renders
  const qc = useQueryClient();
  const [nonce, setNonce] = useState(0);
  const key = ["run", entry.id, nonce];
  const { data: run, error, isLoading } = useQuery({ queryKey: key, queryFn: () => issueRun({ data: { token: getToken(), gameId: entry.id, fresh: nonce > 0 } }) as Promise<RunView>, staleTime: Infinity, refetchOnWindowFocus: false });
  const [busy, setBusy] = useState(false);
  const act: ActFn = async (action, payload) => {
    if (!run) return null;
    setBusy(true);
    const requestId = newRequestId();
    const call = () => runAction({ data: { token: getToken(), runId: run.id, requestId, action, payload } }) as Promise<{ run: RunView; error?: string }>;
    try {
      let res: { run: RunView; error?: string };
      try { res = await call(); } catch { res = await call(); } // same request id: a retry can't double-count
      qc.setQueryData(key, res.run);
      if (res.error && action !== "guess") toast.error(res.error);
      if (["submit", "guess", "skip"].includes(action)) qc.invalidateQueries({ queryKey: ["summary"] });
      return res;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Network error");
      return null;
    } finally { setBusy(false); }
  };

  const next = () => setNonce((n) => n + 1);
  const band = run ? bandFor(run.level) : null;
  const UI = UIS[entry.id]!;
  const finished = run && !["issued", "active"].includes(run.status);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" /> All challenges</Link>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs text-muted-foreground">#{entry.id} · v{entry.version}</p>
          <h1 className="text-3xl font-extrabold sm:text-4xl">{entry.name}</h1>
          <p className="text-muted-foreground">{entry.measures}</p>
        </div>
        {run && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-md bg-primary/15 px-2.5 py-1 font-mono font-semibold text-primary">Level {run.level}</span>
            <span className="rounded-md bg-secondary px-2.5 py-1 text-muted-foreground">{band?.name}</span>
            {run.modifiers.map((m) => <span key={m} className="rounded-md bg-memory/20 px-2.5 py-1 text-memory">{m}</span>)}
          </div>
        )}
      </header>

      {isLoading && <Panel className="text-center text-muted-foreground">Generating a fresh puzzle…</Panel>}
      {error && <Panel className="text-center text-destructive">{error.message}</Panel>}

      {run?.status === "issued" && (
        <Panel className="space-y-4">
          <p className="text-lg">{run.publicData.prompt}</p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>Scoring: {entry.scoring}</li>
            {run.maxAttempts > 1 && <li>Attempt budget: {run.maxAttempts} guesses.</li>}
            {run.timeLimitSec && <li>Time limit: {run.timeLimitSec} s, starting when you press Ready.</li>}
            {run.publicData.showOnce && <li>The stimulus is shown once. Reloading won't replay it.</li>}
            {run.modifiers.length > 0 && <li>Modifiers this round: {run.modifiers.join(", ")}.</li>}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button variant="hero" size="xl" disabled={busy} onClick={() => act("start")}>Ready</Button>
            <Button variant="ghost" disabled={busy} onClick={() => act("skip")}><SkipForward /> Skip (free, puzzle is consumed)</Button>
          </div>
        </Panel>
      )}

      {run?.status === "active" && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">{run.publicData.prompt}</p>
            <div className="flex items-center gap-3">
              {run.timeLimitSec && run.startedAt && <Countdown startedAt={run.startedAt} serverNow={run.serverNow} limitSec={run.timeLimitSec} />}
              {run.maxAttempts > 1 && <span className="font-mono text-sm text-muted-foreground">{run.attempts}/{run.maxAttempts}</span>}
            </div>
          </div>
          <UI key={run.id} run={run} act={act} busy={busy} />
          {run.hintText.length > 0 && <Panel className="border-warning/40 text-sm text-warning">{run.hintText.map((h) => <p key={h}>💡 {h}</p>)}</Panel>}
          <div className="flex flex-wrap gap-2">
            {HINTABLE.has(entry.id) && run.hints === 0 && (
              <Button variant="outline" size="sm" disabled={busy} onClick={() => act("hint")}><Lightbulb /> Hint (gems ×{ECONOMY.hintRate})</Button>
            )}
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => act("skip")}><SkipForward /> Skip (no gems lost)</Button>
          </div>
        </>
      )}

      {finished && run && <Result run={run} onNext={next} />}
    </div>
  );
}

function Result({ run, onNext }: { run: RunView; onNext: () => void }) {
  const r = run.result;
  const rc = r?.receipt;
  const levelUp = rc && rc.newLevel > rc.levelPlayed;
  const tone = run.status === "passed" ? "text-success" : run.status === "void" ? "text-warning" : run.status === "skipped" ? "text-muted-foreground" : "text-destructive";
  const label = { passed: "Passed", failed: "Not this time", skipped: "Skipped", void: "Run voided", issued: "", active: "" }[run.status];
  return (
    <div className="space-y-4 animate-pop-in">
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className={`font-display text-3xl font-extrabold ${tone}`}>{label}</p>
            {r && run.status !== "skipped" && <p className="mt-1 font-mono text-5xl font-semibold tabular">{r.score}<span className="text-xl text-muted-foreground">/100</span></p>}
          </div>
          {levelUp && (
            <div className="animate-breakthrough rounded-xl bg-primary/15 px-4 py-3 text-center text-primary">
              <Trophy className="mx-auto size-6" />
              <p className="font-display font-bold">Level {rc.newLevel} unlocked</p>
            </div>
          )}
        </div>
        <ul className="mt-4 space-y-1">
          {r?.feedback.map((f, i) => <li key={i} className={i === 0 ? "text-lg" : "text-sm text-muted-foreground"}>{f}</li>)}
        </ul>
        {r?.answerReveal && run.status !== "passed" && <p className="mt-3 text-sm">Answer: <span className="font-mono text-primary">{r.answerReveal}</span></p>}
        {r && Object.keys(r.metrics ?? {}).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(r.metrics).map(([k, v]) => <span key={k} className="rounded-md bg-muted px-2 py-1 font-mono text-xs">{k}: {v}</span>)}
          </div>
        )}
      </Panel>

      {rc && r?.reward && (
        <Panel>
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg font-bold">Receipt</h3>
            <span className="font-mono text-xs text-muted-foreground">#{rc.completionId.slice(0, 8)} · economy v{r.reward.economyVersion}</span>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-y-1 text-sm sm:grid-cols-4">
            <dt className="text-muted-foreground">Level played</dt><dd className="font-mono">{rc.levelPlayed} → {rc.newLevel}</dd>
            <dt className="text-muted-foreground">XP</dt><dd className="font-mono">+{rc.xpAwarded}</dd>
            <dt className="text-muted-foreground">Gems earned</dt><dd className="font-mono text-gem">+{rc.gemsAwarded}</dd>
            <dt className="text-muted-foreground">Balance</dt><dd className="font-mono">{rc.balance}</dd>
          </dl>
          {r.reward.base > 0 && (
            <p className="mt-3 text-xs text-muted-foreground">Base {r.reward.base}{r.reward.lines.map((l) => ` × ${l.factor} (${l.label})`).join("")} = {r.reward.gems} gems</p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">Settled once. Refreshing shows this same receipt.</p>
        </Panel>
      )}

      <div className="flex flex-wrap gap-2">
        <Button variant="hero" size="lg" onClick={onNext}><RotateCw /> Next puzzle</Button>
        <Button asChild variant="outline" size="lg"><Link to="/">Try another game</Link></Button>
        {(rc?.balance ?? 0) > 0 && <Button asChild variant="ghost" size="lg"><Link to="/casino"><Dices /> Casino</Link></Button>}
        <span className="ml-auto hidden items-center gap-1 text-sm text-gem sm:flex"><Gem className="size-4" />{rc?.balance}</span>
      </div>
    </div>
  );
}
