// Contracts shared by the challenge engine (server) and the game UIs (browser).
export interface Evaluation {
  score: number; // 0–100
  passed: boolean;
  feedback: string[];
  metrics: Record<string, number | string>;
  void?: boolean; // run interrupted: no reward, no mastery change
}

export interface RunView {
  id: string;
  gameId: number;
  version: number;
  level: number;
  modifiers: string[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  publicData: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  stimulus: any; // only present after Ready (and never re-sent for watch-once games)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  playState: any;
  status: "issued" | "active" | "passed" | "failed" | "skipped" | "void";
  attempts: number;
  maxAttempts: number;
  hints: number;
  hintText: string[];
  timeLimitSec: number | null;
  startedAt: string | null;
  serverNow: string;
  result: RunResult | null;
}

export interface RunResult extends Evaluation {
  receipt: Receipt | null;
  reward: RewardBreakdown | null;
  answerReveal?: string;
}

export interface Receipt {
  completionId: string;
  gameId: number;
  score: number;
  xpAwarded: number;
  gemsAwarded: number;
  levelPlayed: number;
  newLevel: number;
  balance: number;
}

export interface RewardBreakdown {
  economyVersion: number;
  base: number;
  lines: { label: string; factor: number }[];
  gems: number;
  xp: number;
}
