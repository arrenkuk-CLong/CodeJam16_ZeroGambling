"""Versioned casino manifest and exact-cent helpers (port of lib/casino.ts). The browser keeps an identical
copy in ZeroGambling-frontend/lib/casino.ts for display; the server is authoritative for every settlement."""
import math
import re

from .jscompat import to_fixed

REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
AMERICAN_WHEEL_ORDER = [0, 28, 9, 26, 30, 11, 7, 20, 32, 17, 5, 22, 34, 15, 3, 24, 36, 13, 1, 37, 27, 10, 25, 29, 12, 8, 19, 31, 18, 6, 21, 33, 16, 4, 23, 35, 14, 2]
SLOT_SYMBOLS = ["A", "B", "C", "D", "E"]
CLASSIC_SLOT_GROSS = [12, 16, 20, 30, 40]
JACKS_PAYTABLE = [
    {"id": "royal", "label": "Royal flush", "gross": 800}, {"id": "straight-flush", "label": "Other straight flush", "gross": 50},
    {"id": "quads", "label": "Four of a kind", "gross": 25}, {"id": "full-house", "label": "Full house", "gross": 9},
    {"id": "flush", "label": "Flush", "gross": 6}, {"id": "straight", "label": "Straight", "gross": 4},
    {"id": "trips", "label": "Three of a kind", "gross": 3}, {"id": "two-pair", "label": "Two pair", "gross": 2},
    {"id": "high-pair", "label": "Pair J/Q/K/A", "gross": 1},
]
CRASH_CAP_CENTS = 10_000
CASINO_RULES_VERSION = 2
EXPOSURE_LIMIT_CENTS = 100_000
SIX_DRAW_STEPS = [25, 20, 5, 10, 5]
EVEN_MONEY = ("red", "black", "even", "odd", "low", "high")
GAME_IDS = ["roulette", "blackjack", "slots", "baccarat", "crash", "sixdraw", "poker"]
DEFAULT_VARIANT = {"roulette": "european", "blackjack": "simple", "slots": "prototype", "baccarat": "commission",
                   "crash": "auto", "sixdraw": "classic", "poker": "showdown"}


def ratio(num, den=1):
    return {"num": num, "den": den}


def option(id_, label, p, profit, **extra):
    return {"id": id_, "label": label, "p": p, "profitMultiplier": profit, **extra}


def roulette_bets(variant: str) -> list:
    american = variant == "american"
    french = variant == "french"
    size = 38 if american else 37
    bets = []

    def add(id_, label, covered, profit):
        pockets = [str(c) for c in covered]
        bets.append(option(id_, label, len(pockets) / size, profit, covered=pockets, profitRatio=ratio(profit), probabilityLabel=f"{len(pockets)}/{size}"))

    numbers = (["0", "00"] if american else [0]) + list(range(1, 37))
    for n in numbers:
        add(f"straight:{n}", f"Straight {n}", [n], 35)
    if american:
        add("topline", "Top line · 0/00/1/2/3", [0, "00", 1, 2, 3], 6)
    else:
        for n in (1, 2, 3):
            add(f"split:0-{n}", f"Split 0/{n}", [0, n], 17)
        add("trio:0-1-2", "Trio 0/1/2", [0, 1, 2], 11)
        add("trio:0-2-3", "Trio 0/2/3", [0, 2, 3], 11)
        add("firstfour", "First four · 0/1/2/3", [0, 1, 2, 3], 8)
    for street in range(1, 35, 3):
        add(f"street:{street}", f"Street {street}–{street + 2}", [street, street + 1, street + 2], 11)
        for offset in (0, 1):
            a = street + offset
            add(f"split:{a}-{a + 1}", f"Split {a}/{a + 1}", [a, a + 1], 17)
            if street <= 31:
                add(f"corner:{a}", f"Corner {a}/{a + 1}/{a + 3}/{a + 4}", [a, a + 1, a + 3, a + 4], 8)
        if street <= 31:
            add(f"sixline:{street}", f"Six line {street}–{street + 5}", [street + i for i in range(6)], 5)
        for n in range(street, street + 3):
            if n + 3 <= 36:
                add(f"split:{n}-{n + 3}", f"Split {n}/{n + 3}", [n, n + 3], 17)
    for d in range(3):
        add(f"dozen{d + 1}", f"{['1st', '2nd', '3rd'][d]} dozen · {d * 12 + 1}–{d * 12 + 12}", [d * 12 + i + 1 for i in range(12)], 2)
    for c in range(1, 4):
        add(f"column{c}", f"Column {c}", [i * 3 + c for i in range(12)], 2)
    even_money = [
        ("red", "Red", sorted(REDS)), ("black", "Black", [n for n in range(1, 37) if n not in REDS]),
        ("even", "Even", [(i + 1) * 2 for i in range(18)]), ("odd", "Odd", [i * 2 + 1 for i in range(18)]),
        ("low", "Low · 1–18", list(range(1, 19))), ("high", "High · 19–36", list(range(19, 37))),
    ]
    for id_, label, covered in even_money:
        add(id_, f"{label} · la partage" if french else label, covered, 1)
    return bets


