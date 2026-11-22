// Casino, shop, slide and preference server functions, answered by Django (ZeroGambling-backend/core/views.py).
// Same names and inputs as Lovable's createServerFn versions, so the pages call them unchanged.
import { serverFn } from "./api";
import type { AssetInput, CasinoSession, Preferences, RunResult, SlideRun, WorldData } from "./world-types";

type Token = { token: string };
type Request = Token & { requestId: string };
/** An inventory row as the server stores it. */
export interface ItemRow { id: string; kind: "equipment" | "collectible"; item_key: string; name: string; price: number; symbol: string; metadata: { description?: string; rarity?: string }; level: number; acquired_from: string; created_at: string }
export interface StartConfig { variant?: string; tickets?: { betId: string; stakeCents: number }[]; lines?: 1 | 3; target?: number; autoTarget?: number | null }
type WagerAction = "hit" | "stand" | "double" | "split" | "insurance" | "declineInsurance" | "draw" | "reveal" | "cashout" | "tick" | (string & {});

export const getWorld = serverFn<Token & { demo?: boolean }, WorldData>("world");
export const startWager = serverFn<Request & { game: "roulette" | "blackjack" | "slots" | "baccarat" | "crash" | "sixdraw" | "poker"; option: string; asset: AssetInput; config?: StartConfig }, CasinoSession>("casino/start");
export const actOnWager = serverFn<Request & { sessionId: string; action: WagerAction; holds?: number[]; tile?: number; insuranceCents?: number }, CasinoSession>("casino/act");
export const buyProduct = serverFn<Request & { productKey: string }, ItemRow>("shop/buy");
export const buyCollectibles = serverFn<Request & { budget: number }, { spent: number; budget: number; items: (ItemRow & { metadata: { rarity: string } })[] }>("shop/collectibles");
export const tradeItem = serverFn<Request & { itemId: string; offerKey: string }, ItemRow>("shop/trade");
export const startSlideRun = serverFn<Request, SlideRun>("slide/start");
export const finishSlideRun = serverFn<Token & { runId: string; result: "survived" | "crashed"; distanceM: number }, RunResult>("slide/finish");
export const upgradeGlider = serverFn<Request, { level: number }>("slide/glider/upgrade");
export const savePreferences = serverFn<Token & { preferences: Preferences }, Preferences>("preferences");
