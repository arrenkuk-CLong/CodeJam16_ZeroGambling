// Browser-safe, versioned casino manifest. The server returns this exact manifest to the UI.
export type CasinoGameId = "roulette" | "blackjack" | "slots" | "baccarat" | "crash" | "sixdraw" | "poker";
export interface Ratio { num: number; den: number }
export interface CasinoOption {
  id: string; label: string; p: number; profitMultiplier: number; pushP?: number; evOverride?: number;
  covered?: string[]; profitRatio?: Ratio; probabilityLabel?: string;
}
export interface CasinoVariant {
  game: CasinoGameId; id: string; name: string; rulesVersion: number; rules: string;
  stakeStepCents: number; exposureLimitCents: number; assetStakes: boolean;
  options: CasinoOption[]; probabilityNote?: string;
}
export interface CasinoGame { id: CasinoGameId; name: string; rules: string; options: CasinoOption[] }

export const REDS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
export const WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
export const AMERICAN_WHEEL_ORDER = [0, 28, 9, 26, 30, 11, 7, 20, 32, 17, 5, 22, 34, 15, 3, 24, 36, 13, 1, 37, 27, 10, 25, 29, 12, 8, 19, 31, 18, 6, 21, 33, 16, 4, 23, 35, 14, 2];
export const SLOT_SYMBOLS = ["A", "B", "C", "D", "E"];
export const CLASSIC_SLOT_GROSS = [12, 16, 20, 30, 40];
export const JACKS_PAYTABLE = [
  { id: "royal", label: "Royal flush", gross: 800 }, { id: "straight-flush", label: "Other straight flush", gross: 50 },
  { id: "quads", label: "Four of a kind", gross: 25 }, { id: "full-house", label: "Full house", gross: 9 },
  { id: "flush", label: "Flush", gross: 6 }, { id: "straight", label: "Straight", gross: 4 },
  { id: "trips", label: "Three of a kind", gross: 3 }, { id: "two-pair", label: "Two pair", gross: 2 },
  { id: "high-pair", label: "Pair J/Q/K/A", gross: 1 },
];
export const CRASH_CAP_CENTS = 10_000;
export const CASINO_RULES_VERSION = 2;

const exposureLimitCents = 100_000;
const ratio = (num: number, den = 1): Ratio => ({ num, den });
const option = (id: string, label: string, p: number, profitMultiplier: number, extra: Partial<CasinoOption> = {}): CasinoOption => ({ id, label, p, profitMultiplier, ...extra });

export function rouletteBets(variant: string): CasinoOption[] {
  const american = variant === "american";
  const french = variant === "french";
  const size = american ? 38 : 37;
  const bets: CasinoOption[] = [];
  const add = (id: string, label: string, covered: ReadonlyArray<number | string>, profit: number) => {
    const pockets = covered.map(String);
    bets.push(option(id, label, pockets.length / size, profit, {
      covered: pockets, profitRatio: ratio(profit), probabilityLabel: `${pockets.length}/${size}`,
    }));
  };
  for (const n of american ? ["0", "00", ...Array.from({ length: 36 }, (_, i) => i + 1)] : [0, ...Array.from({ length: 36 }, (_, i) => i + 1)]) add(`straight:${n}`, `Straight ${n}`, [n], 35);
  if (american) add("topline", "Top line · 0/00/1/2/3", [0, "00", 1, 2, 3], 6);
  else {
    for (const n of [1, 2, 3]) add(`split:0-${n}`, `Split 0/${n}`, [0, n], 17);
    add("trio:0-1-2", "Trio 0/1/2", [0, 1, 2], 11);
    add("trio:0-2-3", "Trio 0/2/3", [0, 2, 3], 11);
    add("firstfour", "First four · 0/1/2/3", [0, 1, 2, 3], 8);
  }
  for (let street = 1; street <= 34; street += 3) {
    add(`street:${street}`, `Street ${street}–${street + 2}`, [street, street + 1, street + 2], 11);
    for (const offset of [0, 1]) {
      const a = street + offset;
      add(`split:${a}-${a + 1}`, `Split ${a}/${a + 1}`, [a, a + 1], 17);
      if (street <= 31) add(`corner:${a}`, `Corner ${a}/${a + 1}/${a + 3}/${a + 4}`, [a, a + 1, a + 3, a + 4], 8);
    }
    if (street <= 31) add(`sixline:${street}`, `Six line ${street}–${street + 5}`, Array.from({ length: 6 }, (_, i) => street + i), 5);
    for (let n = street; n <= street + 2; n++) if (n + 3 <= 36) add(`split:${n}-${n + 3}`, `Split ${n}/${n + 3}`, [n, n + 3], 17);
  }
  for (let d = 0; d < 3; d++) add(`dozen${d + 1}`, `${["1st", "2nd", "3rd"][d]} dozen · ${d * 12 + 1}–${d * 12 + 12}`, Array.from({ length: 12 }, (_, i) => d * 12 + i + 1), 2);
  for (let c = 1; c <= 3; c++) add(`column${c}`, `Column ${c}`, Array.from({ length: 12 }, (_, i) => i * 3 + c), 2);
  const evenMoney = [
    ["red", "Red", [...REDS]], ["black", "Black", Array.from({ length: 36 }, (_, i) => i + 1).filter((n) => !REDS.has(n))],
    ["even", "Even", Array.from({ length: 18 }, (_, i) => (i + 1) * 2)], ["odd", "Odd", Array.from({ length: 18 }, (_, i) => i * 2 + 1)],
    ["low", "Low · 1–18", Array.from({ length: 18 }, (_, i) => i + 1)], ["high", "High · 19–36", Array.from({ length: 18 }, (_, i) => i + 19)],
  ] as const;
  for (const [id, label, covered] of evenMoney) add(id, french ? `${label} · la partage` : label, covered, 1);
  return bets;
}

