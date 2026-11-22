import type { RunView } from "@/lib/engine/types";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ActFn = (action: "start" | "guess" | "hint" | "skip" | "submit", payload?: any) => Promise<{ run: RunView; error?: string } | null>;
export interface GameProps { run: RunView; act: ActFn; busy: boolean }
