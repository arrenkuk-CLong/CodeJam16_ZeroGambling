"""Server-authoritative casino engine (port of casino.server.ts). Private cards and crash thresholds never
leave this module. States and views are plain dicts with the same camelCase keys the browser reads."""
import secrets
import time
from datetime import datetime, timezone

from .casino_rules import (AMERICAN_WHEEL_ORDER, CLASSIC_SLOT_GROSS, CRASH_CAP_CENTS, DEFAULT_VARIANT, EVEN_MONEY,
                           JACKS_PAYTABLE, REDS, SIX_DRAW_STEPS, SLOT_SYMBOLS, casino_variant, crash_target_step,
                           roulette_bets)
from .jscompat import js_round, to_fixed


class EngineError(Exception):
    """A rule of the table was broken (shown to the player)."""


def now_ms() -> int:
    return int(time.time() * 1000)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rand_int(mx: int) -> int:
    if not isinstance(mx, int) or mx < 1 or mx > 0x1_0000_0000:
        raise EngineError("Invalid random bound")
    return secrets.randbelow(mx)


def shuffled_deck(decks=1):
    cards = [{"r": r, "s": s} for _ in range(decks) for s in range(4) for r in range(1, 14)]
    for i in range(len(cards) - 1, 0, -1):
        j = rand_int(i + 1)
        cards[i], cards[j] = cards[j], cards[i]
    return cards


def draw(cards):
    if not cards:
        raise EngineError("Deck exhausted")
    return cards.pop(0)


def card_value(c):
    return min(10, c["r"])


def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c["r"] == 1)
    soft = False
    while aces > 0 and total + 10 <= 21:
        total += 10
        aces -= 1
        soft = True
    return {"total": total, "soft": soft}


def baccarat_card_value(c):
    return 0 if c["r"] >= 10 else 1 if c["r"] == 1 else c["r"]


def baccarat_value(hand):
    return sum(baccarat_card_value(c) for c in hand) % 10


def gross(stake, profit):
    return stake + stake * profit["num"] // profit["den"]


def settlement(committed, lines, outcome, label):
    returned = sum(line["returnCents"] for line in lines)
    net = returned - committed
    return {"status": "win" if net > 0 else "loss" if net < 0 else "push",
            "multiplier": (returned - committed) / committed if committed else 0,
            "returnCents": returned, "committedCents": committed, "lines": lines, "outcome": outcome, "label": label}


def require_stake(stake, step, limit):
    if not isinstance(stake, int) or isinstance(stake, bool) or stake <= 0 or stake > limit or stake % step != 0:
        raise EngineError(f"Stake must use the {to_fixed(step / 100, 2)} step and stay within the table limit.")


def cap(s):
    return s[0].upper() + s[1:]


def line(id_, label, committed, returned, reason):
    return {"id": id_, "label": label, "committedCents": committed, "returnCents": returned, "reason": reason}


def active_view(state):
    if state.get("variant") == "live":
        return live_crash_view(state, now_ms())
    if state.get("hands") is not None:
        return blackjack_view(state, False)
    if state.get("trap") is not None:
        return six_draw_view(state, False)
    if state.get("phase") == "draw":
        return {"player": state.get("player"), "dealerCount": 5 if state.get("dealer") else 0, "phase": "draw", "variant": state.get("variant")}
    return {"phase": state.get("phase")}


