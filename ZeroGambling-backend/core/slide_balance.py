"""Slide game balance: every number that decides how far you get, what you earn and what upgrades cost.
Pure Python (no Django), so it can be printed, tested and tuned on its own:

    python manage.py slide_table            # the tuning table below, recomputed from these numbers

THE MODEL (four linked curves; change a constant and everything downstream follows)

1. Target reach. The distance an average player should reach with a glider level L:
       reach(L) = REACH_L2 * (REACH_L20 / REACH_L2) ** ((L - 2) / 18)
   100 m at level 2, 1000 m at level 20, growing by the same factor (~13.6%) every level.
   No glider counts as level -1 (about 68 m).

2. Steering. Your glider only changes how fast the ball moves left and right (track half-widths/s):
       steer(L) = STEER_NO_GLIDER + (STEER_MAX - STEER_NO_GLIDER) * ((L + 1) / 21) ** STEER_CURVE
   Level 20 is the old default (1.9/s); no glider is very slow (0.35/s, ~3.7 s to cross the track).

3. The track tightens with distance. Rows of obstacles come every ROW_GAP_S seconds and always leave a
   lane open. Now and then the open lane jumps from one edge to the other (a "swerve"). At distance d a
   swerve gives you just enough time for the steering of the level whose target reach is d / WALL_HEADROOM:
       swerve time(d) = SWERVE_SHIFT / steer(level whose reach(L) = d / WALL_HEADROOM)   (+-SWERVE_JITTER)
   So a level-L glider can make every swerve up to about reach(L) * WALL_HEADROOM and then, sooner or
   later, meets one it physically can't make. Mistakes before that wall pull the average down to about
   reach(L); lucky gaps (SWERVE_JITTER) and clean play push individual runs past it.

4. Money. Checkpoints sit every 50 m up to the 1000 m finish. Only the highest one you passed pays:
       checkpoint_gems(c) = round(CHECKPOINT_GEMS_PER_50M * (c / 50) ** CHECKPOINT_EXP)    (50 m = 1 ... 1000 m = 20)
   Upgrades are priced in "runs at your current level":
       upgrade_cost(L -> L+1) = round(runs(L) * expected_payout(L))
       expected_payout(L) = checkpoint_gems(reach(L)), runs(L) goes from RUNS_PER_UPGRADE_L0 to _L19
   Reach grows ~13.6% per level and pay is linear in distance, so costs grow ~13.6% per level plus the
   slow rise in runs(L): a steady exponential curve, always increasing. Beating your expected distance
   pays proportionally more (mastery), but never more than the 1000 m checkpoint.
"""
import math
import random

# ---------- 1. target reach ----------
REACH_L2_M = 100
REACH_L20_M = 1000
GLIDER_MAX_LEVEL = 20
NO_GLIDER_LEVEL = -1          # no glider plays like level -1

# ---------- 2. steering ----------
STEER_MAX = 1.9               # level 20 (the old default)
STEER_NO_GLIDER = 0.35
STEER_CURVE = 1.0             # 1 = same gain every level; >1 = slow start, big late gains

# ---------- 3. track ----------
TRACK_M = 1000                # finish line = last checkpoint
SPEED_START = 10              # m/s; speed rises linearly to SPEED_MAX at TRACK_M
SPEED_MAX = 20
LANES = (-0.62, 0.0, 0.62)    # lane centres in track half-widths (-1 left edge, 1 right edge)
OBSTACLE_HALF = 0.26          # obstacle half-width (3.25x the ball)
BALL_R = 0.08                 # ball radius; the client draws it at this size
HIT_SCALE = 0.8               # collisions use 80% of the ball, so grazes feel fair
HIT_R = OBSTACLE_HALF + BALL_R * HIT_SCALE   # 0.324: closer than this to an obstacle's centre = crash
WALL_U = 1 - BALL_R           # the ball can't go further out than this
OBSTACLE_DEPTH_M = 1.2        # an obstacle can hit you within this many metres of its row
ROW_GAP_S = (0.5, 0.8)        # ordinary rows: this many seconds apart (was 1.1-1.8 s)
FIRST_ROW_M = 30
CLEAR_FINISH_M = 25           # no obstacles right before the finish
P_SHIFT = 0.18                # chance a row moves the open lane by one lane
P_SWERVE = 0.4                # chance (when the open lane is at an edge) of a swerve to the other edge
SWERVE_SHIFT = 2 * HIT_R      # how far a perfect player must move in a swerve (0.648)
LANE_SHIFT = HIT_R            # how far a one-lane shift asks you to move
WALL_HEADROOM = 1.1           # swerves become impossible at 1.1x your level's target reach
SWERVE_JITTER = 0.15          # each swerve is up to 15% easier or harder than the curve
STEER_FLOOR = 0.25            # the first metres never ask for less than this (everyone makes them)
TOP_GLIDER_MARGIN = 0.97      # no swerve ever needs more than 97% of level 20's steering, so a flawless
                              # level-20 run always finishes
