import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Panel, SubmitButton } from "./common";
import type { GameProps } from "./types";

export function DotCount({ run, act, busy }: GameProps) {
  const stim = run.stimulus as { dots: { x: number; y: number; c: number }[]; flashMs: number } | null;
  const [phase, setPhase] = useState<"wait" | "show" | "answer">(stim ? "wait" : "answer");
  const [v, setV] = useState("");
  useEffect(() => {
    if (!stim) return;
    const a = setTimeout(() => setPhase("show"), 700);
    const b = setTimeout(() => setPhase("answer"), 700 + stim.flashMs);
    return () => { clearTimeout(a); clearTimeout(b); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <Panel className="mx-auto max-w-lg text-center">
      <div className="relative mx-auto aspect-square w-full max-w-sm rounded-xl bg-muted">
        {phase === "wait" && <span className="absolute inset-0 grid place-items-center font-display text-2xl text-muted-foreground">Get ready…</span>}
        {phase === "show" && stim && (
          <svg viewBox="0 0 1 1" className="absolute inset-0 size-full" aria-label="Dots">
            {stim.dots.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={0.012} className={d.c === 0 ? "fill-gem" : "fill-logic"} />)}
          </svg>
        )}
        {phase === "answer" && <span className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">{stim ? "How many?" : "Already flashed before the page reloaded — enter your estimate."}</span>}
      </div>
      {phase === "answer" && (
        <form className="mx-auto mt-5 flex max-w-xs gap-2" onSubmit={(e) => { e.preventDefault(); act("submit", { answer: v }); }}>
          <Input autoFocus inputMode="numeric" value={v} onChange={(e) => setV(e.target.value)} className="h-12 text-center font-mono text-xl" aria-label="Dot count" />
          <SubmitButton disabled={busy || !v} onClick={() => act("submit", { answer: v })} />
        </form>
      )}
    </Panel>
  );
}

const W = 600, H = 340;
export function Trajectory({ run, act, busy }: GameProps) {
  const rounds: { points: [number, number][]; wind: string | null }[] = run.stimulus?.rounds ?? [];
  const [ans, setAns] = useState<number[]>([]);
  const [pick, setPick] = useState<number | null>(null);
  const r = rounds[ans.length];
  const toX = (x: number) => x * W, toY = (y: number) => H - 20 - y * (H - 40);
  const click = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    setPick(Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)));
  };
  const confirm = () => { if (pick === null) return; const next = [...ans, pick]; setAns(next); setPick(null); if (next.length === rounds.length) act("submit", { answers: next }); };
  if (!r) return <Panel className="text-center text-muted-foreground">Checking…</Panel>;
  return (
    <Panel>
      <p className="mb-3 font-mono text-sm text-muted-foreground">Throw {ans.length + 1}/{rounds.length}{r.wind ? ` · ${r.wind}` : ""}</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full cursor-crosshair rounded-xl bg-muted" onClick={click} role="img" aria-label="Trajectory scene; click the ground where the ball lands">
        <line x1={0} x2={W} y1={toY(0)} y2={toY(0)} className="stroke-muted-foreground" strokeWidth={2} />
        <polyline points={r.points.map(([x, y]) => `${toX(x)},${toY(y)}`).join(" ")} fill="none" className="stroke-primary" strokeWidth={3} strokeDasharray="2 6" strokeLinecap="round" />
        {(() => { const last = r.points[r.points.length - 1]!; return <circle cx={toX(last[0])} cy={toY(last[1])} r={8} className="fill-gem" />; })()}
        {pick !== null && <g><line x1={pick * W} x2={pick * W} y1={toY(0) - 30} y2={toY(0)} className="stroke-memory" strokeWidth={3} /><circle cx={pick * W} cy={toY(0)} r={6} className="fill-memory" /></g>}
      </svg>
      <div className="mt-4"><SubmitButton disabled={busy || pick === null} onClick={confirm}>{ans.length + 1 === rounds.length ? "Submit" : "Confirm landing"}</SubmitButton></div>
    </Panel>
  );
}

