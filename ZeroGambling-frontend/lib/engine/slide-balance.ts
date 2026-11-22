// TypeScript port of the slide game's balance model (slide_balance.py). Every number is kept as designed.
// Pure: shared by the server (run dealing, caps, pay) and the browser (shop/glider display).
// 1. reach(L) = 100 m * 10^((L-2)/18). 2. steer grows linearly 0.35 -> 1.9 half-widths/s from level -1 to 20.
// 3. The track tightens with distance: swerves are timed for the level whose reach is d / 1.1.
// 4. Checkpoints every 50 m; only the highest passed pays (50 m = 1 ... 1000 m = 20 gems).

export const REACH_L2_M = 100, REACH_L20_M = 1000, GLIDER_MAX_LEVEL = 20, NO_GLIDER_LEVEL = -1;
export const STEER_MAX = 1.9, STEER_NO_GLIDER = 0.35, STEER_CURVE = 1.0;
export const TRACK_M = 1000, SPEED_START = 10, SPEED_MAX = 20;
export const LANES = [-0.62, 0.0, 0.62] as const;
export const OBSTACLE_HALF = 0.26, BALL_R = 0.08, HIT_SCALE = 0.8;
export const HIT_R = OBSTACLE_HALF + BALL_R * HIT_SCALE;
export const WALL_U = 1 - BALL_R;
export const OBSTACLE_DEPTH_M = 1.2;
export const ROW_GAP_S: [number, number] = [0.5, 0.8];
export const FIRST_ROW_M = 30, CLEAR_FINISH_M = 25, P_SHIFT = 0.18, P_SWERVE = 0.4;
export const SWERVE_SHIFT = 2 * HIT_R, LANE_SHIFT = HIT_R, WALL_HEADROOM = 1.1, SWERVE_JITTER = 0.15;
export const STEER_FLOOR = 0.25, TOP_GLIDER_MARGIN = 0.97;
export const OBSTACLE_KINDS = ["cards", "token", "dice"] as const;
export const CHECKPOINT_EVERY_M = 50, CHECKPOINT_GEMS_PER_50M = 1, CHECKPOINT_EXP = 1.0;
export const RUNS_PER_UPGRADE_L0 = 3, RUNS_PER_UPGRADE_L19 = 6, GLIDER_PRICE = 30;
export const REWARDED_RUNS_PER_DAY = 3, RUN_EXPIRES_MIN = 20, REPORT_STEER_SLACK = 1.1;

export type Level = number | null;
export type ObstacleKind = (typeof OBSTACLE_KINDS)[number];
export interface Row { z: number; obstacles: { lane: number; kind: ObstacleKind }[] }

export function reachM(level: Level) { const L = level ?? NO_GLIDER_LEVEL; return REACH_L2_M * (REACH_L20_M / REACH_L2_M) ** ((L - 2) / 18); }
export function levelForReach(d: number) { return 2 + 18 * Math.log(Math.max(d, 1e-6) / REACH_L2_M) / Math.log(REACH_L20_M / REACH_L2_M); }
export function steer(level: Level) {
  const L = level ?? NO_GLIDER_LEVEL;
  const t = (L - NO_GLIDER_LEVEL) / (GLIDER_MAX_LEVEL - NO_GLIDER_LEVEL);
  return STEER_NO_GLIDER + (STEER_MAX - STEER_NO_GLIDER) * Math.sign(t) * Math.abs(t) ** STEER_CURVE;
}
export function steerPct(level: Level) { return Math.round((100 * steer(level)) / STEER_MAX); }
export function requiredSteer(d: number) { return Math.max(STEER_FLOOR, steer(levelForReach(d / WALL_HEADROOM))); }
export function speed(d: number) { return SPEED_START + (SPEED_MAX - SPEED_START) * Math.min(1, Math.max(0, d) / TRACK_M); }
export function minSeconds(distance: number, step = 5) { let s = 0; for (let d = 0; d < Math.trunc(distance); d += step) s += step / speed(d); return s; }
export function checkpointM(distance: number) { return Math.min(TRACK_M, Math.floor(Math.trunc(distance) / CHECKPOINT_EVERY_M) * CHECKPOINT_EVERY_M); }
export function checkpointGems(c: number) { return c < CHECKPOINT_EVERY_M ? 0 : Math.round(CHECKPOINT_GEMS_PER_50M * (c / CHECKPOINT_EVERY_M) ** CHECKPOINT_EXP); }
export function checkpoints() { const out = []; for (let c = CHECKPOINT_EVERY_M; c <= TRACK_M; c += CHECKPOINT_EVERY_M) out.push({ m: c, gems: checkpointGems(c) }); return out; }
export function expectedPayout(level: Level) { return CHECKPOINT_GEMS_PER_50M * (reachM(level) / CHECKPOINT_EVERY_M) ** CHECKPOINT_EXP; }
export function runsPerUpgrade(level: number) { const t = level / (GLIDER_MAX_LEVEL - 1); return RUNS_PER_UPGRADE_L0 * (RUNS_PER_UPGRADE_L19 / RUNS_PER_UPGRADE_L0) ** t; }
/** Python round() is banker's rounding; match it so costs equal the design table. */
function pyRound(x: number) { const f = Math.floor(x), d = x - f; if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1; return Math.round(x); }
export function upgradeCost(level: number) { let cost = 0; for (let l = 0; l <= level; l++) cost = Math.max(cost + 1, pyRound(runsPerUpgrade(l) * expectedPayout(l))); return cost; }
export function gliderInvested(level: number) { let s = GLIDER_PRICE; for (let l = 0; l < level; l++) s += upgradeCost(l); return s; }