# ---------- Roulette ----------
def start_roulette(o):
    variant = o.get("variant") or "european"
    stake = o.get("stakeCents", 500)
    tickets = o.get("tickets") or [{"betId": "red", "stakeCents": stake}]
    if not tickets or sum(t["stakeCents"] for t in tickets) != stake:
        raise EngineError("Roulette ticket amounts must add up to the total stake.")
    defs = {d["id"]: d for d in roulette_bets(variant)}
    lines = []
    # One server draw resolves every ticket on the table.
    pocket = str(AMERICAN_WHEEL_ORDER[rand_int(38)]).replace("37", "00") if variant == "american" else str(rand_int(37))
    for t in tickets:
        d = defs.get(t["betId"])
        if not d:
            raise EngineError("Unknown roulette ticket.")
        require_stake(t["stakeCents"], 2 if variant == "french" and d["id"] in EVEN_MONEY else 1, 100_000)
        won = pocket in d["covered"]
        partage = variant == "french" and pocket == "0" and d["id"] in EVEN_MONEY
        returned = t["stakeCents"] // 2 if partage else gross(t["stakeCents"], d["profitRatio"]) if won else 0
        reason = "Zero · la partage returns half" if partage else f"{pocket} is covered · {d['profitRatio']['num']}:1 profit" if won else f"{pocket} is not covered"
        lines.append(line(d["id"], d["label"], t["stakeCents"], returned, reason))
    numeric = 37 if pocket == "00" else int(pocket)
    color = "green" if numeric == 0 or pocket == "00" else "red" if numeric in REDS else "black"
    return {"state": {"variant": variant}, "settlement": settlement(stake, lines, {"number": pocket, "tickets": lines}, f"Pocket {pocket} · {color}")}


# ---------- Slots ----------
def start_slots(o):
    variant = o.get("variant") or "prototype"
    line_count = (o.get("lines") or 1) if variant == "classic" else 1
    stake = o.get("stakeCents", 500)
    require_stake(stake, line_count, 100_000)
    per_line = stake // line_count
    centers = [rand_int(5), rand_int(5), rand_int(5)]
    grid = [[SLOT_SYMBOLS[(c + offset + 5) % 5] for c in centers] for offset in (-1, 0, 1)]
    rows = [0, 1, 2] if line_count == 3 else [1]
    lines = []
    for row in rows:
        symbols = grid[row]
        matched = all(s == symbols[0] for s in symbols)
        multiplier = CLASSIC_SLOT_GROSS[SLOT_SYMBOLS.index(symbols[0])] if variant == "classic" else 20
        returned = per_line * multiplier if matched else 0
        lines.append(line(f"line{row + 1}", f"{['Top', 'Center', 'Bottom'][row]} line · {''.join(symbols)}", per_line, returned,
                          f"{symbols[0] * 3} pays {multiplier}× gross" if matched else "No matching triple"))
    label = "Matching line" if any(ln["returnCents"] > 0 for ln in lines) else "No matching line"
    return {"state": {"variant": variant}, "settlement": settlement(stake, lines, {"grid": grid, "reels": grid[1], "lineCount": line_count, "lines": lines}, label)}


# ---------- Baccarat ----------
def banker_draws(banker_total, player_third):
    if player_third is None:
        return banker_total <= 5
    return (banker_total <= 2 or (banker_total == 3 and player_third != 8) or (banker_total == 4 and 2 <= player_third <= 7)
            or (banker_total == 5 and 4 <= player_third <= 7) or (banker_total == 6 and player_third in (6, 7)))