function angleFromEvent(e: React.PointerEvent<SVGSVGElement>) {
  const b = e.currentTarget.getBoundingClientRect();
  const dx = e.clientX - (b.left + b.width / 2), dy = e.clientY - (b.top + b.height / 2);
  return ((Math.atan2(dx, -dy) * 180) / Math.PI + 360) % 360;
}
function Ray({ deg, cls }: { deg: number; cls: string }) {
  const rad = (deg * Math.PI) / 180;
  return <line x1={0} y1={0} x2={Math.sin(rad) * 80} y2={-Math.cos(rad) * 80} className={cls} strokeWidth={6} strokeLinecap="round" />;
}
export function AngleMatch({ run, act, busy }: GameProps) {
  const rounds: { target: number; start: number }[] = run.stimulus?.rounds ?? [];
  const hideAfter: number | null = run.stimulus?.hideAfterMs ?? null;
  const [ans, setAns] = useState<number[]>([]);
  const [cur, setCur] = useState<number>(rounds[0]?.start ?? 0);
  const [hidden, setHidden] = useState(false);
  const drag = useRef(false);
  const r = rounds[ans.length];
  useEffect(() => {
    if (!r) return undefined; setCur(r.start); setHidden(false);
    if (!hideAfter) return undefined;
    const t = setTimeout(() => setHidden(true), hideAfter);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ans.length]);
  if (!r) return <Panel className="text-center text-muted-foreground">Checking…</Panel>;
  const confirm = () => { const next = [...ans, Math.round(cur * 10) / 10]; setAns(next); if (next.length === rounds.length) act("submit", { answers: next }); };
  return (
    <Panel>
      <p className="mb-3 font-mono text-sm text-muted-foreground">Round {ans.length + 1}/{rounds.length} · tolerance {run.publicData.toleranceDeg}°</p>
      <div className="grid gap-6 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="text-center" aria-live="polite">
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Target angle</p>
          <p className="mt-2 font-display text-6xl font-bold text-memory">{hidden ? "??" : `${r.target}°`}</p>
          <p className="mt-2 text-sm text-muted-foreground">{hidden ? "Target hidden — set the dial from memory." : "0° points straight up · angles grow clockwise"}</p>
        </div>
        <figure className="text-center">
          <svg viewBox="-100 -100 200 200" className="mx-auto size-56 touch-none rounded-full bg-muted" tabIndex={0} role="slider" aria-label="Your dial" aria-valuenow={Math.round(cur)} aria-valuemin={0} aria-valuemax={359}
            onPointerDown={(e) => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId); setCur(angleFromEvent(e)); }}
            onPointerMove={(e) => drag.current && setCur(angleFromEvent(e))} onPointerUp={() => (drag.current = false)}
            onKeyDown={(e) => { if (e.key === "ArrowRight" || e.key === "ArrowUp") setCur((c) => (c + (e.shiftKey ? 10 : 1)) % 360); if (e.key === "ArrowLeft" || e.key === "ArrowDown") setCur((c) => (c + 360 - (e.shiftKey ? 10 : 1)) % 360); }}>
            <circle r={90} fill="none" className="stroke-border" strokeWidth={2} />
            <line x1={0} y1={-90} x2={0} y2={-80} className="stroke-muted-foreground" strokeWidth={3} strokeLinecap="round" />
            <Ray deg={cur} cls="stroke-primary" />
            <circle r={6} className="fill-foreground" />
          </svg>
          <figcaption className="mt-2 text-sm text-muted-foreground">Drag or use arrow keys</figcaption>
        </figure>
      </div>
      <div className="mt-4 text-center"><SubmitButton disabled={busy} onClick={confirm}>{ans.length + 1 === rounds.length ? "Submit" : "Lock in"}</SubmitButton></div>
    </Panel>
  );
}

