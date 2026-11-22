import type { Card, SettlementLine } from "./engine/casino-types";
import type { CasinoVariant } from "./casino";

export type AssetInput =
  | { type: "gems"; amount: string }
  | { type: "skill"; gameId: number; rollbackLevel: number }
  | { type: "equipment"; itemId: string }
  | { type: "glider"; levels: number }
  | { type: "log" };
export interface InventoryItem { id: string; kind: "equipment" | "collectible"; key: string; name: string; price: number; symbol: string; metadata: { description?: string; rarity?: string }; level: number; acquiredFrom: string; createdAt: string }
export interface Preferences { reducedMotion: boolean; sound: boolean; sessionReminders: boolean; allowSkillStakes: boolean; allowEquipmentStakes: boolean; allowSlideStakes: boolean; allowLogStakes: boolean; confirmStakes: boolean }
export interface GameSummary {
  gliderLevel: number | null; maxLevel: number; steerPct: number; expectedM: number;
  nextSteerPct: number | null; nextExpectedM: number | null; upgradeCost: number | null; gliderPrice: number;
  trackM: number; checkpoints: { m: number; gems: number }[];
  rewardedRunsToday: number; rewardedRunsPerDay: number; best: number;
  runs: { id: string; status: "survived" | "crashed" | "abandoned"; distanceM: number; checkpointM: number; gems: number; date: string }[];
  reserved: boolean;
}
export interface SlideObstacle { lane: number; kind: "cards" | "token" | "dice" }
export interface SlideRun { id: string; lengthM: number; gliderLevel: number | null; seed: number; lanes: number[]; steer: number; hit: { obstacleHalf: number; ballR: number; hitR: number; wallU: number; depthM: number }; rows: { z: number; obstacles: SlideObstacle[] }[]; speed: { start: number; max: number; rampM: number }; checkpointEveryM: number }
export interface RunResult { status: "survived" | "crashed" | "abandoned"; distanceM: number; checkpointM: number; gems: number }
export interface BlackjackHandView { cards: Card[]; stakeCents: number; fromSplit: boolean; splitAces: boolean; doubled: boolean; done: boolean; bust: boolean; total: number; soft: boolean }
export interface CasinoView {
  player?: Card[]; dealer?: Card[]; dealerCount?: number; phase?: string; playerTotal?: number; dealerTotal?: number;
  playerRank?: string; dealerRank?: string; number?: string; reels?: string[]; grid?: string[][]; crashAt?: number;
  trap?: number; draws?: number[]; banker?: Card[]; bankerTotal?: number; winner?: string; hands?: BlackjackHandView[];
  activeHand?: number; dealerSoft?: boolean; insuranceCents?: number; target?: number; progress?: number;
  nextSafeChance?: number | null; originalWinChance?: number; grossMultiplier?: number; multiplierCents?: number;
  cashOutCents?: number; tick?: number; launchedAt?: number; serverNow?: number; autoTarget?: number | null;
  firstFailedTick?: number; lastPayableTick?: number; payableTick?: number | null; receiptAt?: string;
  events?: string[]; commissionCents?: number; award?: string | null; drawCount?: number; dealerNatural?: boolean;
  [key: string]: unknown;
}
export interface CasinoSession {
  id: string; game: string; option: string; variant: string; rulesVersion: number; version: number;
  stake: number; stakeCents: number; totalCommittedCents: number; assetType: string; assetLabel: string;
  status: "active" | "settled"; createdAt: string; view: CasinoView;
  result: { status: "win" | "loss" | "push"; multiplier: number; label: string; outcome: Record<string, unknown>; returnCents: number; committedCents: number; netCents: number; balanceCents?: number; lines: SettlementLine[] } | null;
}
export interface WorldData {
  inventory: InventoryItem[]; game: GameSummary; preferences: Preferences; activeSession: CasinoSession | null;
  manifest: CasinoVariant[];
  trophies: { id: string; gameId: number; milestone: number; name: string; at: string }[];
  losses: { id: string; game: string; description: string; snapshot: Record<string, unknown>; at: string }[];
  rounds: { id: string; game: string; option: string; variant: string; stake: number; stakeCents: number; returnCents: number; netCents: number; assetType: string; assetLabel: string; won: boolean; totalReturn: number; net: number; outcome: Record<string, unknown>; at: string }[];
  traderOffers: { key: string; name: string; kind: "collectible"; price: number; symbol: string; description: string }[];
}
