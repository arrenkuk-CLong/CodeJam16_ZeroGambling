'use client';
import { Link } from "@/lib/router";
import { useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/query";
import { toast } from "sonner";
import { CATALOG, GROUPS, bandFor, getEntry } from "@/lib/catalog";
import { summaryQuery, worldQuery, startNewProfile, getToken } from "@/lib/player";
import type { WorldData } from "@/lib/world-types";
import { resetProgress } from "@/lib/zg.functions";
import { Button } from "@/components/ui/button";
import { GemCount } from "@/components/zg/AppHeader";
import { formatCents } from "@/lib/casino";
import { useAccount } from "@/lib/account";

const fmt = (s: string) => new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export function Profile() {
  const { data } = useQuery(summaryQuery);
  const { data: worldData } = useQuery(worldQuery);
  const world = worldData as WorldData | undefined;
  const qc = useQueryClient();
  const { account } = useAccount();
  const swap = async (demo: boolean) => {
    if (!confirm(demo ? "Switch to a new labeled judge demo profile with 42 gems? This browser will stop using the current profile." : "Start a fresh profile at 0 gems? This browser will stop using the current profile.")) return;
    startNewProfile(demo); await qc.resetQueries();
  };
  const reset = async (gameId: number) => {
    if (!confirm("Reset this skill to level 1? Your peak level, completions and gems are kept.")) return;
    await resetProgress({ data: { token: getToken(), gameId } });
    qc.invalidateQueries(); toast.success("Progress reset. Peak and history preserved.");
  };
  if (!data) return <p className="text-muted-foreground">Loading…</p>;
  const masteryMap = new Map(data.mastery.map((m) => [m.gameId, m]));
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-extrabold">{data.player.isDemo ? "Judge demo profile" : "Your progress"}</h1>
          <p className="text-muted-foreground">{data.player.lifetimePasses} lifetime passes · profile since {fmt(data.player.createdAt)}</p>
        </div>
        <GemCount value={data.player.gems} className="text-lg" />
      </div>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="text-xl font-bold">Skill trees</h2>
        <p className="text-xs text-muted-foreground">Nineteen challenges in three branches. Difficulty bands deepen at levels 10, 25 and 40.</p>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {GROUPS.map((group) => <div key={group.id} className="rounded-xl bg-muted p-4"><h3 className="font-bold text-primary">{group.label}</h3><div className="mt-3 space-y-1 border-l border-border pl-3">{CATALOG.filter((g) => g.group === group.id).map((g) => { const m=masteryMap.get(g.id); const level=m?.level??1; return <Link key={g.id} to="/play/$gameId" params={{gameId:String(g.id)}} className="relative block rounded-lg bg-card p-2.5 hover:border-primary"><span className="absolute -left-[17px] top-4 size-2 rounded-full bg-primary"/><div className="flex justify-between gap-2 text-sm"><span>#{g.id} {g.name}</span><span className="font-mono">Lv {level}</span></div><p className="mt-1 text-xs text-muted-foreground">{bandFor(level).name} · next trophies {[10,25,40].filter((t)=>t>=level).join(", ")||"all earned"}</p></Link>; })}</div></div>)}
        </div>
      </section>

      <section className="overflow-x-auto rounded-2xl border border-border bg-card shadow-card">
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground"><tr className="border-b border-border">{["Challenge", "Level", "Peak", "Best", "Passed", "XP", ""].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>
            {CATALOG.map((g) => { const m = masteryMap.get(g.id); return (
              <tr key={g.id} className="border-b border-border/50 last:border-0">
                <td className="px-4 py-2"><Link to="/play/$gameId" params={{ gameId: String(g.id) }} className="hover:text-primary"><span className="font-mono text-xs text-muted-foreground">#{g.id}</span> {g.name}</Link></td>
                <td className="px-4 py-2 font-mono">{m?.level ?? 1}</td>
                <td className="px-4 py-2 font-mono">{m?.peak ?? 1}</td>
                <td className="px-4 py-2 font-mono">{m?.best ?? "—"}</td>
                <td className="px-4 py-2 font-mono">{m ? `${m.passes}/${m.plays}` : "—"}</td>
                <td className="px-4 py-2 font-mono">{m?.xp ?? 0}</td>
                <td className="px-4 py-2 text-right">{m && m.level > 1 && <Button size="sm" variant="ghost" onClick={() => reset(g.id)}>Reset progress</Button>}</td>
              </tr>
            ); })}
          </tbody>
        </table>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xl font-bold">Completion history</h2>
          <p className="text-xs text-muted-foreground">Permanent — survives progress resets.</p>
          <ul className="mt-3 divide-y divide-border/50 text-sm">
            {data.completions.length === 0 && <li className="py-2 text-muted-foreground">No completions yet.</li>}
            {data.completions.map((c) => (
              <li key={c.id} className="flex items-center gap-3 py-2">
                <span className={`size-2 rounded-full ${c.passed ? "bg-success" : "bg-destructive"}`} />
                <span className="flex-1">{getEntry(c.gameId)?.name} <span className="text-muted-foreground">Lv {c.level}</span></span>
                <span className="font-mono">{c.score}</span>
                <span className="w-12 text-right font-mono text-gem">{c.gems ? `+${c.gems}` : ""}</span>
                <span className="w-28 text-right text-xs text-muted-foreground">{fmt(c.at)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xl font-bold">Gem ledger</h2>
          <ul className="mt-3 divide-y divide-border/50 text-sm">
            {data.ledger.length === 0 && <li className="py-2 text-muted-foreground">No entries yet.</li>}
            {data.ledger.map((l) => (
              <li key={l.id} className="flex items-center gap-3 py-2">
                <span className="flex-1">{l.reason}</span>
                <span className={`font-mono ${(l.deltaCents ?? l.delta * 100) >= 0 ? "text-success" : "text-destructive"}`}>{(l.deltaCents ?? l.delta * 100) >= 0 ? "+" : ""}{formatCents(l.deltaCents ?? l.delta * 100)}</span>
                <span className="w-16 text-right font-mono text-muted-foreground">{formatCents(l.balanceCents ?? l.balance * 100)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xl font-bold">Permanent trophy case</h2>
          <p className="text-xs text-muted-foreground">Breakthrough trophies survive every reset and full-log loss.</p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {world?.trophies.map((t) => <div key={t.id} className="rounded-xl border border-gem/40 bg-gem/10 p-3"><p className="text-lg text-gem">✦ {t.name}</p><p className="text-xs text-muted-foreground">{getEntry(t.gameId)?.name}</p></div>)}
            {!world?.trophies.length && <p className="text-sm text-muted-foreground">Pass levels 10, 25 or 40 to earn a breakthrough trophy.</p>}
          </div>
          <h3 className="mt-6 font-bold">Inventory</h3>
          <p className="mt-1 text-sm text-muted-foreground">{world?.inventory.length ?? 0} items · <Link to="/shop" className="text-primary underline">open shop</Link></p>
        </section>
        <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xl font-bold">Permanent loss ledger</h2>
          <p className="text-xs text-muted-foreground">Records what was risked and lost, even after a full-log reset.</p>
          <ul className="mt-3 divide-y divide-border/50 text-sm">
            {world?.losses.map((l) => <li key={l.id} className="py-3"><p>{l.description}</p><p className="mt-1 text-xs text-muted-foreground">{l.game} · {fmt(l.at)}</p></li>)}
            {!world?.losses.length && <li className="py-2 text-muted-foreground">No casino losses or trades recorded yet.</li>}
          </ul>
        </section>
      </div>

      <section className="overflow-x-auto rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="text-xl font-bold">Casino round audit</h2>
        <table className="mt-3 w-full text-sm"><thead className="text-left text-xs text-muted-foreground"><tr><th className="py-2">Game</th><th>Asset</th><th>Stake estimate</th><th>Net</th><th>Receipt</th></tr></thead><tbody>
          {world?.rounds.map((r) => <tr key={r.id} className="border-t border-border/50"><td className="py-2 capitalize">{r.game}<span className="block text-xs normal-case text-muted-foreground">{r.variant} · rules v2</span></td><td>{r.assetLabel}</td><td className="font-mono">{formatCents(r.stakeCents)}</td><td className={`font-mono ${r.netCents >= 0 ? "text-success" : "text-destructive"}`}>{r.netCents >= 0 ? "+" : ""}{formatCents(r.netCents)}</td><td className="font-mono text-xs text-muted-foreground">#{r.id.slice(0,8)}</td></tr>)}
          {!world?.rounds.length && <tr><td colSpan={5} className="py-3 text-muted-foreground">No settled casino rounds yet.</td></tr>}
        </tbody></table>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="text-xl font-bold">Profiles</h2>
        {account ? <p className="mt-1 text-sm text-muted-foreground">This progress is saved to your account and follows you to any device. Manage your account in <Link to="/settings" className="text-primary underline">Settings</Link>.</p> : <><p className="mt-1 text-sm text-muted-foreground">This guest profile lives in this browser. <Link to="/auth" className="text-primary underline">Create an account</Link> to keep it across devices. A new profile has a separate history; the current one is left untouched on the server.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => swap(true)}>New judge demo profile (42 gems)</Button>
          <Button variant="ghost" onClick={() => swap(false)}>New fresh profile (0 gems)</Button>
        </div></>}
      </section>
    </div>
  );
}