export function safeGaps(blocked: number[], hit = HIT_R): [number, number][] {
  let safe: [number, number][] = [[-WALL_U, WALL_U]];
  for (const lane of blocked) {
    const c = LANES[lane]!; const out: [number, number][] = [];
    for (const [lo, hi] of safe) { if (lo < c - hit) out.push([lo, Math.min(hi, c - hit)]); if (hi > c + hit) out.push([Math.max(lo, c + hit), hi]); }
    safe = out;
  }
  return safe;
}

export type Rng = () => number;
export function mulberry(seed: number): Rng { let a = seed >>> 0; return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

/** Deals the obstacle rows for one run. Every row leaves a lane open; shifts and swerves get steering time. */
export function makeRows(rng: Rng): Row[] {
  const uniform = (a: number, b: number) => a + (b - a) * rng();
  const choice = <T,>(xs: readonly T[]) => xs[Math.floor(rng() * xs.length)]!;
  const rows: Row[] = []; const last = LANES.length - 1; const edges = [0, last];
  const others = (keep: number) => [0, 1, 2].filter((l) => l !== keep);
  const place = (zPrev: number, shift: number, blocked: number[]) => {
    const t = uniform(...ROW_GAP_S);
    let z = zPrev + speed(zPrev) * t;
    if (shift) {
      const demand = requiredSteer(zPrev) * uniform(1 - SWERVE_JITTER, 1 + SWERVE_JITTER);
      const need = shift / Math.min(demand, STEER_MAX * TOP_GLIDER_MARGIN);
      z = Math.max(z, zPrev + speed(zPrev) * need + 2 * OBSTACLE_DEPTH_M);
    }
    rows.push({ z: Math.round(z * 100) / 100, obstacles: [...blocked].sort((a, b) => a - b).map((lane) => ({ lane, kind: choice(OBSTACLE_KINDS) })) });
    return z;
  };
  let z = FIRST_ROW_M - speed(0) * ROW_GAP_S[0], safeLane = 1; const end = TRACK_M - CLEAR_FINISH_M;
  for (;;) {
    const r = rng(); let next: number; let plan: [number, number[]];
    if (edges.includes(safeLane) && r < P_SWERVE) {
      next = last - safeLane;
      z = place(z, 0, others(safeLane));
      plan = [SWERVE_SHIFT, others(next)];
    } else if (r < P_SWERVE + P_SHIFT) {
      next = edges.includes(safeLane) ? 1 : safeLane + choice([-1, 1]);
      const third = others(next).filter((l) => l !== safeLane);
      plan = [LANE_SHIFT, [safeLane, ...(rng() < 0.5 ? third : [])]];
    } else {
      next = safeLane; const free = others(safeLane);
      plan = [0, rng() < 0.45 ? free : [choice(free)]];
    }
    if (z >= end) break;
    z = place(z, plan[0], plan[1]);
    safeLane = next;
    if (z >= end) { rows.pop(); break; }
  }
  return rows.filter((row) => row.z < end);
}

function merge(iv: [number, number][]) {
  const out: [number, number][] = [];
  for (const [lo, hi] of [...iv].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
    const top = out[out.length - 1];
    if (top && lo <= top[1] + 1e-9) top[1] = Math.max(top[1], hi); else out.push([lo, hi]);
  }
  return out;
}

/** How far a flawless player with this steering can get through these rows. */
export function perfectReach(rows: Row[], steerSpeed: number): number {
  let reach: [number, number][] = [[0, 0]]; let lastZ = 0;
  for (const row of rows) {
    const z = row.z;
    const freeT = Math.max(0, z - OBSTACLE_DEPTH_M - lastZ) / speed((z + lastZ) / 2);
    const grow = steerSpeed * freeT;
    reach = merge(reach.map(([lo, hi]) => [Math.max(-WALL_U, lo - grow), Math.min(WALL_U, hi + grow)]));
    const safe = safeGaps(row.obstacles.map((o) => o.lane));
    const inside: [number, number][] = [];
    for (const [lo, hi] of reach) for (const [slo, shi] of safe) if (Math.max(lo, slo) <= Math.min(hi, shi)) inside.push([Math.max(lo, slo), Math.min(hi, shi)]);
    if (!inside.length) return Math.max(0, z - OBSTACLE_DEPTH_M);
    const win = (steerSpeed * (2 * OBSTACLE_DEPTH_M)) / speed(z);
    const next: [number, number][] = [];
    for (const [lo, hi] of inside) for (const [slo, shi] of safe) if (slo <= lo && hi <= shi) next.push([Math.max(slo, lo - win), Math.min(shi, hi + win)]);
    reach = merge(next);
    lastZ = z + OBSTACLE_DEPTH_M;
  }
  return TRACK_M;
}