OBSTACLE_KINDS = ("cards", "token", "dice")

# ---------- 4. money ----------
CHECKPOINT_EVERY_M = 50
CHECKPOINT_GEMS_PER_50M = 1
CHECKPOINT_EXP = 1.0          # 1 = pay grows in step with distance; <1 flattens the top, >1 rewards mastery more
RUNS_PER_UPGRADE_L0 = 3       # one day of rewarded runs at the cap
RUNS_PER_UPGRADE_L19 = 6      # two days for the last upgrade
GLIDER_PRICE = 30             # buying the glider (level 0); the shop catalogue reads this
REWARDED_RUNS_PER_DAY = 3     # only the first 3 paying runs each day pay
RUN_EXPIRES_MIN = 20          # an unreported run stops counting after this
REPORT_STEER_SLACK = 1.1      # a reported distance is capped at what a flawless player steering 10% faster
                              # than the glider could reach, so frame timing never costs a real player


# ---------- curves ----------
def reach_m(level):
    """Target average reach for a glider level (None = no glider)."""
    L = NO_GLIDER_LEVEL if level is None else level
    return REACH_L2_M * (REACH_L20_M / REACH_L2_M) ** ((L - 2) / 18)


def level_for_reach(d):
    """Inverse of reach_m: the (fractional) level whose target reach is d."""
    return 2 + 18 * math.log(max(d, 1e-6) / REACH_L2_M) / math.log(REACH_L20_M / REACH_L2_M)


def steer(level):
    """Steering speed in track half-widths per second (None = no glider)."""
    L = NO_GLIDER_LEVEL if level is None else level
    t = (L - NO_GLIDER_LEVEL) / (GLIDER_MAX_LEVEL - NO_GLIDER_LEVEL)
    return STEER_NO_GLIDER + (STEER_MAX - STEER_NO_GLIDER) * math.copysign(abs(t) ** STEER_CURVE, t)


def required_steer(d):
    """Steering a swerve at distance d is built for (before jitter)."""
    return max(STEER_FLOOR, steer(level_for_reach(d / WALL_HEADROOM)))


def speed(d):
    return SPEED_START + (SPEED_MAX - SPEED_START) * min(1.0, max(0.0, d) / TRACK_M)


def min_seconds(distance_m, step=5):
    """Fastest possible time to cover distance_m (used to reject impossible reports)."""
    return sum(step / speed(d) for d in range(0, int(distance_m), step))


