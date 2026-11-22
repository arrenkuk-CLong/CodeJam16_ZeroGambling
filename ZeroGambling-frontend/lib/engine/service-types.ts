// The player summary the server returns (ZeroGambling-backend/core/services.py: player_summary).
export interface Summary {
  player: { id: string; name: string; gems: number; gemCents: number; isDemo: boolean; createdAt: string; lifetimePasses: number };
  mastery: { gameId: number; level: number; peak: number; best: number; plays: number; passes: number; xp: number }[];
  completions: { id: string; gameId: number; level: number; score: number; passed: boolean; xp: number; gems: number; newLevel: number; at: string }[];
  ledger: { id: string; delta: number; balance: number; deltaCents: number; balanceCents: number; reason: string; at: string }[];
  rounds: { id: string; game: string; option: string; stake: number; won: boolean; totalReturn: number; net: number; at: string }[];
}