def start_baccarat(o):
    variant = o.get("variant") or "commission"
    stake = o.get("stakeCents", 500)
    tickets = o.get("tickets") or [{"betId": "banker", "stakeCents": stake}]
    if sum(t["stakeCents"] for t in tickets) != stake:
        raise EngineError("Baccarat bet amounts must add up to the total stake.")
    for t in tickets:
        if t["betId"] not in ("banker", "player", "tie"):
            raise EngineError("Unknown baccarat bet.")
        require_stake(t["stakeCents"], (20 if variant == "commission" else 2) if t["betId"] == "banker" else 1, 100_000)
    cards = shuffled_deck(8)
    player, banker = [draw(cards)], [draw(cards)]
    player.append(draw(cards))
    banker.append(draw(cards))
    events = ["Initial deal: Player, Banker, Player, Banker."]
    p0, b0 = baccarat_value(player), baccarat_value(banker)
    if p0 >= 8 or b0 >= 8:
        events.append(f"Natural {max(p0, b0)}: both hands stand.")
    else:
        third = None
        if p0 <= 5:
            third = draw(cards)
            player.append(third)
            events.append(f"Player {p0}: draws {baccarat_card_value(third)}.")
        else:
            events.append(f"Player {p0}: stands.")
        third_value = baccarat_card_value(third) if third else None
        if banker_draws(b0, third_value):
            card = draw(cards)
            banker.append(card)
            events.append(f"Banker {b0}: tableau requires a draw ({baccarat_card_value(card)}).")
        else:
            events.append(f"Banker {b0}: tableau requires a stand.")
    pt, bt = baccarat_value(player), baccarat_value(banker)
    winner = "player" if pt > bt else "banker" if bt > pt else "tie"
    commission = 0
    lines = []
    for t in tickets:
        opt, bet = t["betId"], t["stakeCents"]
        returned = 0
        reason = f"{cap(winner)} wins."
        if winner == "tie" and opt != "tie":
            returned, reason = bet, "Tie: Player/Banker stake pushed."
        elif winner == opt:
            if opt == "tie":
                returned = bet * 9
            elif opt == "player":
                returned = bet * 2
            elif variant == "no-commission" and bt == 6:
                returned, reason = bet * 3 // 2, "Banker six: 1:2 profit."
            elif variant == "commission" and opt == "banker":
                returned = bet * 39 // 20
                c = -(-bet // 20)
                commission += c
                reason = f"Banker wins: 5% commission ({to_fixed(c / 100, 2)})."
            else:
                returned = bet * 2
        elif opt == "tie":
            reason = "Unequal totals: Tie loses."
        else:
            reason = f"{cap(winner)} wins: {opt} loses."
        lines.append(line(opt, f"{cap(opt)} wager", bet, returned, reason))
    outcome = {"player": player, "banker": banker, "playerTotal": pt, "bankerTotal": bt, "winner": winner, "events": events, "commissionCents": commission, "lines": lines}
    return {"state": {"variant": variant}, "settlement": settlement(stake, lines, outcome, f"{cap(winner)} · Player {pt}, Banker {bt}")}


# ---------- Blackjack ----------
def blackjack_view(state, settled):
    hands = state.get("hands")
    active = state.get("activeHand") or 0
    dealer = state.get("dealer")
    view = {"variant": state.get("variant"), "phase": state.get("phase"), "activeHand": active,
            "dealer": dealer if settled else (dealer[:1] if dealer is not None else None)}
    if settled and dealer:
        hv = hand_value(dealer)
        view["dealerTotal"], view["dealerSoft"] = hv["total"], hv["soft"]
    if hands is not None:
        view["hands"] = [{**h, **hand_value(h["cards"])} for h in hands]
    current = hands[active] if hands and 0 <= active < len(hands) else None
    view["player"] = current["cards"] if current else state.get("player")
    if current:
        view["playerTotal"] = hand_value(current["cards"])["total"]
    view["insuranceCents"] = state.get("insuranceCents") or 0
    return {k: v for k, v in view.items() if v is not None}


def natural(hand):
    return not hand["fromSplit"] and len(hand["cards"]) == 2 and hand_value(hand["cards"])["total"] == 21


def settle_blackjack(state, dealer_play, label=None):
    dealer = state["dealer"]
    if dealer_play:
        while hand_value(dealer)["total"] < 17:
            dealer.append(draw(state["deck"]))
    dealer_total = hand_value(dealer)["total"]
    dealer_natural = len(dealer) == 2 and dealer_total == 21
    lines = []
    for index, hand in enumerate(state.get("hands") or []):
        total = hand_value(hand["cards"])["total"]
        returned, reason = 0, ""
        if hand["bust"] or total > 21:
            reason = f"Bust at {total}."
        elif dealer_natural:
            returned = hand["stakeCents"] if natural(hand) else 0
            reason = "Both natural blackjack: push." if natural(hand) else "Dealer natural blackjack."
        elif natural(hand):
            returned, reason = hand["stakeCents"] * 5 // 2, "Natural blackjack pays 3:2."
        elif dealer_total > 21 or total > dealer_total:
            returned = hand["stakeCents"] * 2
            reason = f"Dealer busts at {dealer_total}." if dealer_total > 21 else f"{total} beats dealer {dealer_total}."
        elif total == dealer_total:
            returned, reason = hand["stakeCents"], f"Push at {total}."
        else:
            reason = f"Dealer {dealer_total} beats {total}."
        lines.append(line(f"hand{index + 1}", f"Hand {index + 1}", hand["stakeCents"], returned, reason))
    insurance = state.get("insuranceCents") or 0
    if insurance > 0:
        lines.append(line("insurance", "Insurance", insurance, insurance * 3 if dealer_natural else 0,
                          "Dealer natural: insurance pays 2:1 profit." if dealer_natural else "No dealer natural: insurance loses."))
    committed = sum(h["stakeCents"] for h in state.get("hands") or []) + insurance
    done = {**state, "dealer": dealer, "phase": "done"}
    view = {**blackjack_view(done, True), "dealerNatural": dealer_natural}
    default_label = "Dealer blackjack" if dealer_natural else f"Dealer busts at {dealer_total}" if dealer_total > 21 else f"Dealer {dealer_total}"
    result = settlement(committed, lines, {**view, "lines": lines}, label or default_label)
    return {"state": done, "settlement": result, "view": view}


def peek_blackjack(state):
    dealer_natural = len(state["dealer"]) == 2 and hand_value(state["dealer"])["total"] == 21
    player_natural = natural(state["hands"][0]) if state.get("hands") else False
    if dealer_natural or player_natural:
        label = "Both natural blackjack" if dealer_natural and player_natural else "Dealer natural blackjack" if dealer_natural else "Natural blackjack · pays 3:2"
        return settle_blackjack({**state, "phase": "done"}, False, label)
    nxt = {**state, "phase": "player"}
    return {"state": nxt, "view": blackjack_view(nxt, False)}


def start_blackjack(o):
    variant = o.get("variant") or "simple"
    stake = o.get("stakeCents", 500)
    require_stake(stake, 2 if variant == "classic" else 1, 100_000)
    deck = shuffled_deck(6)
    player, dealer = [draw(deck)], [draw(deck)]
    player.append(draw(deck))
    dealer.append(draw(deck))
    hand = {"cards": player, "stakeCents": stake, "fromSplit": False, "splitAces": False, "doubled": False, "done": False, "bust": False}
    state = {"variant": variant, "dealer": dealer, "deck": deck, "hands": [hand], "activeHand": 0,
             "phase": "insurance" if variant == "classic" and dealer[0]["r"] == 1 else "player", "insuranceCents": 0, "stakeCents": stake}
    if state["phase"] == "insurance":
        return {"state": state, "view": blackjack_view(state, False)}
    if dealer[0]["r"] == 1 or card_value(dealer[0]) == 10 or natural(hand):
        return peek_blackjack(state)
    return {"state": state, "view": blackjack_view(state, False)}


def advance_blackjack(state):
    hands = state["hands"]
    nxt = next((i for i, h in enumerate(hands) if not h["done"]), -1)
    if nxt < 0:
        return settle_blackjack({**state, "activeHand": 0, "phase": "dealer"}, any(not h["bust"] for h in hands))
    hand = hands[nxt]
    if len(hand["cards"]) == 1:
        hand["cards"].append(draw(state["deck"]))
    if hand["splitAces"] or hand_value(hand["cards"])["total"] == 21:
        hand["done"] = True
        return advance_blackjack({**state, "activeHand": nxt})
    s = {**state, "hands": hands, "activeHand": nxt, "phase": "player"}
    return {"state": s, "view": blackjack_view(s, False)}


def blackjack_action(state, action, payload=None):
    payload = payload or {}
    if state.get("phase") == "done":
        raise EngineError("Blackjack hand is already settled")
    if state.get("phase") == "insurance":
        if action == "insurance":
            amount = payload.get("insuranceCents") or 0
            mx = (state.get("stakeCents") or 0) // 2
            if not isinstance(amount, int) or amount < 1 or amount > mx:
                raise EngineError(f"Insurance must be between 0.01 and {to_fixed(mx / 100, 2)}.")
            state["insuranceCents"] = amount
            result = peek_blackjack({**state, "phase": "player"})
            return {**result, "additionalCents": amount}
        if action != "declineInsurance":
            raise EngineError("Take or decline insurance before playing.")
        return peek_blackjack({**state, "phase": "player"})
    if state.get("phase") != "player":
        raise EngineError("No blackjack action is currently available.")
    index = state.get("activeHand") or 0
    hands = state.get("hands") or []
    hand = hands[index] if index < len(hands) else None
    if not hand or hand["done"]:
        raise EngineError("This hand is already complete.")
    if action == "split":
        if state["variant"] != "classic" or len(hand["cards"]) != 2 or hand["cards"][0]["r"] != hand["cards"][1]["r"] or len(hands) >= 4 or hand["splitAces"]:
            raise EngineError("This hand cannot be split.")
        aces = hand["cards"][0]["r"] == 1
        first = {**hand, "cards": [hand["cards"][0]], "fromSplit": True, "splitAces": aces, "done": False}
        second = {**hand, "cards": [hand["cards"][1]], "fromSplit": True, "splitAces": aces, "done": False}
        hands[index:index + 1] = [first, second]
        advanced = advance_blackjack({**state, "activeHand": index})
        return {**advanced, "additionalCents": hand["stakeCents"]}
    if action == "double":
        if state["variant"] != "classic" or len(hand["cards"]) != 2 or hand["splitAces"]:
            raise EngineError("This hand cannot double.")
        extra = hand["stakeCents"]
        hand["stakeCents"] *= 2
        hand["doubled"] = True
        hand["cards"].append(draw(state["deck"]))
        hand["bust"] = hand_value(hand["cards"])["total"] > 21
        hand["done"] = True
        advanced = advance_blackjack({**state})
        return {**advanced, "additionalCents": extra}
    if action == "hit":
        hand["cards"].append(draw(state["deck"]))
        total = hand_value(hand["cards"])["total"]
        if total > 21:
            hand["bust"] = True
            hand["done"] = True
        if total == 21:
            hand["done"] = True
        if hand["done"]:
            return advance_blackjack({**state})
    elif action == "stand":
        hand["done"] = True
        return advance_blackjack({**state})
    else:
        raise EngineError("Choose a legal blackjack action.")
    s = {**state, "hands": hands, "phase": "player"}
    return {"state": s, "view": blackjack_view(s, False)}


# ---------- Crash ----------
TWO53 = 9_007_199_254_740_992


def crash_k_from_r(r: int) -> int:
    if r < 1 or r > TWO53:
        raise EngineError("Crash random value out of range")
    return min(10_000, (97 * TWO53) // r)


def random_crash_k() -> int:
    b = bytearray(secrets.token_bytes(7))
    b[0] &= 0x1F
    return crash_k_from_r(int.from_bytes(bytes(b), "big") + 1)


def crash_settlement(state, payable_tick, now):
    stake, k = state.get("stakeCents") or 0, state["crashK"]
    returned = 0 if payable_tick is None else stake * payable_tick // 100
    reason = (f"Crash at {to_fixed(k / 100, 2)}× · first failed tick {k + 1}, last payable {k}." if payable_tick is None
              else f"Cashed out at {to_fixed(payable_tick / 100, 2)}× · crash point {to_fixed(k / 100, 2)}×.")
    ln = line("crash", "Crash" if payable_tick is None else "Cash-out", stake, returned, reason)
    outcome = {"crashAt": k / 100, "crashHundredths": k, "lastPayableTick": k, "firstFailedTick": k + 1, "payableTick": payable_tick,
               "cashOutCents": returned, "receiptAt": iso(now), "autoTarget": state.get("autoTarget"), "lines": [ln]}
    label = f"Crashed at {to_fixed(k / 100, 2)}×" if payable_tick is None else f"{to_fixed(payable_tick / 100, 2)}× cash-out"
    return {"state": {**state, "phase": "done"}, "settlement": settlement(stake, [ln], outcome, label), "view": outcome}


def live_crash_view(state, now):
    launched = state.get("launchedAt") if state.get("launchedAt") is not None else now
    tick = max(0, (now - launched) // 25)
    multiplier = 100 + tick
    return {"phase": "live", "launchedAt": state.get("launchedAt"), "serverNow": now, "tick": tick, "multiplierCents": multiplier,
            "cashOutCents": (state.get("stakeCents") or 0) * multiplier // 100, "autoTarget": state.get("autoTarget"), "stakeCents": state.get("stakeCents")}


def start_crash(o):
    variant = o.get("variant") or "auto"
    stake = o.get("stakeCents", 500)
    now = o.get("now") or now_ms()
    target = o.get("target") or 200
    if not isinstance(target, int) or target < 101 or target > CRASH_CAP_CENTS:
        raise EngineError("Crash target must be 1.01×–100.00× in hundredth steps.")
    require_stake(stake, crash_target_step(target) if variant == "auto" else 1, 100_000)
    if variant == "auto" and stake % crash_target_step(target) != 0:
        raise EngineError("Stake does not pay this target exactly to the cent.")
    auto = o.get("autoTarget") if variant == "live" else target
    state = {"variant": variant, "crashK": random_crash_k(), "target": target, "launchedAt": now, "stakeCents": stake,
             "phase": "live" if variant == "live" else "done"}
    if auto is not None:
        state["autoTarget"] = auto
    if variant == "auto" or state["crashK"] < 101:
        payable = target if variant == "auto" and state["crashK"] >= target else None
        return crash_settlement({**state, "phase": "done"}, payable, now)
    return {"state": state, "view": live_crash_view(state, now)}


def crash_action(state, action, now):
    if state.get("variant") != "live" or state.get("phase") != "live":
        raise EngineError("Live crash round is already settled.")
    tick = max(0, (now - state["launchedAt"]) // 25)
    visible, k = 100 + tick, state["crashK"]
    crash_event_tick = k - 99
    auto = state.get("autoTarget")
    if auto and k >= auto and tick >= auto - 100:
        return crash_settlement({**state, "phase": "done"}, auto, now)
    if tick >= crash_event_tick:
        return crash_settlement({**state, "phase": "done"}, None, now)
    if action == "cashout":
        if visible < 101 or visible > k:
            raise EngineError("This cash-out tick is not payable.")
        return crash_settlement({**state, "phase": "done"}, visible, now)
    if action != "tick":
        raise EngineError("Choose cash-out or wait for the next tick.")
    return {"state": state, "view": live_crash_view(state, now)}


# ---------- Six-slot draw ----------
def six_draw_view(state, settled):
    draws = state.get("draws") or []
    safe, target = len(draws), state.get("target") or 3
    view = {"phase": "done" if settled else "draw", "draws": draws, "target": target, "progress": safe,
            "nextSafeChance": None if safe >= target else (5 - safe) / (6 - safe), "originalWinChance": (6 - target) / 6,
            "grossMultiplier": 0.9 / ((6 - target) / 6)}
    if settled:
        view["trap"] = state.get("trap")
    return view


def start_six_draw(o):
    variant = o.get("variant") or "classic"
    target = 3 if variant == "classic" else (3 if o.get("target") is None else o["target"])
    stake = o.get("stakeCents", 500)
    if not isinstance(target, int) or target < 1 or target > 5:
        raise EngineError("Choose a target from one to five safe reveals.")
    require_stake(stake, SIX_DRAW_STEPS[target - 1], 100_000)
    state = {"variant": variant, "trap": rand_int(6), "draws": [], "target": target, "stakeCents": stake, "phase": "draw"}
    return {"state": state, "view": six_draw_view(state, False)}


SIX_DRAW_RATIOS = [(27, 25), (27, 20), (9, 5), (27, 10), (27, 5)]  # 0.90 / ((6-k)/6) = 5.4/(6-k)


def six_draw_action(state, tile):
    if state.get("phase") != "draw":
        raise EngineError("This draw is already settled.")
    if not isinstance(tile, int) or isinstance(tile, bool) or tile < 0 or tile > 5:
        raise EngineError("Choose one of the six tiles.")
    if tile in (state.get("draws") or []):
        raise EngineError("That tile is already open.")
    draws = [*(state.get("draws") or []), tile]
    stake, target = state.get("stakeCents") or 0, state.get("target") or 3
    lost = tile == state["trap"]
    won = not lost and len(draws) >= target
    if not lost and not won:
        nxt = {**state, "draws": draws}
        return {"state": nxt, "view": six_draw_view(nxt, False)}
    num, den = SIX_DRAW_RATIOS[target - 1]
    gross_return = stake * num // den if won else 0
    ln = line("draw", f"{target} safe reveals", stake, gross_return,
              f"Tile {tile + 1} hid the trap after {len(draws) - 1} safe reveals." if lost else f"{target} safe reveals completed.")
    done = {**state, "draws": draws, "phase": "done"}
    return {"state": done, "settlement": settlement(stake, [ln], {**six_draw_view(done, True), "lines": [ln]}, "Trap revealed" if lost else f"{target} safe reveals"),
            "view": six_draw_view(done, True)}


# ---------- Poker ----------
def evaluate_poker(hand):
    if len(hand) != 5:
        raise EngineError("Poker evaluation requires five cards")
    ranks = sorted((14 if c["r"] == 1 else c["r"] for c in hand), reverse=True)
    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(counts.items(), key=lambda g: (-g[1], -g[0]))
    flush = all(c["s"] == hand[0]["s"] for c in hand)
    unique = list(dict.fromkeys(ranks))
    wheel = len(unique) == 5 and unique == [14, 5, 4, 3, 2]
    straight_high = 5 if wheel else unique[0] if len(unique) == 5 and all(i == 0 or unique[i - 1] - r == 1 for i, r in enumerate(unique)) else 0
    if straight_high and flush:
        return [8, straight_high]
    if groups[0][1] == 4:
        return [7, groups[0][0], groups[1][0]]
    if groups[0][1] == 3 and groups[1][1] == 2:
        return [6, groups[0][0], groups[1][0]]
    if flush:
        return [5, *ranks]
    if straight_high:
        return [4, straight_high]
    if groups[0][1] == 3:
        return [3, groups[0][0], *sorted((g[0] for g in groups[1:]), reverse=True)]
    if groups[0][1] == 2 and groups[1][1] == 2:
        return [2, groups[0][0], groups[1][0], groups[2][0]]
    if groups[0][1] == 2:
        return [1, groups[0][0], *sorted((g[0] for g in groups[1:]), reverse=True)]
    return [0, *ranks]


def compare_poker(a, b):
    av, bv = evaluate_poker(a), evaluate_poker(b)
    for i in range(max(len(av), len(bv))):
        d = (av[i] if i < len(av) else 0) - (bv[i] if i < len(bv) else 0)
        if d:
            return d
    return 0


POKER_NAMES = ["High card", "One pair", "Two pair", "Three of a kind", "Straight", "Flush", "Full house", "Four of a kind", "Straight flush"]


def poker_name(category):
    return POKER_NAMES[category]


def rank_name(r):
    return {14: "ace", 13: "king", 12: "queen", 11: "jack"}.get(r, str(r))


def poker_description(hand):
    score = evaluate_poker(hand)
    category = score[0]
    if category == 8 and score[1] == 14:
        return "Royal flush"
    if category in (8, 4):
        return f"{poker_name(category)} · {rank_name(score[1])} high"
    if category in (7, 6, 3, 2, 1):
        return f"{poker_name(category)} · {rank_name(score[1])}{f' over {rank_name(score[2])}' if category == 2 else ''}"
    return poker_name(category)


def jacks_award(hand):
    score = evaluate_poker(hand)
    cat = score[0]
    if cat == 8:
        return JACKS_PAYTABLE[0] if score[1] == 14 else JACKS_PAYTABLE[1]
    table = {7: 2, 6: 3, 5: 4, 4: 5, 3: 6, 2: 7}
    if cat in table:
        return JACKS_PAYTABLE[table[cat]]
    if cat == 1 and score[1] in (11, 12, 13, 14):
        return JACKS_PAYTABLE[8]
    return None


def start_poker(o):
    variant = o.get("variant") or "showdown"
    stake = o.get("stakeCents", 500)
    require_stake(stake, 5 if variant == "showdown" else 1, 100_000)
    cards = shuffled_deck()
    player = cards[:5]
    del cards[:5]
    state = {"variant": variant, "player": player, "deck": cards, "phase": "draw", "stakeCents": stake}
    if variant == "showdown":
        state["dealer"] = cards[:5]
        del cards[:5]
    return {"state": state, "view": {"player": player, "dealerCount": 5 if variant == "showdown" else 0, "phase": "draw", "variant": variant}}


def poker_action(state, holds):
    if state.get("phase") != "draw":
        raise EngineError("Poker hand is already settled")
    player, cards, stake = state["player"], state["deck"], state.get("stakeCents") or 0
    keep = {i for i in holds if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < 5}
    for i in range(5):
        if i not in keep:
            player[i] = draw(cards)
    if state["variant"] == "jacks":
        award = jacks_award(player)
        returned = stake * award["gross"] if award else 0
        ln = line(award["id"] if award else "no-win", award["label"] if award else "No qualifying pair", stake, returned,
                  f"{award['label']} pays {award['gross']}× gross." if award else "Pair of tens or lower does not qualify.")
        outcome = {"player": player, "playerRank": poker_description(player), "award": award["id"] if award else None, "drawCount": 5 - len(keep), "lines": [ln]}
        return {"state": {**state, "player": player, "deck": cards, "phase": "done"},
                "settlement": settlement(stake, [ln], outcome, award["label"] if award else "No qualifying hand"), "view": outcome}
    dealer = state["dealer"]
    if evaluate_poker(dealer)[0] >= 4:
        dealer_keep = [0, 1, 2, 3, 4]
    else:
        paired = [i for i, c in enumerate(dealer) if any(j != i and o["r"] == c["r"] for j, o in enumerate(dealer))]
        if paired:
            dealer_keep = paired
        else:
            ordered = sorted(({"i": i, "rank": 14 if c["r"] == 1 else c["r"]} for i, c in enumerate(dealer)), key=lambda x: -x["rank"])
            dealer_keep = sorted(x["i"] for x in ordered[:2])
    for i in range(5):
        if i not in dealer_keep:
            dealer[i] = draw(cards)
    cmp = compare_poker(player, dealer)
    returned = stake * 9 // 5 if cmp > 0 else stake if cmp == 0 else 0
    pr, dr = poker_description(player), poker_description(dealer)
    reason = f"{pr} beats {dr}." if cmp > 0 else f"{dr} beats {pr}." if cmp < 0 else f"Equal {pr}; suits do not break ties."
    ln = line("showdown", pr, stake, returned, reason)
    outcome = {"player": player, "dealer": dealer, "playerRank": pr, "dealerRank": dr, "drawCount": 5 - len(keep), "dealerKeep": dealer_keep, "lines": [ln]}
    return {"state": {**state, "player": player, "dealer": dealer, "deck": cards, "phase": "done"},
            "settlement": settlement(stake, [ln], outcome, f"{pr} vs {dr}"), "view": outcome}


def start_game(game, option_id, options=None):
    o = dict(options or {})
    selected = o.get("variant") or DEFAULT_VARIANT.get(game, "european")
    if not casino_variant(game, selected):
        raise EngineError("Unknown casino variant")
    o["variant"] = selected
    if game == "roulette":
        return start_roulette(o)
    if game == "slots":
        return start_slots(o)
    if game == "baccarat":
        if not o.get("tickets"):
            o["tickets"] = [{"betId": option_id, "stakeCents": o.get("stakeCents", 500)}]
        return start_baccarat(o)
    if game == "crash":
        if o.get("target") is None:
            try:
                o["target"] = js_round(float(option_id) * 100) or 200
            except ValueError:
                o["target"] = 200
        return start_crash(o)
    if game == "sixdraw":
        if o.get("target") is None:
            o["target"] = 3 if option_id == "survive" else int(option_id) if option_id.isdigit() else -1
        return start_six_draw(o)
    if game == "blackjack":
        return start_blackjack(o)
    if game == "poker":
        return start_poker(o)
    raise EngineError("Unknown casino game")


def sanitize_active_view(state, now=None):
    now = now_ms() if now is None else now
    if state.get("variant") == "live" and state.get("phase") == "live":
        return live_crash_view(state, now)
    return active_view(state)
