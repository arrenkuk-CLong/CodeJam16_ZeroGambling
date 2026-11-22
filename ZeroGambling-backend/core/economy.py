"""Versioned payout rules and asset valuation (port of engine/economy.ts and economy-assets.ts).
Every gem minted by a challenge goes through compute_reward. Non-gem assets have a payout estimate,
never a cash-out or sell-back path."""
from . import slide_balance as sb
from .jscompat import js_round

ECONOMY_VERSION = 1
ECONOMY = {
    "basePerLevel": 2,
    "baseFlat": 5,
    "rebuildRate": 0.5,  # playtest setting: passing a level below your peak pays half
    "hintRate": 0.5,
    "repeatDecayPerRun": 0.15,  # per same-game pass in the last hour
    "repeatFloor": 0.4,
    "repeatWindowMinutes": 60,
    "failXp": 2,
}


# How hard each challenge is compared with the others. Harder games pay more per pass; this multiplies on top of
# the level-based base pay, so climbing levels inside one game still raises pay the same way.
GAME_DIFFICULTY = {
    # hard: multi-step reasoning or fine motor/audio skill
    1: "hard", 3: "hard", 7: "hard", 8: "hard", 12: "hard", 17: "hard", 20: "hard",
    # medium
    2: "medium", 4: "medium", 10: "medium", 11: "medium", 15: "medium", 16: "medium", 19: "medium",
    # easy: quick perception or recall
    5: "easy", 6: "easy", 13: "easy", 14: "easy", 18: "easy",
}
DIFFICULTY_FACTOR = {"easy": 1.0, "medium": 1.25, "hard": 1.5}

# Speed bonus: a typical solve time (seconds at level 1, growing with level). Solving in half of it pays ×1.5,
# within it ×1.25. Games whose length is fixed by the stimulus (sequence memory, trajectory, tempo, time
# estimation, pitch) have no speed bonus, since finishing early isn't possible or isn't the skill.
SPEED_PAR_SEC = {1: 45, 2: 60, 3: 120, 4: 120, 5: 60, 6: 90, 7: 150, 8: 90, 10: 45, 12: 45, 13: 30, 14: 20, 16: 30, 18: 30}


def speed_par(game_id, level):
    par = SPEED_PAR_SEC.get(game_id)
    return None if par is None else par * (1 + level / 40)


class UserError(Exception):
    """A rule the player broke; the message is shown to them as-is."""


def compute_reward(passed, is_void, level, peak_before, hints, recent_same_game_passes, repeated_task, game_id=None, elapsed_sec=None) -> dict:
    if is_void:
        return {"economyVersion": ECONOMY_VERSION, "base": 0, "lines": [{"label": "Run voided", "factor": 0}], "gems": 0, "xp": 0}
    if not passed:
        return {"economyVersion": ECONOMY_VERSION, "base": 0, "lines": [{"label": "Not passed", "factor": 0}], "gems": 0, "xp": ECONOMY["failXp"]}
    base = ECONOMY["baseFlat"] + ECONOMY["basePerLevel"] * level
    lines = []
    if repeated_task:
        lines.append({"label": "Previously rewarded puzzle", "factor": 0})
    if level < peak_before:
        lines.append({"label": f"Rebuilding below peak level {peak_before}", "factor": ECONOMY["rebuildRate"]})
    if hints > 0:
        lines.append({"label": "Hint used", "factor": ECONOMY["hintRate"]})
    if recent_same_game_passes > 0:
        f = max(ECONOMY["repeatFloor"], 1 - ECONOMY["repeatDecayPerRun"] * recent_same_game_passes)
        lines.append({"label": f"Same game ×{recent_same_game_passes + 1} this hour (rotate to restore)", "factor": js_round(f * 100) / 100})
    tier = GAME_DIFFICULTY.get(game_id)
    if tier and DIFFICULTY_FACTOR[tier] != 1:
        lines.append({"label": f"{tier.capitalize()} game", "factor": DIFFICULTY_FACTOR[tier]})
    par = speed_par(game_id, level)
    if par is not None and elapsed_sec is not None and elapsed_sec >= 0:
        if elapsed_sec <= par / 2:
            lines.append({"label": f"Fast solve ({round(elapsed_sec)} s)", "factor": 1.5})
        elif elapsed_sec <= par:
            lines.append({"label": f"Quick solve ({round(elapsed_sec)} s)", "factor": 1.25})
    value = base
    for line in lines:
        value *= line["factor"]
    return {"economyVersion": ECONOMY_VERSION, "base": base, "lines": lines, "gems": js_round(value), "xp": 10 + level}


def band_floor(peak: int) -> int:
    """Difficulty floor: failing can't drop you below the start of your peak's band."""
    return 40 if peak >= 40 else 25 if peak >= 25 else 10 if peak >= 10 else 1


def next_level(level: int, peak: int, passed: bool, is_void: bool) -> int:
    if is_void:
        return level
    return level + 1 if passed else max(band_floor(peak), level - 1)


# ---- asset valuation: V(p) = B(0.5p + 0.5p²) ----
def skill_base(level: int) -> int:
    if level >= 40:
        return 200
    if level >= 25:
        return 100
    if level >= 10:
        return 50
    return 20


def skill_percent(level: int) -> float:
    return max(0, min(0.99, (level - 1) / 10))


def skill_value(level: int, base=None) -> float:
    b = skill_base(level) if base is None else base
    p = skill_percent(level)
    return b * (0.5 * p + 0.5 * p * p)


def skill_stake_value(level: int, rollback_level: int) -> int:
    if rollback_level < 1 or rollback_level >= level:
        return 0
    return max(1, js_round(skill_value(level) - skill_value(rollback_level, skill_base(level))))


def equipment_stake_value(shop_price) -> int:
    return max(1, int(shop_price * 0.5 // 1))


def glider_stake_value(level: int, levels: int) -> int:
    """Staking n glider levels: worth half of what those levels cost (same 50% rule as equipment)."""
    if levels < 1 or levels > level:
        return 0
    return equipment_stake_value(sb.glider_invested(level) - sb.glider_invested(level - levels))


def log_stake_value(levels, journal_entries: int) -> int:
    skills = sum(skill_stake_value(level, 1) for level in levels)
    return skills + min(50, max(0, journal_entries))