_ROULETTE_DEFAULTS = [
    option("red", "Red", 18 / 37, 1), option("black", "Black", 18 / 37, 1),
    option("even", "Even", 18 / 37, 1), option("odd", "Odd", 18 / 37, 1),
    option("dozen1", "1st dozen", 12 / 37, 2), option("straight17", "Straight 17", 1 / 37, 35),
]


def _american_p(o):
    return 1 / 38 if o["id"].startswith("straight") else 12 / 38 if o["id"].startswith("dozen") else 18 / 38


def _variant(game, id_, name, rules, step, asset_stakes, options, note=None):
    v = {"game": game, "id": id_, "name": name, "rulesVersion": 2, "rules": rules, "stakeStepCents": step,
         "exposureLimitCents": EXPOSURE_LIMIT_CENTS, "assetStakes": asset_stakes, "options": options}
    if note is not None:
        v["probabilityNote"] = note
    return v


CASINO_VARIANTS = [
    _variant("roulette", "european", "European", "37 equally likely pockets. Full inside and outside tickets; zero loses outside bets.", 1, True,
             _ROULETTE_DEFAULTS, "Standard tickets: RTP 97.297%, house edge 2.703%."),
    _variant("roulette", "american", "American", "38 pockets with 0 and 00, ordinary grid bets and the 0/00/1/2/3 top line.", 1, True,
             [{**o, "p": _american_p(o)} for o in _ROULETTE_DEFAULTS], "Standard edge 5.263%; top-line edge 7.895%."),
    _variant("roulette", "french", "French · la partage", "European wheel. Zero returns half of each even-money ticket; other tickets follow European rules.", 1, True,
             _ROULETTE_DEFAULTS, "Even-money edge 1.351%; other standard tickets 2.703%."),
    _variant("blackjack", "simple", "Simple", "Six decks, US hole card and peek, dealer stands on all 17s, natural pays 3:2. Hit or stand only.", 1, True,
             [option("standard", "Hit / stand", 0.43, 1, pushP=0.09, evOverride=-0.01)], "Decision-dependent RTP; no verified strategy estimate is claimed."),
    _variant("blackjack", "classic", "Classic", "Insurance, double on any first two cards, split equal ranks up to four hands, one card on split aces. No surrender.", 2, False,
             [option("standard", "Full classic rules", 0.43, 1, pushP=0.09, evOverride=-0.01)], "Decision-dependent RTP; no verified strategy estimate is claimed."),
    _variant("slots", "prototype", "Prototype line", "Three independent A–E reels. Any matching center triple pays 20× gross.", 1, True,
             [option("three", "Center line · any triple", 1 / 25, 19, profitRatio=ratio(19))], "Hit frequency 4%; RTP 80%."),
    _variant("slots", "classic", "Classic lines", "Play one or three horizontal lines. AAA–EEE pay 12×, 16×, 20×, 30× or 40× gross per line.", 1, False,
             [option("three", "Per-line paytable", 1 / 25, 19, evOverride=-0.056)], "Each line RTP 94.4%; hit frequency 4%. Three-line wins are correlated."),
    _variant("baccarat", "commission", "Commission", "Eight-deck Punto Banco. Banker profit 0.95:1, Player 1:1, Tie 8:1; Player and Banker push on ties.", 1, True,
             [option("banker", "Banker · 5% commission", 0.458597, 0.95, pushP=0.095156, profitRatio=ratio(19, 20)),
              option("player", "Player", 0.446247, 1, pushP=0.095156, profitRatio=ratio(1)),
              option("tie", "Tie · 8:1", 0.095156, 8, profitRatio=ratio(8))]),
    _variant("baccarat", "no-commission", "No commission · Banker six", "Banker pays 1:2 profit when its winning final total is six, otherwise 1:1. Player and Tie are unchanged.", 1, True,
             [option("banker", "Banker · six pays half", 0.458597, 1, pushP=0.095156, profitRatio=ratio(1)),
              option("player", "Player", 0.446247, 1, pushP=0.095156, profitRatio=ratio(1)),
              option("tie", "Tie · 8:1", 0.095156, 8, profitRatio=ratio(8))], "Approximate edges: Player 1.235%, Banker 1.46%, Tie 14.36%."),
    _variant("crash", "auto", "Auto", "Precommit a 1.01×–100.00× target. Exact discrete 97% model; the private crash point is fixed at commit.", 1, True,
             [option("1.5", "1.50×", 0.97 / 1.5, 0.5), option("2", "2.00×", 0.97 / 2, 1), option("5", "5.00×", 0.97 / 5, 4)], "Target stake must pay exactly to the cent."),
    _variant("crash", "live", "Live", "Cash out manually from 1.01× or arm an optional auto target. Server ticks every 25 ms; returns round down to cents.", 1, False,
             [option("live", "Manual cash-out", 0.5, 1, evOverride=-0.03)], "Nominal 97% return before cent rounding; actual cash-out amount is shown live."),
    _variant("sixdraw", "classic", "Classic · three safe", "Reveal three distinct safe tiles to earn 1.80× gross. One uniformly placed trap; no early banking.", 5, True,
             [option("survive", "Three safe reveals", 0.5, 0.8, profitRatio=ratio(4, 5))], "Original survival chance 50%; house edge 10%."),
    _variant("sixdraw", "target", "Target draw", "Commit to 1–5 safe reveals. Gross return is 0.90 divided by the original survival probability.", 5, True,
             [option(str(k), f"{k} safe · {to_fixed(0.9 / ((6 - k) / 6), 2)}×", (6 - k) / 6, 0.9 / ((6 - k) / 6) - 1) for k in range(1, 6)],
             "Every target has a 10% house edge before exact-cent stake requirements."),
    _variant("poker", "showdown", "Dealer showdown", "Five-card draw against the dealer bot. Win pays 0.8:1; exact ties push. Dealer follows a published hold rule.", 5, True,
             [option("ante", "Beat the dealer", 0.45, 0.8, pushP=0.05, profitRatio=ratio(4, 5))], "Strategy-dependent RTP; no house-edge claim is made."),
    _variant("poker", "jacks", "9/6 Jacks or Better", "Single-player video poker with an 800× royal at every stake. Only the highest qualifying category pays.", 1, True,
             [option("ante", "Full-pay 9/6 table", 0.45, 1, evOverride=-0.0046)], "About 99.54% RTP with optimal play; actual returns depend on holds."),
]


