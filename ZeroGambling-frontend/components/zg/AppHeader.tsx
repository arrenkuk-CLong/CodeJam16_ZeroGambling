'use client';
import { Link } from "@/lib/router";
import { useQuery } from "@/lib/query";
import { Gem } from "lucide-react";
import { summaryQuery } from "@/lib/player";
import { formatCents } from "@/lib/casino";
import { useAccount } from "@/lib/account";

const NAV = [
  { to: "/", label: "Challenges" },
  { to: "/casino", label: "Casino" },
  { to: "/slide", label: "Slide" },
  { to: "/shop", label: "Shop" },
  { to: "/advice", label: "Advice" },
  { to: "/profile", label: "Profile" },
  { to: "/settings", label: "Settings" },
  { to: "/about", label: "About & rules" },
] as const;

export function GemCount({ value, className = "" }: { value: number | string | undefined; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-gem/15 px-3 py-1 font-mono text-sm font-semibold text-gem tabular ${className}`}>
      <Gem className="size-3.5" aria-hidden /> {value ?? "—"}
      <span className="sr-only">gems</span>
    </span>
  );
}

export function AppHeader() {
  const { data } = useQuery(summaryQuery);
  const { account, username, ready } = useAccount();
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        <Link to="/" className="flex items-center gap-2 font-display text-lg font-bold">
          <span className="grid size-7 place-items-center rounded-lg bg-primary text-primary-foreground">0</span>
          ZeroGambling
        </Link>
        <nav className="hidden gap-0.5 lg:flex">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} activeOptions={{ exact: n.to === "/" }}
              className="rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {data?.player.isDemo && <span className="rounded bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning">Judge demo profile</span>}
          {ready && (account
            ? <Link to="/settings" className="text-sm font-medium text-muted-foreground hover:text-foreground">{username ?? "Account"}</Link>
            : <Link to="/auth" className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-foreground">Sign in</Link>)}
          <Link to="/profile" aria-label="Wallet"><GemCount value={data ? formatCents(data.player.gemCents) : undefined} /></Link>
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto border-t border-border/60 px-2 py-1 lg:hidden">
        {NAV.map((n) => (
          <Link key={n.to} to={n.to} activeOptions={{ exact: n.to === "/" }} className="rounded px-3 py-1 text-sm text-muted-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground">{n.label}</Link>
        ))}
      </nav>
    </header>
  );
}
