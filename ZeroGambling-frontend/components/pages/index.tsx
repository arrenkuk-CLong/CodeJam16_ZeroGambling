'use client';
import { Link, useNavigate } from "@/lib/router";
import { useQuery } from "@/lib/query";
import { useMemo, useState } from "react";
import { Search, Shuffle, ArrowRight } from "lucide-react";
import { CATALOG, GROUPS, ACTIVE_IDS } from "@/lib/catalog";
import { summaryQuery } from "@/lib/player";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const groupColor = { logic: "text-logic", memory: "text-memory", perception: "text-perception" } as const;
const groupBg = { logic: "bg-logic", memory: "bg-memory", perception: "bg-perception" } as const;

export function Chooser() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const { data } = useQuery(summaryQuery);
  const mastery = useMemo(() => new Map((data?.mastery ?? []).map((m) => [m.gameId, m])), [data]);
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return CATALOG;
    return CATALOG.filter((g) => [g.name, g.measures, g.example, g.depth, g.width, String(g.id)].join(" ").toLowerCase().includes(s));
  }, [q]);

  const rotate = () => {
    // Mixed rotation: sample from the 19 active IDs, avoiding the most recent game.
    const last = data?.completions[0]?.gameId;
    const pool = ACTIVE_IDS.filter((id) => id !== last);
    const pick = pool[Math.floor(Math.random() * pool.length)]!;
    navigate({ to: "/play/$gameId", params: { gameId: String(pick) } });
  };

  return (
    <div className="space-y-12">
      <section className="grid gap-8 md:grid-cols-[1.4fr_1fr] md:items-end">
        <div>
          <p className="mb-3 font-mono text-xs uppercase tracking-widest text-primary">Hackathon prototype · virtual gems only</p>
          <h1 className="text-4xl font-extrabold leading-[1.05] sm:text-6xl">Earn by getting <span className="text-primary">better</span>, not luckier.</h1>
          <p className="mt-4 max-w-xl text-lg text-muted-foreground">Pick a challenge and start playing. Each one is generated fresh, checked by code, and pays gems once for real progress.</p>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Gems" value={data?.player.gems} tone="text-gem" />
            <Stat label="Passes" value={data?.player.lifetimePasses} tone="text-primary" />
            <Stat label="Games tried" value={data?.mastery.length} tone="text-logic" />
          </div>
          <Button variant="hero" size="xl" className="mt-5 w-full" onClick={rotate}><Shuffle /> Mixed rotation</Button>
        </div>
      </section>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the 19 challenges — e.g. memory, timing, cipher" className="h-12 pl-10 text-base" aria-label="Search challenges" />
      </div>

      {GROUPS.map((grp) => {
        const games = filtered.filter((g) => g.group === grp.id);
        if (!games.length) return null;
        return (
          <section key={grp.id}>
            <div className="mb-4 flex items-baseline gap-3">
              <span className={`size-2.5 rounded-full ${groupBg[grp.id]}`} />
              <h2 className="text-2xl font-bold">{grp.label}</h2>
              <p className="text-sm text-muted-foreground">{grp.blurb}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {games.map((g) => {
                const m = mastery.get(g.id);
                return (
                  <Link key={g.id} to="/play/$gameId" params={{ gameId: String(g.id) }}
                    className="group relative flex flex-col rounded-xl border border-border bg-card p-4 shadow-card transition hover:-translate-y-0.5 hover:border-primary/60">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className={`font-mono text-xs ${groupColor[g.group]}`}>#{g.id}</span>
                        <h3 className="text-lg font-bold leading-tight">{g.name}</h3>
                      </div>
                      {m ? <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-xs tabular">Lv {m.level}{m.peak > m.level ? ` · peak ${m.peak}` : ""}</span>
                        : <span className="rounded-md bg-primary/15 px-2 py-0.5 text-xs text-primary">New</span>}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{g.measures}</p>
                    <p className="mt-3 rounded-md bg-muted px-3 py-2 font-mono text-sm">{g.example}</p>
                    <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{m ? `Best ${m.best} · ${m.passes}/${m.plays} passed` : "Level 1"}</span>
                      <span className="flex items-center gap-1 text-primary opacity-0 transition group-hover:opacity-100">Play <ArrowRight className="size-3" /></span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        );
      })}
      {!filtered.length && <p className="text-center text-muted-foreground">No challenge matches “{q}”.</p>}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | undefined; tone: string }) {
  return (
    <div>
      <div className={`font-mono text-2xl font-semibold tabular ${tone}`}>{value ?? "—"}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
