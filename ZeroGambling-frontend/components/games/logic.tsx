import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Panel, SubmitButton, PEG_COLORS } from "./common";
import type { GameProps } from "./types";

export function MathChain({ run, act, busy }: GameProps) {
  const [v, setV] = useState("");
  return (
    <Panel className="text-center">
      <p className="font-mono text-3xl font-semibold leading-relaxed sm:text-4xl">{run.stimulus?.expression}</p>
      <form className="mx-auto mt-6 flex max-w-sm gap-2" onSubmit={(e) => { e.preventDefault(); act("submit", { answer: v }); }}>
        <Input autoFocus inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} placeholder="Your answer" className="h-12 text-center font-mono text-xl" aria-label="Answer" />
        <SubmitButton onClick={() => act("submit", { answer: v })} disabled={busy || !v.trim()} />
      </form>
    </Panel>
  );
}

export function Pattern({ run, act, busy }: GameProps) {
  const terms: (number | null)[] = run.stimulus?.terms ?? [];
  const [vals, setVals] = useState<Record<number, string>>({});
  const missing = terms.map((t, i) => (t === null ? i : -1)).filter((i) => i >= 0);
  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {terms.map((t, i) => t === null
          ? <Input key={i} aria-label={`Term ${i + 1}`} value={vals[i] ?? ""} onChange={(e) => setVals({ ...vals, [i]: e.target.value })} className="h-14 w-24 text-center font-mono text-xl" />
          : <span key={i} className="grid h-14 min-w-16 place-items-center rounded-lg bg-muted px-3 font-mono text-xl">{t}</span>)}
      </div>
      <div className="mt-6 text-center"><SubmitButton disabled={busy || missing.some((i) => !vals[i]?.trim())} onClick={() => act("submit", { answers: missing.map((i) => vals[i]) })} /></div>
    </Panel>
  );
}

export function Cipher({ run, act, busy }: GameProps) {
  const [v, setV] = useState("");
  return (
    <Panel>
      <p className="text-sm text-muted-foreground">{run.stimulus?.cipher} · {run.stimulus?.keyInfo}</p>
      <p className="mt-3 break-all rounded-lg bg-muted p-4 font-mono text-2xl tracking-widest">{run.stimulus?.cipherText}</p>
      <Textarea value={v} onChange={(e) => setV(e.target.value)} placeholder="Decoded message" className="mt-4 font-mono text-lg" aria-label="Decoded message" />
      <div className="mt-4"><SubmitButton disabled={busy || !v.trim()} onClick={() => act("submit", { answer: v })} /></div>
    </Panel>
  );
}

const markCls = { g: "bg-success text-primary-foreground", y: "bg-warning text-gem-foreground", x: "bg-secondary text-muted-foreground" } as const;
export function Wordle({ run, act, busy }: GameProps) {
  const len: number = run.publicData.length;
  const history: { guess: string; marks: ("g" | "y" | "x")[] }[] = run.playState.history ?? [];
  const [v, setV] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => { const r = await act("guess", { guess: v }); if (r?.error) setErr(r.error); else { setErr(null); setV(""); } };
  const rows = Array.from({ length: run.maxAttempts }, (_, i) => history[i]);
  return (
    <Panel className="mx-auto max-w-md">
      <div className="space-y-1.5">
        {rows.map((h, r) => (
          <div key={r} className="flex justify-center gap-1.5">
            {Array.from({ length: len }, (_, c) => {
              const ch = h ? h.guess[c] : r === history.length ? v[c]?.toUpperCase() : "";
              return <span key={c} className={`grid size-12 place-items-center rounded-md border font-display text-xl font-bold ${h ? markCls[h.marks[c]!] + " border-transparent" : "border-border"}`}>{ch}</span>;
            })}
          </div>
        ))}
      </div>
      {run.status === "active" && (
        <form className="mt-5 flex gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <Input autoFocus maxLength={len} value={v} onChange={(e) => setV(e.target.value.replace(/[^a-z]/gi, ""))} className="h-11 font-mono uppercase tracking-[0.4em]" aria-label="Guess" />
          <Button type="submit" variant="hero" disabled={busy || v.length !== len}>Guess</Button>
        </form>
      )}
      {err && <p className="mt-2 text-sm text-warning">{err}</p>}
      <p className="mt-3 text-xs text-muted-foreground">🟩 right spot · 🟨 in word, wrong spot · ⬜ not in word{run.publicData.hardMode ? " · Hard mode: reuse revealed hints" : ""}</p>
    </Panel>
  );
}

