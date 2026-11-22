// Non-gem assets have a payout estimate, never a cash-out or sell-back path.
import { bandFloor } from "./engine/economy";
import { gliderInvested } from "./engine/slide-balance";

export type AssetType = "gems" | "skill" | "equipment" | "glider" | "log";

export function skillBase(level: number): number {
  if (level >= 40) return 200;
  if (level >= 25) return 100;
  if (level >= 10) return 50;
  return 20;
}

export function skillPercent(level: number): number {
  return Math.max(0, Math.min(0.99, (level - 1) / 10));
}

export function skillValue(level: number, base = skillBase(level)): number {
  const p = skillPercent(level);
  return base * (0.5 * p + 0.5 * p * p);
}

export function skillStakeValue(level: number, rollbackLevel: number): number {
  if (rollbackLevel < 1 || rollbackLevel >= level) return 0;
  return Math.max(1, Math.round(skillValue(level) - skillValue(rollbackLevel, skillBase(level))));
}

export function equipmentStakeValue(shopPrice: number): number {
  return Math.max(1, Math.floor(shopPrice * 0.5));
}

/** Staking n glider levels: worth half of what those levels cost (same 50% rule as equipment). */
export function gliderStakeValue(level: number, levels: number): number {
  if (levels < 1 || levels > level) return 0;
  return equipmentStakeValue(gliderInvested(level) - gliderInvested(level - levels));
}

export function logStakeValue(levels: number[], journalEntries: number): number {
  const skills = levels.reduce((sum, level) => sum + skillStakeValue(level, 1), 0);
  return skills + Math.min(50, Math.max(0, journalEntries));
}

export function rollbackLabel(level: number): string {
  return `Level ${level} · band ${bandFloor(level)}`;
}
