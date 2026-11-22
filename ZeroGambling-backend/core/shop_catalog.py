"""Shop products, Trader Alex's offers and the mystery-collectible draw (port of lib/shop.ts and
lib/collectibles.ts). Odds are the same at every budget: spending more buys more draws, never better odds."""
from . import slide_balance as sb

EQUIPMENT = [
    # Price comes from the slide balance model (GLIDER_PRICE). Starts at level 0; upgrade up to level 20.
    {"key": "glider", "name": "Glider", "kind": "equipment", "price": sb.GLIDER_PRICE, "symbol": "△",
     "description": "Steers the slide ball faster. Upgrade it level by level for more steering and a longer expected reach."},
]

COLLECTIBLE_NAMES = ["Prism", "Relic", "Orbit", "Totem", "Cipher", "Comet", "Monolith", "Bloom"]
COLLECTIBLE_SYMBOLS = ["◈", "✦", "⬡", "◉", "✧", "▣"]
RARITIES = [{"name": "Uncommon", "multiplier": 1}, {"name": "Rare", "multiplier": 1.5}, {"name": "Mythic", "multiplier": 2.5}]

TRADER_OFFERS = [
    {"key": "alex-orbit", "name": "Alex's Copper Orbit", "kind": "collectible", "price": 120, "symbol": "◉", "description": "A patient little solar system."},
    {"key": "alex-prism", "name": "Alex's Violet Prism", "kind": "collectible", "price": 240, "symbol": "◈", "description": "A faceted light study, one of one."},
    {"key": "alex-relic", "name": "Alex's Ancient Relic", "kind": "collectible", "price": 480, "symbol": "⬡", "description": "A mysterious artifact from the demo vault."},
]

COLLECTIBLE_TIERS = [
    {"name": "Common", "weight": 5000, "min": 50, "max": 90},
    {"name": "Uncommon", "weight": 2500, "min": 100, "max": 180},
    {"name": "Rare", "weight": 1300, "min": 250, "max": 450},
    {"name": "Epic", "weight": 700, "min": 600, "max": 1100},
    {"name": "Legendary", "weight": 350, "min": 1500, "max": 3000},
    {"name": "Mythic", "weight": 120, "min": 4000, "max": 8000},
    {"name": "Celestial", "weight": 30, "min": 12000, "max": 30000},
]
TIER_WEIGHT_TOTAL = sum(t["weight"] for t in COLLECTIBLE_TIERS)
MIN_BUDGET = 100
MAX_BUDGET = 100_000
MAX_ITEMS = 1000


def draw_collectibles(budget: int, rng):
    """rng(n) returns an integer in [0, n). Stops at the first draw that no longer fits the remaining budget."""
    items, remaining, misses = [], budget, 0
    while len(items) < MAX_ITEMS and remaining >= COLLECTIBLE_TIERS[0]["min"]:
        roll, tier = rng(TIER_WEIGHT_TOTAL), COLLECTIBLE_TIERS[0]
        for t in COLLECTIBLE_TIERS:
            if roll < t["weight"]:
                tier = t
                break
            roll -= t["weight"]
        price = tier["min"] + rng(tier["max"] - tier["min"] + 1)
        if price > remaining:
            if not items and misses < 100:
                misses += 1
                continue
            break
        remaining -= price
        items.append({"name": f"{tier['name']} {COLLECTIBLE_NAMES[rng(len(COLLECTIBLE_NAMES))]} {100 + rng(900)}",
                      "symbol": COLLECTIBLE_SYMBOLS[rng(len(COLLECTIBLE_SYMBOLS))], "rarity": tier["name"], "price": price,
                      "key": f"generated-{rng(10 ** 9)}"})
    return {"items": items, "spent": budget - remaining}
