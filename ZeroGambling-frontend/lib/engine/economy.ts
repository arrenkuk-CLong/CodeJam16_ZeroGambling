// Versioned payout rules. Every gem minted by a challenge goes through computeReward.
import type { RewardBreakdown } from "./types";

export const ECONOMY_VERSION = 1;
export const ECONOMY = {
  basePerLevel: 2,
  baseFlat: 5,
  rebuildRate: 0.5, // playtest setting: passing a level below your peak pays half
  hintRate: 0.5,
  repeatDecayPerRun: 0.15, // per same-game pass in the last hour
  repeatFloor: 0.4,
  repeatWindowMinutes: 60,
  failXp: 2,
} as const;

export interface RewardInput {
  passed: boolean;
  isVoid: boolean;
  level: number;
  peakBefore: number;
  hints: number;
  recentSameGamePasses: number;
  repeatedTask: boolean; // fingerprint already rewarded before
}

export function computeReward(i: RewardInput): RewardBreakdown {
  if (i.isVoid) return { economyVersion: ECONOMY_VERSION, base: 0, lines: [{ label: "Run voided", factor: 0 }], gems: 0, xp: 0 };
  if (!i.passed) return { economyVersion: ECONOMY_VERSION, base: 0, lines: [{ label: "Not passed", factor: 0 }], gems: 0, xp: ECONOMY.failXp };
  const base = ECONOMY.baseFlat + ECONOMY.basePerLevel * i.level;
  const lines: { label: string; factor: number }[] = [];
  if (i.repeatedTask) lines.push({ label: "Previously rewarded puzzle", factor: 0 });
  if (i.level < i.peakBefore) lines.push({ label: `Rebuilding below peak level ${i.peakBefore}`, factor: ECONOMY.rebuildRate });
  if (i.hints > 0) lines.push({ label: "Hint used", factor: ECONOMY.hintRate });
  if (i.recentSameGamePasses > 0) {
    const f = Math.max(ECONOMY.repeatFloor, 1 - ECONOMY.repeatDecayPerRun * i.recentSameGamePasses);
    lines.push({ label: `Same game ×${i.recentSameGamePasses + 1} this hour (rotate to restore)`, factor: Math.round(f * 100) / 100 });
  }
  const gems = Math.round(lines.reduce((v, l) => v * l.factor, base));
  return { economyVersion: ECONOMY_VERSION, base, lines, gems, xp: 10 + i.level };
}

/** Difficulty floor: failing can't drop you below the start of your peak's band. */
export function bandFloor(peak: number): number {
  return peak >= 40 ? 40 : peak >= 25 ? 25 : peak >= 10 ? 10 : 1;
}

export function nextLevel(level: number, peak: number, passed: boolean, isVoid: boolean): number {
  if (isVoid) return level;
  return passed ? level + 1 : Math.max(bandFloor(peak), level - 1);
}
