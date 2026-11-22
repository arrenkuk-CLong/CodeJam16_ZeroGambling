import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Panel, SubmitButton } from "./common";
import type { GameProps } from "./types";

export function SequenceMemory({ run, act, busy }: GameProps) {
  const size: number = run.publicData.size;
  const stim = run.stimulus as { sequence: number[]; stepMs: number } | null;
  const [phase, setPhase] = useState<"watch" | "recall">(stim ? "watch" : "recall");
  const [lit, setLit] = useState<number | null>(null);
  const [input, setInput] = useState<number[]>([]);
  useEffect(() => {
    if (!stim) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    stim.sequence.forEach((c, i) => {
      timers.push(setTimeout(() => setLit(c), 600 + i * stim.stepMs));
      timers.push(setTimeout(() => setLit(null), 600 + i * stim.stepMs + stim.stepMs * 0.65));
    });
    timers.push(setTimeout(() => setPhase("recall"), 800 + stim.sequence.length * stim.stepMs));
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const len: number = run.publicData.length;
  return (
    <Panel className="mx-auto max-w-md text-center">
      <p className="mb-4 text-sm font-medium">{phase === "watch" ? "Watch…" : run.publicData.reverse ? "Now tap them in REVERSE order" : "Now tap them in order"}</p>
      {!stim && <p className="mb-4 text-xs text-warning">The sequence was already shown before this page reloaded, so it won't replay.</p>}
      <div className="mx-auto grid w-fit gap-2" style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}>
        {Array.from({ length: size * size }, (_, i) => (
          <button key={i} aria-label={`Cell ${i + 1}`} disabled={phase === "watch" || input.length >= len}
            onClick={() => setInput([...input, i])}
            className={`size-20 rounded-xl border transition-all duration-100 ${lit === i ? "scale-105 border-primary bg-primary shadow-glow" : "border-border bg-secondary hover:bg-accent"} disabled:cursor-default`} />
        ))}
      </div>
      <p className="mt-4 font-mono text-sm text-muted-foreground">{input.length}/{len}</p>
      {phase === "recall" && (
        <div className="mt-3 flex justify-center gap-2">
          <Button variant="ghost" onClick={() => setInput(input.slice(0, -1))} disabled={!input.length}>Undo</Button>
          <SubmitButton disabled={busy || input.length !== len} onClick={() => act("submit", { cells: input })} />
        </div>
      )}
    </Panel>
  );
}

function Shape({ cells, cls = "fill-primary" }: { cells: [number, number][]; cls?: string }) {
  const w = Math.max(...cells.map((c) => c[0])) + 1, h = Math.max(...cells.map((c) => c[1])) + 1;
  const s = Math.max(w, h);
  return (
    <svg viewBox={`-0.5 -0.5 ${s + 1} ${s + 1}`} className="size-24" aria-hidden>
      <g transform={`translate(${(s - w) / 2} ${(s - h) / 2})`}>
        {cells.map(([x, y], i) => <rect key={i} x={x} y={y} width={0.94} height={0.94} rx={0.12} className={cls} />)}
      </g>
    </svg>
  );
}
export function Rotation({ run, act, busy }: GameProps) {
  const items: { shape: [number, number][]; options: [number, number][][] }[] = run.stimulus?.items ?? [];
  const [ans, setAns] = useState<(number | undefined)[]>([]);
  return (
    <Panel className="space-y-6">
      {items.map((it, i) => (
        <div key={i} className="flex flex-wrap items-center gap-4">
          <div className="rounded-xl bg-muted p-2"><Shape cells={it.shape} cls="fill-memory" /></div>
          <span className="text-muted-foreground">→</span>
          {it.options.map((o, j) => (
            <button key={j} aria-label={`Item ${i + 1} option ${j + 1}`} onClick={() => { const a = [...ans]; a[i] = j; setAns(a); }}
              className={`rounded-xl border-2 p-2 transition ${ans[i] === j ? "border-primary bg-primary/10" : "border-border hover:border-muted-foreground"}`}>
              <Shape cells={o} cls="fill-foreground" />
            </button>
          ))}
        </div>
      ))}
      <SubmitButton disabled={busy || items.some((_, i) => ans[i] === undefined)} onClick={() => act("submit", { answers: ans })} />
    </Panel>
  );
}

export function OddColor({ run, act, busy }: GameProps) {
  const rounds: { n: number; cells: { h: number; s: number; l: number }[] }[] = run.stimulus?.rounds ?? [];
  const [ans, setAns] = useState<number[]>([]);
  const r = rounds[ans.length];
  useEffect(() => { if (rounds.length && ans.length === rounds.length && !busy) act("submit", { answers: ans }); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ans.length]);
  if (!r) return <Panel className="text-center text-muted-foreground">Checking…</Panel>;
  return (
    <Panel className="mx-auto max-w-lg text-center">
      <p className="mb-4 font-mono text-sm text-muted-foreground">Board {ans.length + 1}/5</p>
      <div className="mx-auto grid w-full max-w-sm gap-1.5" style={{ gridTemplateColumns: `repeat(${r.n}, minmax(0, 1fr))` }}>
        {r.cells.map((c, i) => (
          <button key={`${ans.length}-${i}`} aria-label={`Tile ${i + 1}`} onClick={() => setAns([...ans, i])}
            className="aspect-square rounded-md transition hover:scale-[1.03]" style={{ background: `hsl(${c.h} ${c.s}% ${c.l}%)` }} />
        ))}
      </div>
    </Panel>
  );
}