def _game_name(id_):
    return "Six-Slot Draw" if id_ == "sixdraw" else "Five-Card Draw" if id_ == "poker" else id_[0].upper() + id_[1:]


CASINO_GAMES = []
for _g in GAME_IDS:
    _v = next(v for v in CASINO_VARIANTS if v["game"] == _g)
    CASINO_GAMES.append({"id": _g, "name": _game_name(_g), "rules": _v["rules"], "options": _v["options"]})


def casino_variant(game, id_):
    return next((v for v in CASINO_VARIANTS if v["game"] == game and v["id"] == id_), None)


def find_option(game, option_id):
    g = next((x for x in CASINO_GAMES if x["id"] == game), None)
    return next((o for o in g["options"] if o["id"] == option_id), None) if g else None


def expected_value(o) -> float:
    if "evOverride" in o:
        return o["evOverride"]
    return o["p"] * o["profitMultiplier"] - (1 - o["p"] - o.get("pushP", 0))


def roulette_wins(option_id: str, n: int) -> bool:
    if option_id.startswith("straight"):
        return str(n) == re.sub(r"^straight(?::)?", "", option_id)
    bet = next((o for o in roulette_bets("european") if o["id"] == option_id), None)
    return bool(bet) and str(n) in bet["covered"]


def format_cents(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


_MONEY = re.compile(r"^\d+(?:\.\d{1,2})?$", re.ASCII)


def parse_cents(value):
    if not isinstance(value, str) or not _MONEY.match(value):
        return None
    whole, _, fraction = value.partition(".")
    cents = int(whole) * 100 + int(fraction.ljust(2, "0") or "0")
    return cents if cents <= 2 ** 53 - 1 else None


def crash_target_step(target: int) -> int:
    return 100 // math.gcd(100, target)