export function Vocab({ run, act, busy }: GameProps) {
  const items: { q: string; options: string[] }[] = run.stimulus?.items ?? [];
  const [ans, setAns] = useState<(number | undefined)[]>([]);
  return (
    <Panel className="space-y-5">
      {items.map((it, i) => (
        <div key={i}>
          <p className="font-medium"><span className="font-mono text-muted-foreground">{i + 1}.</span> {it.q}</p>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {it.options.map((o, j) => (
              <Button key={j} variant={ans[i] === j ? "default" : "outline"} onClick={() => { const a = [...ans]; a[i] = j; setAns(a); }}>{o}</Button>
            ))}
          </div>
        </div>
      ))}
      <SubmitButton disabled={busy || items.some((_, i) => ans[i] === undefined)} onClick={() => act("submit", { answers: ans })} />
    </Panel>
  );
}

export function Typing({ run, act, busy }: GameProps) {
  const passage: string = run.stimulus?.passage ?? "";
  const [text, setText] = useState("");
  const pasted = useRef(false);
  const t0 = useRef<number | null>(null);
  const submit = () => act("submit", { text, elapsedMs: t0.current ? performance.now() - t0.current : 0, pasted: pasted.current });
  return (
    <Panel>
      <p className="select-none rounded-lg bg-muted p-4 font-mono text-lg leading-relaxed" aria-label="Passage">
        {passage.split("").map((ch, i) => (
          <span key={i} className={i < text.length ? (text[i] === ch ? "text-success" : "bg-destructive/40 text-destructive-foreground") : i === text.length ? "border-b-2 border-primary" : "text-muted-foreground"}>{ch}</span>
        ))}
      </p>
      <Textarea autoFocus value={text} spellCheck={false} autoComplete="off" autoCorrect="off"
        onPaste={(e) => { e.preventDefault(); pasted.current = true; }}
        onChange={(e) => { if (t0.current === null) t0.current = performance.now(); setText(e.target.value); }}
        className="mt-4 font-mono text-lg" aria-label="Type here" />
      <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
        <span>Timer starts on your first key. Needs ≥ {(run.publicData.minAccuracy * 100).toFixed(1)}% and ≥ {Math.round(run.publicData.minWpm)} WPM.</span>
        <SubmitButton disabled={busy || !text} onClick={submit}>Finish</SubmitButton>
      </div>
    </Panel>
  );
}

