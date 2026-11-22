// Challenge server functions, answered by Django (ZeroGambling-backend/core/views.py).
// Same names and inputs as Lovable's createServerFn versions, so the pages call them unchanged.
import { serverFn } from "./api";
import type { RunView } from "./engine/types";
import type { Summary } from "./engine/service-types";

type Token = { token: string };

export const getSummary = serverFn<Token & { demo?: boolean }, Summary>("summary");
export const issueRun = serverFn<Token & { gameId: number; fresh?: boolean }, RunView>("challenges/issue");
export const runAction = serverFn<Token & { runId: string; requestId: string; action: "start" | "guess" | "hint" | "skip" | "submit"; payload?: unknown }, { run: RunView; error?: string }>("challenges/action");
export const resetProgress = serverFn<Token & { gameId: number }, { ok: true }>("challenges/reset");