const rouletteDefaults = [
  option("red", "Red", 18 / 37, 1), option("black", "Black", 18 / 37, 1),
  option("even", "Even", 18 / 37, 1), option("odd", "Odd", 18 / 37, 1),
  option("dozen1", "1st dozen", 12 / 37, 2), option("straight17", "Straight 17", 1 / 37, 35),
];

export const CASINO_VARIANTS: CasinoVariant[] = [
  { game: "roulette", id: "european", name: "European", rulesVersion: 2, rules: "37 equally likely pockets. Full inside and outside tickets; zero loses outside bets.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: rouletteDefaults, probabilityNote: "Standard tickets: RTP 97.297%, house edge 2.703%." },
  { game: "roulette", id: "american", name: "American", rulesVersion: 2, rules: "38 pockets with 0 and 00, ordinary grid bets and the 0/00/1/2/3 top line.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: rouletteDefaults.map((o) => ({ ...o, p: o.id.startsWith("straight") ? 1 / 38 : o.id.startsWith("dozen") ? 12 / 38 : 18 / 38 })), probabilityNote: "Standard edge 5.263%; top-line edge 7.895%." },
  { game: "roulette", id: "french", name: "French · la partage", rulesVersion: 2, rules: "European wheel. Zero returns half of each even-money ticket; other tickets follow European rules.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: rouletteDefaults, probabilityNote: "Even-money edge 1.351%; other standard tickets 2.703%." },
  { game: "blackjack", id: "simple", name: "Simple", rulesVersion: 2, rules: "Six decks, US hole card and peek, dealer stands on all 17s, natural pays 3:2. Hit or stand only.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: [option("standard", "Hit / stand", 0.43, 1, { pushP: 0.09, evOverride: -0.01 })], probabilityNote: "Decision-dependent RTP; no verified strategy estimate is claimed." },
  { game: "blackjack", id: "classic", name: "Classic", rulesVersion: 2, rules: "Insurance, double on any first two cards, split equal ranks up to four hands, one card on split aces. No surrender.", stakeStepCents: 2, exposureLimitCents, assetStakes: false, options: [option("standard", "Full classic rules", 0.43, 1, { pushP: 0.09, evOverride: -0.01 })], probabilityNote: "Decision-dependent RTP; no verified strategy estimate is claimed." },
  { game: "slots", id: "prototype", name: "Prototype line", rulesVersion: 2, rules: "Three independent A–E reels. Any matching center triple pays 20× gross.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: [option("three", "Center line · any triple", 1 / 25, 19, { profitRatio: ratio(19) })], probabilityNote: "Hit frequency 4%; RTP 80%." },
  { game: "slots", id: "classic", name: "Classic lines", rulesVersion: 2, rules: "Play one or three horizontal lines. AAA–EEE pay 12×, 16×, 20×, 30× or 40× gross per line.", stakeStepCents: 1, exposureLimitCents, assetStakes: false, options: [option("three", "Per-line paytable", 1 / 25, 19, { evOverride: -0.056 })], probabilityNote: "Each line RTP 94.4%; hit frequency 4%. Three-line wins are correlated." },
  { game: "baccarat", id: "commission", name: "Commission", rulesVersion: 2, rules: "Eight-deck Punto Banco. Banker profit 0.95:1, Player 1:1, Tie 8:1; Player and Banker push on ties.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: [option("banker", "Banker · 5% commission", 0.458597, 0.95, { pushP: 0.095156, profitRatio: ratio(19, 20) }), option("player", "Player", 0.446247, 1, { pushP: 0.095156, profitRatio: ratio(1) }), option("tie", "Tie · 8:1", 0.095156, 8, { profitRatio: ratio(8) })] },
  { game: "baccarat", id: "no-commission", name: "No commission · Banker six", rulesVersion: 2, rules: "Banker pays 1:2 profit when its winning final total is six, otherwise 1:1. Player and Tie are unchanged.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: [option("banker", "Banker · six pays half", 0.458597, 1, { pushP: 0.095156, profitRatio: ratio(1) }), option("player", "Player", 0.446247, 1, { pushP: 0.095156, profitRatio: ratio(1) }), option("tie", "Tie · 8:1", 0.095156, 8, { profitRatio: ratio(8) })], probabilityNote: "Approximate edges: Player 1.235%, Banker 1.46%, Tie 14.36%." },
  { game: "crash", id: "auto", name: "Auto", rulesVersion: 2, rules: "Precommit a 1.01×–100.00× target. Exact discrete 97% model; the private crash point is fixed at commit.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: [option("1.5", "1.50×", 0.97 / 1.5, 0.5), option("2", "2.00×", 0.97 / 2, 1), option("5", "5.00×", 0.97 / 5, 4)], probabilityNote: "Target stake must pay exactly to the cent." },
  { game: "crash", id: "live", name: "Live", rulesVersion: 2, rules: "Cash out manually from 1.01× or arm an optional auto target. Server ticks every 25 ms; returns round down to cents.", stakeStepCents: 1, exposureLimitCents, assetStakes: false, options: [option("live", "Manual cash-out", 0.5, 1, { evOverride: -0.03 })], probabilityNote: "Nominal 97% return before cent rounding; actual cash-out amount is shown live." },
  { game: "sixdraw", id: "classic", name: "Classic · three safe", rulesVersion: 2, rules: "Reveal three distinct safe tiles to earn 1.80× gross. One uniformly placed trap; no early banking.", stakeStepCents: 5, exposureLimitCents, assetStakes: true, options: [option("survive", "Three safe reveals", 0.5, 0.8, { profitRatio: ratio(4, 5) })], probabilityNote: "Original survival chance 50%; house edge 10%." },
  { game: "sixdraw", id: "target", name: "Target draw", rulesVersion: 2, rules: "Commit to 1–5 safe reveals. Gross return is 0.90 divided by the original survival probability.", stakeStepCents: 5, exposureLimitCents, assetStakes: true, options: [1, 2, 3, 4, 5].map((k) => option(String(k), `${k} safe · ${(0.9 / ((6 - k) / 6)).toFixed(2)}×`, (6 - k) / 6, 0.9 / ((6 - k) / 6) - 1)), probabilityNote: "Every target has a 10% house edge before exact-cent stake requirements." },
  { game: "poker", id: "showdown", name: "Dealer showdown", rulesVersion: 2, rules: "Five-card draw against the dealer bot. Win pays 0.8:1; exact ties push. Dealer follows a published hold rule.", stakeStepCents: 5, exposureLimitCents, assetStakes: true, options: [option("ante", "Beat the dealer", 0.45, 0.8, { pushP: 0.05, profitRatio: ratio(4, 5) })], probabilityNote: "Strategy-dependent RTP; no house-edge claim is made." },
  { game: "poker", id: "jacks", name: "9/6 Jacks or Better", rulesVersion: 2, rules: "Single-player video poker with an 800× royal at every stake. Only the highest qualifying category pays.", stakeStepCents: 1, exposureLimitCents, assetStakes: true, options: [option("ante", "Full-pay 9/6 table", 0.45, 1, { evOverride: -0.0046 })], probabilityNote: "About 99.54% RTP with optimal play; actual returns depend on holds." },
];

export const CASINO_GAMES: CasinoGame[] = ["roulette", "blackjack", "slots", "baccarat", "crash", "sixdraw", "poker"].map((id) => {
  const variant = CASINO_VARIANTS.find((v) => v.game === id)!;
  return { id: id as CasinoGameId, name: id === "sixdraw" ? "Six-Slot Draw" : id === "poker" ? "Five-Card Draw" : id[0]!.toUpperCase() + id.slice(1), rules: variant.rules, options: variant.options };
});

export function casinoVariant(game: string, id: string): CasinoVariant | undefined { return CASINO_VARIANTS.find((v) => v.game === game && v.id === id); }
export function findOption(game: string, optionId: string) { const g = CASINO_GAMES.find((x) => x.id === game); return g ? g.options.find((o) => o.id === optionId) : undefined; }
export function expectedValue(o: CasinoOption): number { if (o.evOverride !== undefined) return o.evOverride; return o.p * o.profitMultiplier - (1 - o.p - (o.pushP ?? 0)); }
export function rouletteWins(optionId: string, n: number): boolean {
  const normalized = optionId.startsWith("straight") ? optionId.replace(/^straight(?::)?/, "") : optionId;
  if (optionId.startsWith("straight")) return String(n) === normalized;
  const bet = rouletteBets("european").find((o) => o.id === optionId);
  return bet?.covered?.includes(String(n)) ?? false;
}
export function formatCents(cents: number): string { return `${cents < 0 ? "-" : ""}${Math.floor(Math.abs(cents) / 100)}.${String(Math.abs(cents) % 100).padStart(2, "0")}`; }
export function parseCents(value: string): number | null {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(cents) ? cents : null;
}
export function exactRatio(stakeCents: number, r: Ratio): number { return Math.floor((stakeCents * r.num) / r.den); }
export function crashTargetStep(target: number): number { const gcd = (a: number, b: number): number => b ? gcd(b, a % b) : a; return 100 / gcd(100, target); }
export const SIX_DRAW_STEPS = [25, 20, 5, 10, 5];
