export interface ShopProduct {
  key: string;
  name: string;
  kind: "equipment" | "collectible";
  price: number;
  description: string;
  symbol: string;
}

import { GLIDER_PRICE } from "./engine/slide-balance";

export const EQUIPMENT: ShopProduct[] = [
  // Price comes from the slide balance model (GLIDER_PRICE). Starts at level 0; upgrade up to level 20.
  { key: "glider", name: "Glider", kind: "equipment", price: GLIDER_PRICE, symbol: "△", description: "Steers the slide ball faster. Upgrade it level by level for more steering and a longer expected reach." },
];

export const COLLECTIBLE_NAMES = ["Prism", "Relic", "Orbit", "Totem", "Cipher", "Comet", "Monolith", "Bloom"];
export const COLLECTIBLE_SYMBOLS = ["◈", "✦", "⬡", "◉", "✧", "▣"];
export const RARITIES = [
  { name: "Uncommon", multiplier: 1 },
  { name: "Rare", multiplier: 1.5 },
  { name: "Mythic", multiplier: 2.5 },
] as const;

export const TRADER_OFFERS: ShopProduct[] = [
  { key: "alex-orbit", name: "Alex's Copper Orbit", kind: "collectible", price: 120, symbol: "◉", description: "A patient little solar system." },
  { key: "alex-prism", name: "Alex's Violet Prism", kind: "collectible", price: 240, symbol: "◈", description: "A faceted light study, one of one." },
  { key: "alex-relic", name: "Alex's Ancient Relic", kind: "collectible", price: 480, symbol: "⬡", description: "A mysterious artifact from the demo vault." },
];