export function Tempo({ run, act, busy }: GameProps) {
  const { bpm, audibleBeats, silentBeats } = run.publicData as { bpm: number; audibleBeats: number; silentBeats: number };
  const [state, setState] = useState<"idle" | "playing" | "done" | "error">("idle");
  const [beat, setBeat] = useState(-1);
  const taps = useRef<number[]>([]);
  const t0 = useRef(0);
  const interrupted = useRef(false);
  const [tapCount, setTapCount] = useState(0);
  const iv = 60000 / bpm;
  const tap = () => { if (state !== "playing") return; taps.current.push(performance.now() - t0.current); setTapCount(taps.current.length); };
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.code === "Space") { e.preventDefault(); tap(); } };
    const vis = () => { if (document.hidden) interrupted.current = true; };
    window.addEventListener("keydown", k); document.addEventListener("visibilitychange", vis);
    return () => { window.removeEventListener("keydown", k); document.removeEventListener("visibilitychange", vis); };
  });
  const begin = () => {
    try {
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      const startAt = ctx.currentTime + 0.6;
      for (let i = 0; i < audibleBeats; i++) {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = i === 0 ? 1320 : 880; o.connect(g); g.connect(ctx.destination);
        const t = startAt + (i * iv) / 1000;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(document.documentElement.dataset["sound"] === "off" ? 0.0001 : 0.5, t + 0.005); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
        o.start(t); o.stop(t + 0.1);
      }
      const latency = ((ctx as AudioContext & { outputLatency?: number }).outputLatency ?? 0) + (ctx.baseLatency ?? 0);
      t0.current = performance.now() + (startAt - ctx.currentTime + latency) * 1000;
      setState("playing");
      const total = audibleBeats + silentBeats;
      for (let i = 0; i < total; i++) setTimeout(() => setBeat(i), t0.current - performance.now() + i * iv);
      setTimeout(() => { setState("done"); ctx.close(); act("submit", { taps: taps.current.map((x) => Math.round(x)), interrupted: interrupted.current, latencyMs: Math.round(latency * 1000) }); }, t0.current - performance.now() + total * iv + iv * 0.6);
    } catch { setState("error"); }
  };
  return (
    <Panel className="mx-auto max-w-md text-center">
      <p className="font-mono text-sm text-muted-foreground">{bpm} BPM · {audibleBeats} audible + {silentBeats} silent beats</p>
      <div className="my-6 flex justify-center gap-1.5">
        {Array.from({ length: audibleBeats + silentBeats }, (_, i) => (
          <span key={i} className={`size-3 rounded-full ${i < audibleBeats ? "bg-primary" : "bg-muted-foreground/40"} ${beat === i && i < audibleBeats ? "scale-150" : ""} transition`} />
        ))}
      </div>
      {state === "idle" && <Button variant="hero" size="xl" onClick={begin} disabled={busy}>Play beats</Button>}
      {state === "playing" && (
        <button onPointerDown={tap} className="mx-auto grid size-40 place-items-center rounded-full border-4 border-primary bg-primary/10 font-display text-2xl font-bold active:scale-95">
          TAP<span className="block font-mono text-sm font-normal text-muted-foreground">{tapCount} taps</span>
        </button>
      )}
      {state === "playing" && <p className="mt-4 text-sm text-muted-foreground">{beat >= audibleBeats ? "Silence — keep the beat!" : "Tap along…"} (space bar works too)</p>}
      {state === "done" && <p className="text-muted-foreground">Scoring…</p>}
      {state === "error" && <p className="text-warning">Audio isn't available on this device. Use Skip — it costs nothing.</p>}
      <p className="mt-4 text-xs text-muted-foreground">Hiding the tab voids the run without penalty. Device output latency is subtracted when the browser reports it.</p>
    </Panel>
  );
}

export function LineSplit({ run, act, busy }: GameProps) {
  const rounds: { label: string; origin: "left" | "right" }[] = run.stimulus?.rounds ?? [];
  const [ans, setAns] = useState<number[]>([]);
  const [pick, setPick] = useState<number | null>(null);
  const r = rounds[ans.length];
  const L = 60, R = 540;
  if (!r) return <Panel className="text-center text-muted-foreground">Checking…</Panel>;
  const click = (e: React.MouseEvent<SVGSVGElement>) => {
    const b = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - b.left) / b.width) * 600;
    setPick(Math.round(((x - L) / (R - L)) * 1000) / 1000);
  };
  const confirm = () => { if (pick === null) return; const next = [...ans, pick]; setAns(next); setPick(null); if (next.length === rounds.length) act("submit", { answers: next }); };
  return (
    <Panel className="text-center">
      <p className="font-mono text-sm text-muted-foreground">Line {ans.length + 1}/{rounds.length}</p>
      <p className="mt-2 font-display text-3xl font-bold">Mark <span className="text-primary">{r.label}</span> from the {r.origin} end</p>
      <svg viewBox="0 0 600 120" className="mt-6 w-full cursor-crosshair" onClick={click} role="img" aria-label="Line; click to mark">
        <line x1={L} x2={R} y1={60} y2={60} className="stroke-foreground" strokeWidth={4} strokeLinecap="round" />
        <circle cx={r.origin === "left" ? L : R} cy={60} r={10} className="fill-primary" />
        <line x1={r.origin === "left" ? R : L} x2={r.origin === "left" ? R : L} y1={48} y2={72} className="stroke-foreground" strokeWidth={4} />
        {pick !== null && <line x1={L + pick * (R - L)} x2={L + pick * (R - L)} y1={34} y2={86} className="stroke-memory" strokeWidth={4} />}
      </svg>
      <div className="mt-4"><SubmitButton disabled={busy || pick === null} onClick={confirm}>{ans.length + 1 === rounds.length ? "Submit" : "Confirm"}</SubmitButton></div>
    </Panel>
  );
}

