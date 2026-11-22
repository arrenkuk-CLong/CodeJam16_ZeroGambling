'use client';
import { Link } from "@/lib/router";
import { useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Bot, Eye, EyeOff, ShieldCheck, Volume2, VolumeX } from "lucide-react";
import { CASINO_GAMES, casinoVariant, crashTargetStep, expectedValue, formatCents, parseCents, SIX_DRAW_STEPS, type CasinoGameId, type CasinoVariant } from "@/lib/casino";
import { startWager, actOnWager } from "@/lib/world.functions";
import { getToken, newRequestId, summaryQuery, worldQuery } from "@/lib/player";
import type { AssetInput, CasinoSession, WorldData } from "@/lib/world-types";
import type { Summary } from "@/lib/engine/service-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GemCount } from "@/components/zg/AppHeader";
import { estimateAssetCents, StakeBuilder } from "@/components/casino/StakeBuilder";
import { BaccaratView, BlackjackView, CrashView, PokerView, RouletteView, SettlementLines, SixDrawView, SlotsView, type RouletteTicket } from "@/components/casino/CasinoViews";

const defaultVariant = (game: CasinoGameId) => game === "blackjack" ? "simple" : game === "slots" ? "prototype" : game === "baccarat" ? "commission" : game === "crash" ? "auto" : game === "sixdraw" ? "classic" : game === "poker" ? "showdown" : "european";
const defaultOption = (game: CasinoGameId) => game === "roulette" ? "red" : game === "blackjack" ? "standard" : game === "slots" ? "three" : game === "baccarat" ? "banker" : game === "crash" ? "2" : game === "sixdraw" ? "survive" : "ante";
const targetFromInput = (value: string) => { const cents = parseCents(value); return cents === null ? 0 : cents; };

