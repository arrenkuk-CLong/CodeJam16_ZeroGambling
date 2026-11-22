// Shapes of the casino engine's cards and receipt lines. The engine itself runs on the server
// (ZeroGambling-backend/core/casino_engine.py); the browser only displays these.
export interface Card { r: number; s: number }
export interface BlackjackHand { cards: Card[]; stakeCents: number; fromSplit: boolean; splitAces: boolean; doubled: boolean; done: boolean; bust: boolean }
export interface SettlementLine { id: string; label: string; committedCents: number; returnCents: number; reason: string }
export interface Settlement {
  status: "win" | "loss" | "push"; multiplier: number; outcome: Record<string, unknown>; label: string;
  returnCents: number; committedCents: number; lines: SettlementLine[];
}
