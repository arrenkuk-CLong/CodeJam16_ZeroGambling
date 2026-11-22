import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-border bg-card p-5 shadow-card sm:p-7 ${className}`}>{children}</div>;
}

export function SubmitButton({ onClick, disabled, children = "Submit answer" }: { onClick: () => void; disabled?: boolean; children?: ReactNode }) {
  return <Button variant="hero" size="lg" onClick={onClick} disabled={disabled}>{children}</Button>;
}

export function Countdown({ startedAt, serverNow, limitSec }: { startedAt: string; serverNow: string; limitSec: number }) {
  const [now, setNow] = useState(() => Date.now());
  const [offset] = useState(() => new Date(serverNow).getTime() - Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(t); }, []);
  const left = Math.max(0, limitSec - (now + offset - new Date(startedAt).getTime()) / 1000);
  const pct = (left / limitSec) * 100;
  return (
    <div className="flex items-center gap-3" aria-live="off">
      <div className="h-1.5 w-32 overflow-hidden rounded-full bg-muted"><div className={`h-full ${left < 10 ? "bg-destructive" : "bg-primary"}`} style={{ width: `${pct}%` }} /></div>
      <span className={`font-mono text-sm tabular ${left < 10 ? "text-destructive" : "text-muted-foreground"}`}>{Math.ceil(left)}s</span>
    </div>
  );
}

export const PEG_COLORS = ["oklch(0.65 0.2 25)", "oklch(0.8 0.16 85)", "oklch(0.72 0.17 150)", "oklch(0.68 0.14 240)", "oklch(0.7 0.18 320)", "oklch(0.92 0.02 250)", "oklch(0.7 0.14 55)", "oklch(0.55 0.05 260)"];