def checkpoint_m(distance_m):
    """Highest checkpoint passed (0 = none)."""
    return min(TRACK_M, int(distance_m) // CHECKPOINT_EVERY_M * CHECKPOINT_EVERY_M)


def checkpoint_gems(c):
    """Gems for ending a run with checkpoint c as your highest. Below 50 m pays nothing."""
    if c < CHECKPOINT_EVERY_M:
        return 0
    return round(CHECKPOINT_GEMS_PER_50M * (c / CHECKPOINT_EVERY_M) ** CHECKPOINT_EXP)


def checkpoints():
    return [{"m": c, "gems": checkpoint_gems(c)} for c in range(CHECKPOINT_EVERY_M, TRACK_M + 1, CHECKPOINT_EVERY_M)]


def expected_payout(level):
    """Pay for reaching exactly your target reach, on the continuous curve (used to price upgrades)."""
    return CHECKPOINT_GEMS_PER_50M * (reach_m(level) / CHECKPOINT_EVERY_M) ** CHECKPOINT_EXP


def runs_per_upgrade(level):
    t = level / (GLIDER_MAX_LEVEL - 1)
    return RUNS_PER_UPGRADE_L0 * (RUNS_PER_UPGRADE_L19 / RUNS_PER_UPGRADE_L0) ** t


def upgrade_cost(level):
    """Gems to go from `level` to `level + 1`: runs_per_upgrade(level) runs at the expected pay for the level,
    and always at least 1 gem more than the previous upgrade (so the curve strictly rises)."""
    cost = 0
    for l in range(level + 1):
        cost = max(cost + 1, round(runs_per_upgrade(l) * expected_payout(l)))
    return cost


def glider_invested(level):
    """Shop price plus every upgrade paid so far (trades and casino stakes use this)."""
    return GLIDER_PRICE + sum(upgrade_cost(l) for l in range(level))


# ---------- runs ----------
def safe_gaps(blocked_lanes, hit=HIT_R):
    """Positions (list of (lo, hi)) where the ball clears a row that blocks these lane indexes."""
    safe = [(-WALL_U, WALL_U)]
    for lane in blocked_lanes:
        c, out = LANES[lane], []
        for lo, hi in safe:
            if lo < c - hit:
                out.append((lo, min(hi, c - hit)))
            if hi > c + hit:
                out.append((max(lo, c + hit), hi))
        safe = out
    return safe


def make_rows(rng=None):
    """Deals the obstacle rows for one run. Every row leaves at least one lane open. The open lane only
    moves at shifts and swerves, and the gap before those rows is timed by required_steer there."""
    rng = rng or random.Random()
    rows, edges, last = [], (0, len(LANES) - 1), len(LANES) - 1
    others = lambda keep: [l for l in range(len(LANES)) if l != keep]

    def place(z_prev, shift, blocked):
        """Puts the next row after z_prev; a row that moves the open lane gets time to steer there."""
        t = rng.uniform(*ROW_GAP_S)
        z = z_prev + speed(z_prev) * t
        if shift:
            demand = required_steer(z_prev) * rng.uniform(1 - SWERVE_JITTER, 1 + SWERVE_JITTER)
            need = shift / min(demand, STEER_MAX * TOP_GLIDER_MARGIN)
            z = max(z, z_prev + speed(z_prev) * need + 2 * OBSTACLE_DEPTH_M)
        rows.append({"z": round(z, 2), "obstacles": [{"lane": l, "kind": rng.choice(OBSTACLE_KINDS)}
                                                     for l in sorted(blocked)]})
        return z

    z, safe_lane, end = FIRST_ROW_M - speed(0) * ROW_GAP_S[0], 1, TRACK_M - CLEAR_FINISH_M
    while True:
        r = rng.random()
        if safe_lane in edges and r < P_SWERVE:
            new = last - safe_lane  # swerve: only this edge open, then only the other edge
            z = place(z, 0, others(safe_lane))
            plan = (SWERVE_SHIFT, others(new))
        elif r < P_SWERVE + P_SHIFT:
            new = 1 if safe_lane in edges else safe_lane + rng.choice((-1, 1))
            third = [l for l in others(new) if l != safe_lane]
            plan = (LANE_SHIFT, [safe_lane] + (third if rng.random() < 0.5 else []))
        else:
            new, free = safe_lane, others(safe_lane)
            plan = (0, free if rng.random() < 0.45 else [rng.choice(free)])
        if z >= end:
            break
        z = place(z, *plan)
        safe_lane = new
        if z >= end:
            rows.pop()
            break
    return [r for r in rows if r["z"] < end]


def perfect_reach(rows, steer_speed):
    """How far a flawless player with this steering can get: the distance of the first row they
    physically can't clear (or TRACK_M)."""
    hit = HIT_R
    reach = [(0.0, 0.0)]  # positions the ball can be at
    last_z = 0.0

    for row in rows:
        z = row["z"]
        free_t = max(0.0, (z - OBSTACLE_DEPTH_M) - last_z) / speed((z + last_z) / 2)
        grow = steer_speed * free_t
        reach = _merge([(max(-WALL_U, lo - grow), min(WALL_U, hi + grow)) for lo, hi in reach])
        safe = safe_gaps([ob["lane"] for ob in row["obstacles"]], hit)
        inside = [(max(lo, slo), min(hi, shi)) for lo, hi in reach for slo, shi in safe if max(lo, slo) <= min(hi, shi)]
        if not inside:
            return max(0.0, z - OBSTACLE_DEPTH_M)
        # while passing the row you can still slide inside its gap
        win = steer_speed * (2 * OBSTACLE_DEPTH_M) / speed(z)
        reach = _merge([(max(slo, lo - win), min(shi, hi + win)) for lo, hi in inside
                        for slo, shi in safe if slo <= lo and hi <= shi])
        last_z = z + OBSTACLE_DEPTH_M
    return float(TRACK_M)


def _merge(iv):
    iv = sorted(iv)
    out = []
    for lo, hi in iv:
        if out and lo <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def table(samples=300, seed=1):
    """One row per glider level: steering, target reach, simulated perfect-play reach, pay and cost."""
    rng = random.Random(seed)
    runs = [make_rows(rng) for _ in range(samples)]
    out = []
    for level in [None] + list(range(GLIDER_MAX_LEVEL + 1)):
        s = steer(level)
        reaches = sorted(perfect_reach(r, s) for r in runs)
        cp = checkpoint_m(reach_m(level))
        out.append({
            "level": level, "steer": s, "reach": reach_m(level),
            "perfect_median": reaches[len(reaches) // 2], "perfect_p10": reaches[len(reaches) // 10],
            "perfect_p90": reaches[len(reaches) * 9 // 10],
            "expected_checkpoint": cp, "expected_gems": checkpoint_gems(cp),
            "upgrade_cost": None if level is None or level >= GLIDER_MAX_LEVEL else upgrade_cost(level),
            "runs_to_upgrade": None if level is None or level >= GLIDER_MAX_LEVEL else runs_per_upgrade(level),
            "invested": GLIDER_PRICE if level is None else glider_invested(level),
        })
    return out
