// Mystery collectible tiers. Odds are the same at every budget: spending more buys more draws, never better odds.
import { COLLECTIBLE_NAMES, COLLECTIBLE_SYMBOLS } from "./shop";

export const COLLECTIBLE_TIERS = [
  { name: "Common", weight: 5000, min: 50, max: 90 },
  { name: "Uncommon", weight: 2500, min: 100, max: 180 },
  { name: "Rare", weight: 1300, min: 250, max: 450 },
  { name: "Epic", weight: 700, min: 600, max: 1100 },
  { name: "Legendary", weight: 350, min: 1500, max: 3000 },
  { name: "Mythic", weight: 120, min: 4000, max: 8000 },
  { name: "Celestial", weight: 30, min: 12000, max: 30000 },
] as const;
export const TIER_WEIGHT_TOTAL = COLLECTIBLE_TIERS.reduce((s, t) => s + t.weight, 0);
export const MIN_BUDGET = 100;
export const MAX_BUDGET = 100_000;
export const MAX_ITEMS = 1000;

export interface DrawnCollectible { name: string; symbol: string; rarity: string; price: number; key: string }

/** rng(n) returns an integer in [0, n). Stops at the first draw that no longer fits the remaining budget. */
export function drawCollectibles(budget: number, rng: (n: number) => number): { items: DrawnCollectible[]; spent: number } {
  const items: DrawnCollectible[] = [];
  let remaining = budget, misses = 0;
  while (items.length < MAX_ITEMS && remaining >= COLLECTIBLE_TIERS[0].min) {
    let roll = rng(TIER_WEIGHT_TOTAL), tier: (typeof COLLECTIBLE_TIERS)[number] = COLLECTIBLE_TIERS[0];
    for (const t of COLLECTIBLE_TIERS) { if (roll < t.weight) { tier = t; break; } roll -= t.weight; }
    const price = tier.min + rng(tier.max - tier.min + 1);
    if (price > remaining) { if (items.length === 0 && misses++ < 100) continue; break; }
    remaining -= price;
    items.push({ name: `${tier.name} ${COLLECTIBLE_NAMES[rng(COLLECTIBLE_NAMES.length)]} ${100 + rng(900)}`, symbol: COLLECTIBLE_SYMBOLS[rng(COLLECTIBLE_SYMBOLS.length)]!, rarity: tier.name, price, key: `generated-${rng(1e9)}` });
  }
  return { items, spent: budget - remaining };
}
