"""Fixed demo catalog: exactly 19 active challenges. ID 9 is permanently retracted.
Mirrors ZeroGambling-frontend/lib/catalog.ts (the browser shows the same list)."""

RETRACTED_IDS = (9,)

CATALOG = [
    {"id": 1, "name": "Mental math chains", "group": "logic"},
    {"id": 2, "name": "Pattern completion", "group": "logic"},
    {"id": 3, "name": "Cipher decoding", "group": "logic"},
    {"id": 4, "name": "Wordle-style", "group": "logic"},
    {"id": 5, "name": "Vocabulary", "group": "logic"},
    {"id": 6, "name": "Typing gauntlet", "group": "logic"},
    {"id": 7, "name": "Mastermind", "group": "logic"},
    {"id": 8, "name": "Lights Out", "group": "logic"},
    {"id": 10, "name": "Base conversion / units", "group": "logic"},
    {"id": 11, "name": "Sequence memory", "group": "memory"},
    {"id": 12, "name": "Mental rotation", "group": "memory"},
    {"id": 13, "name": "Odd-one-out (color)", "group": "memory"},
    {"id": 14, "name": "Dot count", "group": "perception"},
    {"id": 15, "name": "Trajectory landing", "group": "perception"},
    {"id": 16, "name": "Angle matching", "group": "perception"},
    {"id": 17, "name": "Tempo keeping", "group": "perception"},
    {"id": 18, "name": "Line splitting", "group": "perception"},
    {"id": 19, "name": "Time estimation", "group": "perception"},
    {"id": 20, "name": "Pitch matching", "group": "perception"},
]

ACTIVE_IDS = [g["id"] for g in CATALOG]


def get_entry(game_id):
    if game_id in RETRACTED_IDS:
        return None
    return next((g for g in CATALOG if g["id"] == game_id), None)


def band_for(level: int) -> dict:
    if level < 10:
        return {"name": "Depth only", "maxModifiers": 0}
    if level < 25:
        return {"name": "One modifier", "maxModifiers": 1}
    if level < 40:
        return {"name": "Up to two modifiers", "maxModifiers": 2}
    return {"name": "Chained modifiers", "maxModifiers": 3}