export function Casino() {
  const { data: summaryData } = useQuery(summaryQuery);
  const { data: worldData } = useQuery(worldQuery);
  const summary = summaryData as Summary | undefined, world = worldData as WorldData | undefined;
  const qc = useQueryClient();
  const [gameId, setGameId] = useState<CasinoGameId>("roulette");
  const [variantId, setVariantId] = useState("european");
  const [optionId, setOptionId] = useState("red");
  const [asset, setAsset] = useState<AssetInput>({ type: "gems", amount: "5.00" });
  const [session, setSession] = useState<CasinoSession | null>(null);
  const [tickets, setTickets] = useState<RouletteTicket[]>([]);
  const [slotLines, setSlotLines] = useState<1 | 3>(1);
  const [crashTarget, setCrashTarget] = useState("2.00"), [autoTarget, setAutoTarget] = useState("");
  const [busy, setBusy] = useState(false), [skipAnimation, setSkipAnimation] = useState(false);
  const [muted, setMuted] = useState(false), [reduced, setReduced] = useState(false);
  const pending = useRef<string | null>(null), busyRef = useRef(false);
  const active = session?.status === "active";
  const variants = world?.manifest.filter((v) => v.game === gameId) ?? [];
  const variant = variants.find((v) => v.id === variantId) ?? variants[0];
  const game = CASINO_GAMES.find((g) => g.id === gameId)!;
  const option = variant?.options.find((o) => o.id === optionId) ?? variant?.options[0];

  useEffect(() => { if (world?.activeSession) { const s=world.activeSession; setSession(s); setGameId(s.game as CasinoGameId); setVariantId(s.variant); setOptionId(s.option); } }, [world?.activeSession?.id]);
  useEffect(() => { if (world) setReduced(world.preferences.reducedMotion); }, [world?.preferences.reducedMotion]);
  useEffect(() => { busyRef.current = busy; }, [busy]);

  const refresh = () => { qc.invalidateQueries({ queryKey: ["summary"] }); qc.invalidateQueries({ queryKey: ["world"] }); };
  const selectGame = (id: CasinoGameId) => { if (active) return; setGameId(id); setVariantId(defaultVariant(id)); setOptionId(defaultOption(id)); setSession(null); setTickets([]); };
  const selectVariant = (v: CasinoVariant) => { if (active) return; setVariantId(v.id); setSession(null); setTickets([]); if (!v.assetStakes) setAsset({ type: "gems", amount: "5.00" }); if (v.game === "sixdraw") setOptionId(v.id === "classic" ? "survive" : "3"); };
  const multi = gameId === "roulette" || gameId === "baccarat";
  // Changing the chip size keeps tickets already on the table; only switching to/from a non-gem stake clears them.
  const changeAsset = (next: AssetInput) => { if (next.type !== "gems" || asset.type !== "gems") { if (tickets.length) toast.message("Non-gem stakes cover a single bet, so the table was cleared."); setTickets([]); } setAsset(next); };
  const stakeCents = summary && world && variant ? estimateAssetCents(summary, world, asset) : 0;
  const totalCents = multi ? tickets.reduce((sum, t) => sum + t.stakeCents, 0) : stakeCents;
  const target = targetFromInput(crashTarget);

  const commit = async () => {
    if (!summary || !world || !variant) return;
    if (multi && !tickets.length) { toast.error(gameId === "roulette" ? "Add at least one roulette ticket." : "Place a chip on Player, Banker or Tie."); return; }
    if (totalCents < 1 || totalCents > variant.exposureLimitCents) { toast.error(`Total stake must be 0.01–${formatCents(variant.exposureLimitCents)}.`); return; }
    if (asset.type === "gems" && summary.player.gemCents < totalCents) { toast.error("Not enough gems for the total exposure."); return; }
    if (world.preferences.confirmStakes && !window.confirm(`Commit ${formatCents(totalCents)} in estimated value to ${game.name} · ${variant.name}? The outcome is final.`)) return;
    setBusy(true); pending.current ??= newRequestId();
    try {
      const commitAsset: AssetInput = asset.type === "gems" ? { type: "gems", amount: formatCents(totalCents) } : asset;
      const config = { variant: variant.id, tickets: multi ? tickets : undefined, lines: gameId === "slots" ? slotLines : undefined,
        target: gameId === "crash" ? target : gameId === "sixdraw" && variant.id === "target" ? Number(optionId) : undefined,
        autoTarget: gameId === "crash" && variant.id === "live" ? (autoTarget ? targetFromInput(autoTarget) : null) : undefined };
      const engineOption = multi ? tickets[0]!.betId : optionId;
      const result = await startWager({ data: { token: getToken(), requestId: pending.current, game: gameId, option: engineOption, asset: commitAsset, config } }) as CasinoSession;
      pending.current = null; setSession(result); setSkipAnimation(false); refresh();
      if (result.result) toast[result.result.status === "win" ? "success" : "message"](result.result.label);
    } catch (e) { pending.current = null; toast.error(e instanceof Error ? e.message : "Could not place stake"); }
    finally { setBusy(false); }
  };

  const act = async (action: string, payload: { holds?: number[]; tile?: number; insuranceCents?: number } = {}) => {
    if (!session) return;
    setBusy(true); busyRef.current = true;
    try {
      const result = await actOnWager({ data: { token: getToken(), requestId: newRequestId(), sessionId: session.id, action, ...payload } }) as CasinoSession;
      setSession(result); if (result.result) { toast[result.result.status === "win" ? "success" : "message"](result.result.label); refresh(); }
    } catch (e) { toast.error(e instanceof Error ? e.message : "Action failed"); refresh(); }
    finally { setBusy(false); busyRef.current = false; }
  };

  useEffect(() => {
    if (!session || session.game !== "crash" || session.variant !== "live" || session.status !== "active") return;
    let stopped = false, timer = 0;
    const tick = async () => {
      if (stopped) return;
      if (!busyRef.current) {
        try {
          const next = await actOnWager({ data: { token: getToken(), requestId: newRequestId(), sessionId: session.id, action: "tick", holds: [] } }) as CasinoSession;
          if (!stopped) { setSession(next); if (next.result) { toast[next.result.status === "win" ? "success" : "message"](next.result.label); refresh(); } }
        } catch (e) { if (!stopped) toast.error(e instanceof Error ? e.message : "Crash synchronization failed"); }
      }
      if (!stopped) timer = window.setTimeout(tick, 50);
    };
    timer = window.setTimeout(tick, 50);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [session?.id, session?.status, session?.variant]);

  if (!summary || !world || !variant) return <p className="text-muted-foreground">Loading the tables…</p>;
  const visible = session?.game === gameId && session.variant === variant.id ? session : null;
  const result = visible?.result;
  const gemCredit = result ? visible.assetType === "gems" ? result.returnCents : result.status === "win" ? Math.max(0, result.returnCents - visible.stakeCents) : 0 : 0;
  const currentStep = gameId === "crash" && variant.id === "auto" ? crashTargetStep(target) : gameId === "sixdraw" ? SIX_DRAW_STEPS[(variant.id === "classic" ? 3 : Number(optionId)) - 1]! : gameId === "slots" ? slotLines : gameId === "baccarat" && optionId === "banker" ? variant.id === "commission" ? 20 : 2 : variant.stakeStepCents;
  const fixedReturn = gameId === "crash" && target >= 101 ? Math.floor(totalCents * target / 100) : gameId === "sixdraw" ? Math.floor(totalCents * (0.9 / ((6 - (variant.id === "classic" ? 3 : Number(optionId))) / 6))) : gameId === "blackjack" ? Math.floor(totalCents * 2.5) : null;

  // A chip can't take the table past your wallet or the table limit; remove tickets with Undo, Clear or ×.
  const overLimit = () => {
    if (asset.type !== "gems") return false;
    const next = totalCents + stakeCents;
    if (next > summary.player.gemCents) { toast.error(`That chip would put ${formatCents(next)} on the table, but you have ${formatCents(summary.player.gemCents)}.`); return true; }
    if (next > variant.exposureLimitCents) { toast.error(`The table limit is ${formatCents(variant.exposureLimitCents)}.`); return true; }
    return false;
  };
  const addTicket = (betId: string) => {
    if (stakeCents < 1) { toast.error("Choose a chip value first."); return; }
    if (overLimit()) return;
    if (asset.type !== "gems" && tickets.length) { toast.error("An asset stake fits one ticket; use gems for overlapping tickets."); return; }
    if (asset.type !== "gems" && variant.id === "french" && ["red", "black", "even", "odd", "low", "high"].includes(betId)) { toast.error("La partage tickets accept gems only for asset compatibility."); return; }
    setTickets((old) => [...old, { betId, stakeCents }]);
  };
  const addBaccarat = (betId: string) => {
    setOptionId(betId);
    if (stakeCents < 1) { toast.error("Choose a chip value first."); return; }
    if (asset.type !== "gems") { setTickets([{ betId, stakeCents }]); return; }
    if (overLimit()) return;
    setTickets((old) => [...old, { betId, stakeCents }]);
  };
  const newHand = () => { setSession(null); setTickets([]); setAsset({ type: "gems", amount: "5.00" }); refresh(); };
  const toggleMotion = () => { const next=!reduced; setReduced(next); document.documentElement.classList.toggle("reduce-motion", next); };

  return <div className="space-y-6">
    <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4"/> Exit to challenges</Link>
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="font-mono text-xs uppercase tracking-widest text-primary">Seven games · fifteen tables · exact virtual credits</p><h1 className="mt-2 text-4xl font-extrabold">The house edge, laid bare.</h1><p className="mt-2 max-w-2xl text-muted-foreground">Built like a real online casino, house edge included — with virtual gems only. Versioned rules and a receipt for every ticket and hand.</p></div><div className="flex items-center gap-2"><GemCount value={formatCents(summary.player.gemCents)} className="text-lg"/><Button size="icon" variant="ghost" aria-label={muted ? "Unmute" : "Mute"} onClick={() => { setMuted(!muted); document.documentElement.dataset["sound"] = muted ? "on" : "off"; }}>{muted ? <VolumeX/> : <Volume2/>}</Button><Button size="icon" variant="ghost" aria-label={reduced ? "Enable motion" : "Reduce motion"} onClick={toggleMotion}>{reduced ? <EyeOff/> : <Eye/>}</Button></div></div>
    <div className="flex gap-2 overflow-x-auto pb-2">{CASINO_GAMES.map((g) => <Button key={g.id} variant={g.id === gameId ? "felt" : "ghost"} disabled={active} onClick={() => selectGame(g.id)}>{g.name}</Button>)}</div>
    <div className="flex flex-wrap items-center gap-2"><span className="mr-2 text-xs uppercase tracking-widest text-muted-foreground">Table</span>{variants.map((v) => <Button key={v.id} size="sm" variant={v.id === variant.id ? "secondary" : "outline"} disabled={active} onClick={() => selectVariant(v)}>{v.name}</Button>)}<span className="ml-auto font-mono text-xs text-muted-foreground">rules v{variant.rulesVersion}</span></div>
    <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
      <section className="relative overflow-hidden rounded-3xl border-4 border-felt-deep bg-felt p-4 shadow-card sm:p-6">
        <div className="mb-3 flex items-center justify-between text-xs text-foreground/70"><span className="inline-flex items-center gap-1"><ShieldCheck className="size-4"/> Server-decided · receipt #{visible?.id.slice(0, 8) ?? "new"}</span><span className="flex items-center gap-2">{["blackjack", "poker"].includes(gameId) && <span className="inline-flex items-center gap-1"><Bot className="size-4"/> Dealer bot</span>}{visible && <button className="underline" onClick={() => setSkipAnimation(true)}>Skip animation</button>}</span></div>
        {gameId === "roulette" && <RouletteView session={visible} variant={variant.id} tickets={tickets} chipCents={stakeCents} disabled={busy || active} onAddTicket={addTicket} onUndo={() => setTickets((old) => old.slice(0, -1))} onClear={() => setTickets([])} onRemove={(i) => setTickets((old) => old.filter((_, j) => j !== i))} skipAnimation={skipAnimation || reduced}/>}
        {gameId === "blackjack" && <BlackjackView session={visible} busy={busy} act={act} balanceCents={summary.player.gemCents}/>}
        {gameId === "slots" && <SlotsView session={visible}/>}
        {gameId === "baccarat" && <BaccaratView session={visible}/>}
        {gameId === "crash" && <CrashView session={visible}/>}
        {gameId === "sixdraw" && <SixDrawView session={visible} busy={busy} act={act}/>}
        {gameId === "poker" && <PokerView session={visible} busy={busy} act={act}/>}
      </section>
      <aside className="space-y-4">
        <section className="rounded-2xl border border-border bg-card p-5 shadow-card"><h2 className="text-xl font-bold">{game.name} · {variant.name}</h2><p className="mt-1 text-sm text-muted-foreground">{variant.rules}</p>
          {gameId === "baccarat" && <div className="mt-4 space-y-2"><p className="text-xs text-muted-foreground">Tap a bet to place a chip of the current size. Change the chip size any time; placed chips stay.</p><div className="flex flex-wrap gap-2">{variant.options.map((o) => { const sum = tickets.filter((t) => t.betId === o.id).reduce((a, t) => a + t.stakeCents, 0); return <Button key={o.id} size="sm" variant={sum ? "default" : "outline"} disabled={active || busy} onClick={() => addBaccarat(o.id)}>{o.label}{sum ? ` · ${formatCents(sum)}` : ""}</Button>; })}</div>{tickets.length > 0 && <div className="flex gap-2"><Button size="sm" variant="outline" disabled={active || busy} onClick={() => setTickets((old) => old.slice(0, -1))}>Undo chip</Button><Button size="sm" variant="outline" disabled={active || busy} onClick={() => setTickets([])}>Clear bets</Button></div>}</div>}
          {gameId !== "roulette" && gameId !== "crash" && gameId !== "baccarat" && <div className="mt-4 flex flex-wrap gap-2">{variant.options.map((o) => <Button key={o.id} size="sm" variant={o.id === optionId ? "default" : "outline"} disabled={active} onClick={() => setOptionId(o.id)}>{o.label}</Button>)}</div>}
          {gameId === "crash" && <div className="mt-4 space-y-3"><div className="flex gap-2">{[1.5, 2, 5].map((n) => <Button key={n} size="sm" variant={target === n * 100 ? "default" : "outline"} disabled={active} onClick={() => setCrashTarget(n.toFixed(2))}>{n.toFixed(2)}×</Button>)}</div><label className="block text-xs">{variant.id === "auto" ? "Target" : "Optional auto target"}<Input className="mt-1 font-mono" value={variant.id === "auto" ? crashTarget : autoTarget} disabled={active} placeholder={variant.id === "live" ? "Off" : "2.00"} onChange={(e) => variant.id === "auto" ? setCrashTarget(e.target.value) : setAutoTarget(e.target.value)} /></label></div>}
          {gameId === "slots" && variant.id === "classic" && <div className="mt-3 flex gap-2"><Button size="sm" variant={slotLines === 1 ? "default" : "outline"} disabled={active} onClick={() => setSlotLines(1)}>Center only</Button><Button size="sm" variant={slotLines === 3 ? "default" : "outline"} disabled={active} onClick={() => setSlotLines(3)}>All 3 lines</Button></div>}
          <dl className="mt-4 grid grid-cols-2 gap-y-2 rounded-xl bg-muted p-3 text-sm"><dt className="text-muted-foreground">Win chance</dt><dd className="text-right font-mono">{gameId === "blackjack" || gameId === "poker" ? "decision-dependent" : gameId === "roulette" ? "per ticket" : gameId === "crash" ? target >= 101 ? `${(Number((97n * 9_007_199_254_740_992n) / BigInt(target)) / 9_007_199_254_740_992 * 100).toFixed(3)}%` : "—" : option ? `${(option.p * 100).toFixed(2)}%` : "—"}</dd><dt className="text-muted-foreground">Stake step</dt><dd className="text-right font-mono">{formatCents(currentStep)}</dd><dt className="text-muted-foreground">Exposure limit</dt><dd className="text-right font-mono">{formatCents(variant.exposureLimitCents)}</dd><dt className="text-muted-foreground">Stake-inclusive return</dt><dd className="text-right font-mono text-gem">{fixedReturn !== null ? formatCents(fixedReturn) : "see paytable"}</dd>{option && !["blackjack", "poker", "roulette"].includes(gameId) && <><dt className="text-muted-foreground">Expected net / unit</dt><dd className="text-right font-mono text-destructive">{expectedValue(option).toFixed(3)}</dd></>}</dl>{variant.probabilityNote && <p className="mt-2 text-xs text-muted-foreground">{variant.probabilityNote}</p>}
        </section>
        <StakeBuilder summary={summary} world={world} value={asset} onChange={changeAsset} disabled={busy || active} variant={variant} undoable={!multi}/>
        {gameId === "crash" && variant.id === "live" && active ? <Button variant="gem" size="xl" className="w-full" disabled={busy} onClick={() => act("cashout")}>Cash out {formatCents(visible?.view.cashOutCents ?? 0)}</Button> : !active && <Button variant="gem" size="xl" className="w-full" disabled={busy || totalCents < 1 || (asset.type === "gems" && totalCents > summary.player.gemCents)} onClick={commit}>{busy ? "Committing…" : session ? "Start another wager" : gameId === "roulette" ? `Spin · ${formatCents(totalCents)}` : gameId === "baccarat" ? `Deal · ${formatCents(totalCents)}` : "Commit stake"}</Button>}
        {session && !active && <Button variant="outline" className="w-full" onClick={newHand}>Clear table</Button>}
        {result && visible && <section className="animate-pop-in rounded-2xl border border-border bg-card p-5 shadow-card" aria-live="polite"><p className={`font-display text-2xl font-bold ${result.status === "win" ? "text-success" : result.status === "loss" ? "text-destructive" : "text-warning"}`}>{result.status === "win" ? "Win" : result.status === "loss" ? "Loss" : "Push"}</p><p className="mt-1 text-sm text-muted-foreground">{result.label}</p><dl className="mt-4 grid grid-cols-3 gap-2 text-center text-sm"><div><dt className="text-xs text-muted-foreground">Committed</dt><dd className="font-mono">{formatCents(result.committedCents)}</dd></div><div><dt className="text-xs text-muted-foreground">Gem return</dt><dd className="font-mono">{formatCents(gemCredit)}</dd></div><div><dt className="text-xs text-muted-foreground">Net estimate</dt><dd className={`font-mono ${result.netCents >= 0 ? "text-success" : "text-destructive"}`}>{result.netCents >= 0 ? "+" : ""}{formatCents(result.netCents)}</dd></div></dl><p className="mt-3 text-xs text-muted-foreground">New balance {formatCents(result.balanceCents ?? summary.player.gemCents)} · {visible.assetLabel} · rules v{visible.rulesVersion}</p><SettlementLines lines={result.lines}/><Link to="/" className="mt-3 inline-block text-sm text-primary underline">Leave the casino — back to challenges</Link></section>}
      </aside>
    </div>
  </div>;
}