export function Mastermind({ run, act, busy }: GameProps) {
  const { positions, symbols } = run.publicData as { positions: number; symbols: number };
  const history: { guess: number[]; exact: number; misplaced: number }[] = run.playState.history ?? [];
  const [cur, setCur] = useState<number[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const send = async () => { const r = await act("guess", { guess: cur }); if (r?.error) setErr(r.error); else { setErr(null); setCur([]); } };
  const Peg = ({ c, size = "size-8" }: { c: number | undefined; size?: string }) => <span className={`${size} inline-block rounded-full border border-border`} style={c === undefined ? undefined : { background: PEG_COLORS[c] }} />;
  return (
    <Panel className="mx-auto max-w-lg">
      <div className="space-y-2">
        {history.map((h, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="w-6 font-mono text-xs text-muted-foreground">{i + 1}</span>
            <div className="flex gap-1.5">{h.guess.map((c, j) => <Peg key={j} c={c} />)}</div>
            <span className="ml-auto font-mono text-sm"><span className="text-success">● {h.exact}</span> <span className="ml-2 text-warning">○ {h.misplaced}</span></span>
          </div>
        ))}
      </div>
      {run.status === "active" && (
        <div className="mt-5 border-t border-border pt-5">
          <div className="flex gap-2">{Array.from({ length: positions }, (_, i) => <button key={i} aria-label={`Slot ${i + 1}`} onClick={() => setCur(cur.filter((_, j) => j !== i))}><Peg c={cur[i]} size="size-10" /></button>)}</div>
          <div className="mt-4 flex flex-wrap gap-2">
            {Array.from({ length: symbols }, (_, c) => (
              <button key={c} aria-label={`Color ${c + 1}`} disabled={cur.length >= positions} onClick={() => setCur([...cur, c])} className="rounded-full p-0.5 ring-offset-2 ring-offset-card hover:ring-2 hover:ring-ring disabled:opacity-40"><Peg c={c} /></button>
            ))}
          </div>
          <div className="mt-4 flex gap-2"><Button variant="hero" disabled={busy || cur.length !== positions} onClick={send}>Guess</Button><Button variant="ghost" onClick={() => setCur([])}>Clear</Button></div>
          {err && <p className="mt-2 text-sm text-warning">{err}</p>}
          <p className="mt-3 text-xs text-muted-foreground">● right color, right spot · ○ right color, wrong spot{run.publicData.duplicates ? " · colors may repeat" : ""}</p>
        </div>
      )}
    </Panel>
  );
}

function press(board: number[], n: number, idx: number, wrap: boolean) {
  const b = [...board]; const r = Math.floor(idx / n), c = idx % n;
  for (let [rr, cc] of [[r, c], [r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]] as [number, number][]) {
    if (wrap) { rr = (rr + n) % n; cc = (cc + n) % n; } else if (rr < 0 || cc < 0 || rr >= n || cc >= n) continue;
    b[rr * n + cc] = b[rr * n + cc] ? 0 : 1;
  }
  return b;
}
export function LightsOut({ run, act, busy }: GameProps) {
  const s = run.stimulus as { n: number; board: number[]; wrap: boolean; moveLimit: number } | null;
  const [moves, setMoves] = useState<number[]>([]);
  if (!s) return null;
  const board = moves.reduce((b, m) => press(b, s.n, m, s.wrap), s.board);
  const lit = board.filter(Boolean).length;
  return (
    <Panel className="mx-auto max-w-md text-center">
      <div className="mx-auto grid w-fit gap-1.5" style={{ gridTemplateColumns: `repeat(${s.n}, minmax(0, 1fr))` }}>
        {board.map((on, i) => (
          <button key={i} aria-label={`Cell ${i + 1} ${on ? "on" : "off"}`} disabled={moves.length >= s.moveLimit}
            onClick={() => setMoves([...moves, i])}
            className={`size-14 rounded-lg border transition ${on ? "border-gem bg-gem shadow-glow" : "border-border bg-secondary"}`} />
        ))}
      </div>
      <p className="mt-4 font-mono text-sm text-muted-foreground">Moves {moves.length}/{s.moveLimit} · {lit} lit{s.wrap ? " · edges wrap" : ""}</p>
      <div className="mt-4 flex justify-center gap-2">
        <Button variant="ghost" onClick={() => setMoves(moves.slice(0, -1))} disabled={!moves.length}>Undo</Button>
        <Button variant="ghost" onClick={() => setMoves([])} disabled={!moves.length}>Reset</Button>
        <SubmitButton disabled={busy || lit > 0} onClick={() => act("submit", { moves })}>Submit solution</SubmitButton>
      </div>
    </Panel>
  );
}

export function BaseConvert({ run, act, busy }: GameProps) {
  const [v, setV] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  return (
    <Panel className="text-center">
      <p className="font-mono text-3xl font-semibold">{run.stimulus?.question}</p>
      <form className="mx-auto mt-6 flex max-w-sm gap-2" onSubmit={(e) => { e.preventDefault(); act("submit", { answer: v }); }}>
        <Input ref={ref} value={v} onChange={(e) => setV(e.target.value)} placeholder={`Answer in ${run.stimulus?.target}`} className="h-12 text-center font-mono text-xl" aria-label="Answer" />
        <SubmitButton disabled={busy || !v.trim()} onClick={() => act("submit", { answer: v })} />
      </form>
    </Panel>
  );
}