export function TimeEstimate({ run, act, busy }: GameProps) {
  const t0 = useRef(performance.now());
  const hidden = useRef(false);
  const [noise, setNoise] = useState(0);
  useEffect(() => {
    const vis = () => { if (document.hidden) hidden.current = true; };
    document.addEventListener("visibilitychange", vis);
    const t = run.publicData.distraction ? setInterval(() => setNoise(Math.floor(Math.random() * 90) + 10), 370) : undefined;
    return () => { document.removeEventListener("visibilitychange", vis); if (t) clearInterval(t); };
  }, [run.publicData.distraction]);
  return (
    <Panel className="mx-auto max-w-md text-center">
      <p className="font-display text-5xl font-extrabold">{(run.publicData.targetMs / 1000).toFixed(1)} s</p>
      <p className="mt-2 text-sm text-muted-foreground">Timing started. Press Stop when you think it's up.</p>
      {run.publicData.distraction && <p className="mt-4 font-mono text-4xl text-memory tabular" aria-hidden>{noise}</p>}
      <Button variant="hero" size="xl" className="mt-6 w-40" disabled={busy} onClick={() => act("submit", { elapsedMs: Math.round(performance.now() - t0.current), hidden: hidden.current })}>Stop</Button>
    </Panel>
  );
}

export function PitchMatch({ run, act, busy }: GameProps) {
  const s = run.stimulus as { refHz: number; minHz: number; maxHz: number; playOnce: boolean } | null;
  const [pos, setPos] = useState(500);
  const [played, setPlayed] = useState(0);
  const ctx = useRef<AudioContext | null>(null);
  if (!s) return null;
  const hz = s.minHz * Math.pow(s.maxHz / s.minHz, pos / 1000);
  const play = (f: number) => {
    ctx.current ??= new AudioContext();
    const c = ctx.current, o = c.createOscillator(), g = c.createGain();
    o.type = "sine"; o.frequency.value = f; o.connect(g); g.connect(c.destination);
    const volume = document.documentElement.dataset["sound"] === "off" ? 0.0001 : 0.3;
    const t = c.currentTime; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(volume, t + 0.05); g.gain.setValueAtTime(volume, t + 0.9); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.1);
    o.start(t); o.stop(t + 1.15);
  };
  const refBlocked = s.playOnce && played >= 1;
  return (
    <Panel className="mx-auto max-w-lg text-center">
      <div className="flex justify-center gap-3">
        <Button variant="secondary" size="lg" disabled={refBlocked} onClick={() => { play(s.refHz); setPlayed(played + 1); }}>▶ Reference{s.playOnce ? (refBlocked ? " (used)" : " (once)") : ""}</Button>
        <Button variant="outline" size="lg" onClick={() => play(hz)}>▶ My tone</Button>
      </div>
      <div className="mt-8 px-2">
        <Slider value={[pos]} min={0} max={1000} step={1} onValueChange={(v) => setPos(v[0] ?? 500)} aria-label="Pitch" />
        <div className="mt-2 flex justify-between text-xs text-muted-foreground"><span>lower</span><span>higher</span></div>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">Works without a microphone. Tolerance ±{run.publicData.toleranceCents} cents.</p>
      <div className="mt-5"><SubmitButton disabled={busy || played === 0} onClick={() => act("submit", { hz: Math.round(hz * 100) / 100 })}>Lock pitch</SubmitButton></div>
    </Panel>
  );
}
