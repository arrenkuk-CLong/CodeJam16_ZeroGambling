"""Persistent world: inventory, preferences, the multi-asset casino, shop and Trader Alex (port of
expanded.server.ts and the zg_casino_*_v2 / zg_shop_* / zg_trade Postgres functions)."""
import copy
import math
import secrets

from django.db import transaction
from django.utils import timezone

from . import casino_engine as engine
from . import challenge_catalog as catalog
from . import slide_balance as sb
from .casino_rules import CASINO_VARIANTS, DEFAULT_VARIANT, EVEN_MONEY, GAME_IDS, casino_variant, format_cents, parse_cents
from .economy import UserError, equipment_stake_value, glider_stake_value, log_stake_value, skill_stake_value
from .jscompat import js_round
from .models import (ActionRequest, CasinoRound, CasinoSession, ChallengeMastery, ChallengeRun, Completion, InventoryItem, LossLedger,
                     PlayerPreferences, Trophy)
from .services import iso, lock_player, move_gems, rid
from .shop_catalog import (COLLECTIBLE_NAMES, COLLECTIBLE_SYMBOLS, EQUIPMENT, MAX_BUDGET, MIN_BUDGET, RARITIES, TRADER_OFFERS,
                           draw_collectibles)
from .slide import game_summary, steer_pct

DEFAULT_PREFERENCES = {"reducedMotion": False, "sound": True, "sessionReminders": True, "allowSkillStakes": True, "allowEquipmentStakes": True,
                       "allowSlideStakes": True, "allowLogStakes": False, "confirmStakes": True}
PREF_FIELDS = {"reducedMotion": "reduced_motion", "sound": "sound", "sessionReminders": "session_reminders", "allowSkillStakes": "allow_skill_stakes",
               "allowEquipmentStakes": "allow_equipment_stakes", "allowSlideStakes": "allow_slide_stakes", "allowLogStakes": "allow_log_stakes",
               "confirmStakes": "confirm_stakes"}


def random_int(mx: int) -> int:
    return secrets.randbelow(mx)


def ensure_world(player):
    PlayerPreferences.objects.get_or_create(player=player)


def preferences_view(p):
    return {k: getattr(p, f) for k, f in PREF_FIELDS.items()} if p else dict(DEFAULT_PREFERENCES)


def item_row(i: InventoryItem) -> dict:
    """The inventory row as stored (what the Postgres functions returned with to_jsonb)."""
    return {"id": str(i.id), "player_id": str(i.player_id), "kind": i.kind, "item_key": i.item_key, "name": i.name, "price": i.price, "symbol": i.symbol,
            "metadata": i.metadata, "level": i.level, "acquired_from": i.acquired_from, "request_id": i.request_id, "created_at": iso(i.created_at)}


def session_view(s: CasinoSession, now=None) -> dict:
    settled = s.status == "settled"
    stake_cents = s.stake_cents if s.stake_cents is not None else s.stake * 100
    total = s.total_committed_cents if s.total_committed_cents is not None else stake_cents
    result = None
    if s.result:
        r = s.result
        outcome = r.get("outcome") or {}
        returned = r.get("returnCents", outcome.get("returnCents", 0))
        committed = r.get("committedCents", total)
        result = {"status": r.get("status"), "multiplier": r.get("multiplier"), "label": r.get("label"), "outcome": r.get("outcome"),
                  "returnCents": returned, "committedCents": committed, "netCents": r.get("netCents", returned - committed),
                  "lines": r.get("lines") or outcome.get("lines") or []}
        if r.get("balanceCents") is not None:
            result["balanceCents"] = r["balanceCents"]
    return {
        "id": str(s.id), "game": s.game, "option": s.option, "variant": s.variant or DEFAULT_VARIANT.get(s.game, "european"),
        "rulesVersion": s.rules_version or 1, "version": s.version or 1, "stake": s.stake, "stakeCents": stake_cents, "totalCommittedCents": total,
        "assetType": s.asset_type, "assetLabel": (s.quote or {}).get("label") or "Virtual gems", "status": s.status,
        "view": ((s.result or {}).get("outcome") or {}) if settled else engine.sanitize_active_view(s.state or {}, now),
        "result": result, "createdAt": iso(s.created_at),
    }


def get_world(player) -> dict:
    ensure_world(player)
    active = CasinoSession.objects.filter(player=player, status="active").order_by("-created_at").first()
    rounds = []
    for r in CasinoRound.objects.filter(player=player).order_by("-created_at")[:30]:
        stake_cents = r.stake_cents if r.stake_cents is not None else r.stake * 100
        return_cents = r.return_cents if r.return_cents is not None else r.total_return * 100
        net = r.net if r.net is not None else r.total_return - r.stake
        rounds.append({"id": str(r.id), "game": r.game, "option": r.option, "variant": r.variant or "european", "stake": r.stake, "stakeCents": stake_cents,
                       "returnCents": return_cents, "netCents": r.net_cents if r.net_cents is not None else net * 100, "assetType": r.asset_type or "gems",
                       "assetLabel": r.asset_label or "Virtual gems", "won": r.won, "totalReturn": r.total_return, "net": net, "outcome": r.outcome,
                       "at": iso(r.created_at)})
    return {
        "inventory": [{"id": str(i.id), "kind": i.kind, "key": i.item_key, "name": i.name, "price": i.price, "symbol": i.symbol, "metadata": i.metadata,
                       "level": i.level, "acquiredFrom": i.acquired_from, "createdAt": iso(i.created_at)}
                      for i in InventoryItem.objects.filter(player=player).order_by("-created_at")],
        "game": game_summary(player),
        "trophies": [{"id": str(t.id), "gameId": t.game_id, "milestone": t.milestone, "name": t.name, "at": iso(t.created_at)}
                     for t in Trophy.objects.filter(player=player).order_by("-created_at")],
        "losses": [{"id": str(entry.id), "game": entry.game, "description": entry.description, "snapshot": entry.snapshot, "at": iso(entry.created_at)}
                   for entry in LossLedger.objects.filter(player=player).order_by("-created_at")[:40]],
        "preferences": preferences_view(PlayerPreferences.objects.filter(player=player).first()),
        "manifest": CASINO_VARIANTS,
        "activeSession": session_view(active) if active else None,
        "rounds": rounds,
        "traderOffers": TRADER_OFFERS,
    }


# ---------- casino ----------
def quote_asset(player, asset, prefs) -> tuple:
    kind = asset.get("type") if isinstance(asset, dict) else None
    if kind == "gems":
        stake = parse_cents(asset.get("amount"))
        if stake is None or stake < 1 or stake > 100_000:
            raise UserError("Gem stake must be 0.01–1000.00 with at most two decimal places.")
        return {"type": kind, "label": "Virtual gems"}, stake
    if kind == "skill":
        if not prefs["allowSkillStakes"]:
            raise UserError("Skill staking is switched off in Preferences.")
        game_id, rollback = asset.get("gameId"), asset.get("rollbackLevel")
        if not isinstance(game_id, int) or not isinstance(rollback, int) or rollback < 1:
            raise UserError("Choose a rollback level below your current level.")
        m = ChallengeMastery.objects.filter(player=player, game_id=game_id).first()
        entry = catalog.get_entry(game_id)
        if not m or not entry:
            raise UserError("No skill progress is available to stake.")
        stake = skill_stake_value(m.level, rollback)
        if not stake:
            raise UserError("Choose a rollback level below your current level.")
        return {"type": kind, "gameId": game_id, "rollbackLevel": rollback, "label": f"{entry['name']} · Lv {m.level} → {rollback}"}, stake * 100
    if kind == "equipment":
        if not prefs["allowEquipmentStakes"]:
            raise UserError("Equipment staking is switched off in Preferences.")
        item = InventoryItem.objects.filter(id=_uuid(asset.get("itemId")), player=player, kind="equipment").first()
        if not item:
            raise UserError("That equipment is no longer available.")
        glider = item.item_key == "glider"
        worth = sb.glider_invested(item.level) if glider else item.price
        label = f"{item.name}{f' Lv {item.level}' if glider else ''} · lost on a loss"
        return {"type": kind, "itemId": str(item.id), "label": label}, equipment_stake_value(worth) * 100
    if kind == "glider":
        if not prefs["allowSlideStakes"]:
            raise UserError("Glider level staking is switched off in Preferences.")
        g = InventoryItem.objects.filter(player=player, item_key="glider").first()
        if not g:
            raise UserError("You need a glider to stake glider levels.")
        n = asset.get("levels")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1 or n > g.level:
            raise UserError(f"Choose 1 to {g.level} glider levels." if g.level else "Your glider is at level 0, so there are no levels to stake.")
        to = g.level - n
        label = (f"Glider Lv {g.level} → {to} · steering {steer_pct(g.level)}% → {steer_pct(to)}% · "
                 f"reach {js_round(sb.reach_m(g.level))} m → {js_round(sb.reach_m(to))} m")
        return {"type": kind, "levels": n, "fromLevel": g.level, "label": label}, glider_stake_value(g.level, n) * 100
    if kind == "log":
        if not prefs["allowLogStakes"]:
            raise UserError("Full-log staking is switched off in Preferences.")
        levels = list(ChallengeMastery.objects.filter(player=player).values_list("level", flat=True))
        entries = Completion.objects.filter(player=player, passed=True).count()
        stake = log_stake_value(levels, entries)
        if not stake:
            raise UserError("Your active log has no progress to stake yet.")
        return {"type": kind, "label": "Entire active log + open skill progress", "levels": [{"level": lv} for lv in levels], "journalEntries": entries}, stake * 100
    raise UserError("Choose a valid stake asset.")


def _uuid(value):
    import uuid
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _apply_asset_loss(s: CasinoSession):
    q = s.quote or {}
    now = timezone.now()
    if s.asset_type == "skill":
        ChallengeMastery.objects.filter(player_id=s.player_id, game_id=q.get("gameId")).update(level=q.get("rollbackLevel"))
        ChallengeRun.objects.filter(player_id=s.player_id, game_id=q.get("gameId"), status__in=["issued", "active"]).update(status="skipped", finished_at=now)
        return f"Skill progress: {q.get('label') or 'challenge'}"
    if s.asset_type == "equipment":
        InventoryItem.objects.filter(id=s.asset_id, player_id=s.player_id).delete()
        return f"Equipment: {q.get('label') or 'item'}"
    if s.asset_type == "glider":
        g = InventoryItem.objects.filter(player_id=s.player_id, item_key="glider").first()
        if g:
            g.level = max(0, g.level - int(q.get("levels") or 0))
            g.save(update_fields=["level"])
        return f"Glider levels: {q.get('label') or 'glider'}"
    Completion.objects.filter(player_id=s.player_id).delete()
    ChallengeMastery.objects.filter(player_id=s.player_id).update(level=1)
    ChallengeRun.objects.filter(player_id=s.player_id, status__in=["issued", "active"]).update(status="skipped", finished_at=now)
    return "Entire active log and open skill progress"


def settle_session(session_id, result: dict, state: dict) -> CasinoSession:
    """zg_casino_settle_v2: pays gems, applies a lost asset, records the round. Call inside a transaction."""
    s = CasinoSession.objects.select_for_update().get(id=session_id)
    if s.status == "settled":
        return s
    p = lock_player(s.player_id)
    outcome = result.get("status")
    if outcome not in ("win", "loss", "push"):
        raise UserError("Invalid casino result.")
    total = s.total_committed_cents
    if s.asset_type == "gems":
        credit = int(result.get("returnCents") or 0)
        if credit < 0 or credit > 100_000_000:
            raise UserError("Invalid casino return.")
        net = credit - total
    else:
        credit = max(0, int(result.get("returnCents") or 0) - s.stake_cents) if outcome == "win" else 0
        net = -total if outcome == "loss" else credit
        if outcome == "loss":
            asset_name = _apply_asset_loss(s)
            LossLedger.objects.create(player=p, game=s.game, description=f"Lost {asset_name} · estimated value {format_cents(s.stake_cents)} gems", snapshot=s.quote)
    if credit > 0:
        move_gems(p, credit, f"Casino {outcome}: {s.game}", f"{s.request_id}:return:{s.version}")
    result = {**result, "balanceCents": p.gem_cents, "netCents": net}
    s.status, s.result, s.state, s.finished_at = "settled", result, state, timezone.now()
    s.save()
    CasinoRound.objects.create(player=p, request_id=s.request_id, game=s.game, option=s.option, stake=math.ceil(total / 100), outcome=result,
                               won=outcome == "win", total_return=credit // 100, asset_type=s.asset_type,
                               asset_label=(s.quote or {}).get("label") or "Virtual gems", net=(abs(net) // 100) * (1 if net >= 0 else -1), session=s,
                               variant=s.variant, rules_version=s.rules_version, stake_cents=total, return_cents=credit, net_cents=net)
    return s


def _check_config(config):
    config = config if isinstance(config, dict) else {}
    out = {}
    if config.get("variant") is not None:
        if not isinstance(config["variant"], str) or len(config["variant"]) > 30:
            raise UserError("Unknown casino variant.")
        out["variant"] = config["variant"]
    tickets = config.get("tickets")
    if tickets is not None:
        if not isinstance(tickets, list) or len(tickets) > 40:
            raise UserError("Too many tickets on the table.")
        clean = []
        for t in tickets:
            if not isinstance(t, dict) or not isinstance(t.get("betId"), str) or len(t["betId"]) > 60:
                raise UserError("Unknown ticket.")
            cents = t.get("stakeCents")
            if not isinstance(cents, int) or isinstance(cents, bool) or not 0 < cents <= 100_000:
                raise UserError("Each ticket needs a stake between 0.01 and 1000.00.")
            clean.append({"betId": t["betId"], "stakeCents": cents})
        out["tickets"] = clean
    if config.get("lines") is not None:
        if config["lines"] not in (1, 3):
            raise UserError("Play one or three lines.")
        out["lines"] = config["lines"]
    if config.get("target") is not None:
        if not isinstance(config["target"], int) or not 1 <= config["target"] <= 10_000:
            raise UserError("Choose a valid target.")
        out["target"] = config["target"]
    if "autoTarget" in config:
        at = config["autoTarget"]
        if at is not None and (not isinstance(at, int) or not 101 <= at <= 10_000):
            raise UserError("Auto target must be 1.01×–100.00×.")
        out["autoTarget"] = at
    return out


def start_wager(player, request_id, game, option, asset, config) -> dict:
    if game not in GAME_IDS:
        raise UserError("Unknown casino game.")
    if not isinstance(option, str) or len(option) > 30:
        raise UserError("Unknown bet.")
    config = _check_config(config)
    key = rid(player, request_id)
    existing = CasinoSession.objects.filter(request_id=key).first()
    if existing:
        return session_view(existing)
    if CasinoSession.objects.filter(player=player, status="active").exists():
        raise UserError("Finish your active hand before starting another wager.")
    variant_id = config.get("variant") or DEFAULT_VARIANT[game]
    variant = casino_variant(game, variant_id)
    if not variant:
        raise UserError("Unknown casino variant.")
    prefs = preferences_view(PlayerPreferences.objects.filter(player=player).first())
    quote, stake_cents = quote_asset(player, asset, prefs)
    if quote["type"] != "gems":
        if not variant["assetStakes"]:
            raise UserError("This variant accepts gem credits only because partial returns or extra wagers cannot be represented by the asset adapter.")
        n_tickets = len(config["tickets"]) if config.get("tickets") is not None else 1
        if game == "baccarat" and n_tickets != 1:
            raise UserError("An asset stake fits one baccarat bet. Switch to gems to stack bets.")
        if game == "roulette":
            if n_tickets != 1:
                raise UserError("An asset stake fits one roulette ticket. Switch to gems for multiple tickets.")
            bet = config["tickets"][0]["betId"] if config.get("tickets") else option
            if variant_id == "french" and bet in EVEN_MONEY:
                raise UserError("La partage can return half a stake, so this ticket accepts gems only.")
    try:
        result = engine.start_game(game, option, {**config, "variant": variant_id, "stakeCents": stake_cents, "now": engine.now_ms()})
    except engine.EngineError as e:
        raise UserError(str(e))
    with transaction.atomic():
        existing = CasinoSession.objects.filter(request_id=key).first()
        if existing:
            return session_view(existing)
        p = lock_player(player.id)
        if stake_cents < 1 or stake_cents > 100_000:
            raise UserError("Stake must be between 0.01 and 1000.00.")
        kind = quote["type"]
        if kind == "gems":
            if p.gem_cents < stake_cents:
                raise UserError("Not enough gems for that stake.")
            move_gems(p, -stake_cents, f"Casino stake reserved: {game}", key)
        elif kind == "skill":
            m = ChallengeMastery.objects.filter(player=p, game_id=quote["gameId"]).first()
            if not m or m.level <= quote["rollbackLevel"] or quote["rollbackLevel"] < 1:
                raise UserError("That stake is no longer available.")
        elif kind == "equipment":
            if not InventoryItem.objects.filter(id=quote["itemId"], player=p, kind="equipment").exists():
                raise UserError("That stake is no longer available.")
        elif kind == "glider":
            g = InventoryItem.objects.filter(player=p, item_key="glider").first()
            if not g or not 1 <= quote["levels"] <= g.level or g.level != quote["fromLevel"]:
                raise UserError("That stake is no longer available.")
        elif kind == "log":
            if not ChallengeMastery.objects.filter(player=p).exists() and not Completion.objects.filter(player=p).exists():
                raise UserError("That stake is no longer available.")
        s = CasinoSession.objects.create(player=p, request_id=key, game=game, option=option, stake=math.ceil(stake_cents / 100), asset_type=kind,
                                         asset_id=_uuid(quote.get("itemId")) if quote.get("itemId") else None, quote=quote, state=result["state"],
                                         variant=variant_id, rules_version=variant["rulesVersion"], stake_cents=stake_cents, total_committed_cents=stake_cents)
        if result.get("settlement"):
            s = settle_session(s.id, result["settlement"], result["state"])
    return session_view(s)


ACTIONS = ("hit", "stand", "double", "split", "insurance", "declineInsurance", "draw", "reveal", "cashout", "tick")


def act_on_wager(player, session_id, request_id, action, payload) -> dict:
    if action not in ACTIONS:
        raise UserError("This game has no such action.")
    key = rid(player, request_id)
    prior = ActionRequest.objects.filter(request_id=key).first()
    if prior and (prior.response or {}).get("sessionId"):
        return session_view(CasinoSession.objects.get(id=prior.response["sessionId"]))
    s = CasinoSession.objects.filter(id=_uuid(session_id), player=player).first()
    if not s or s.status != "active":
        raise UserError("This round is not active.")
    state = copy.deepcopy(s.state)
    try:
        if s.game == "blackjack":
            result = engine.blackjack_action(state, action, {"insuranceCents": payload.get("insuranceCents")})
        elif s.game == "poker" and action == "draw":
            holds = payload.get("holds") or []
            if not isinstance(holds, list) or len(holds) > 5:
                raise UserError("Hold up to five cards.")
            result = engine.poker_action(state, holds)
        elif s.game == "crash":
            result = engine.crash_action(state, action, engine.now_ms())
        elif s.game == "sixdraw" and action == "reveal":
            result = engine.six_draw_action(state, payload.get("tile"))
        else:
            raise UserError("This game has no such action.")
    except engine.EngineError as e:
        raise UserError(str(e))
    if not result.get("settlement") and s.game == "crash":
        s.state = result["state"]
        return session_view(s)
    extra = result.get("additionalCents") or 0
    if extra > 0 and s.asset_type != "gems":
        raise UserError("This asset cannot fund an additional wager.")
    with transaction.atomic():
        if ActionRequest.objects.filter(request_id=key).exists():
            return session_view(CasinoSession.objects.get(id=s.id))
        locked = CasinoSession.objects.select_for_update().get(id=s.id)
        if locked.status != "active":
            raise UserError("This round is not active.")
        if locked.version != s.version:
            raise UserError("This round changed in another tab. Refresh to resume it.")
        if extra < 0 or locked.total_committed_cents + extra > 100_000:
            raise UserError("That would go over the table's exposure limit.")
        if extra > 0:
            p = lock_player(locked.player_id)
            if p.gem_cents < extra:
                raise UserError("Not enough gems for this additional wager.")
            move_gems(p, -extra, f"Casino {action}: {locked.game}", key)
        locked.action_log = [*(locked.action_log or []), {"action": action, "at": iso(timezone.now()), "additionalCents": extra, "version": locked.version}]
        locked.state, locked.version, locked.total_committed_cents = result["state"], locked.version + 1, locked.total_committed_cents + extra
        locked.save()
        ActionRequest.objects.create(request_id=key, player_id=locked.player_id, response={"sessionId": str(locked.id)})
        if result.get("settlement"):
            locked = settle_session(locked.id, result["settlement"], result["state"])
    return session_view(locked)


# ---------- shop and trades ----------
def buy_product(player, request_id, product_key) -> dict:
    product = next((dict(p) for p in EQUIPMENT if p["key"] == product_key), None)
    if product_key == "random-collectible":
        rarity = RARITIES[random_int(len(RARITIES))]
        product = {"kind": "collectible", "key": f"generated-{random_int(10 ** 9)}",
                   "name": f"{COLLECTIBLE_NAMES[random_int(len(COLLECTIBLE_NAMES))]} {100 + random_int(900)}",
                   "price": js_round((100 + random_int(161)) * rarity["multiplier"]), "symbol": COLLECTIBLE_SYMBOLS[random_int(len(COLLECTIBLE_SYMBOLS))],
                   "description": f"{rarity['name']} procedurally generated collectible."}
    if not product:
        raise UserError("Unknown shop product.")
    key = rid(player, request_id)
    with transaction.atomic():
        done = InventoryItem.objects.filter(request_id=key).first()
        if done:
            return item_row(done)
        p = lock_player(player.id)
        if not 1 <= product["price"] <= 100_000 or product["kind"] not in ("equipment", "collectible"):
            raise UserError("Unknown shop product.")
        if product["key"] == "glider" and InventoryItem.objects.filter(player=p, item_key="glider").exists():
            raise UserError("You already own a glider. Upgrade it instead.")
        if p.gems < product["price"]:
            raise UserError("Not enough gems. Earn more with a challenge.")
        move_gems(p, -product["price"] * 100, f"Shop purchase: {product['name']}", key)
        item = InventoryItem.objects.create(player=p, kind=product["kind"], item_key=product["key"], name=product["name"], price=product["price"],
                                            symbol=product["symbol"], metadata={"description": product.get("description") or f"{product['name']} collectible."},
                                            request_id=key)
    return item_row(item)


def trade_item(player, request_id, item_id, offer_key) -> dict:
    offer = next((o for o in TRADER_OFFERS if o["key"] == offer_key), None)
    if not offer:
        raise UserError("Unknown trader offer.")
    item = InventoryItem.objects.filter(id=_uuid(item_id), player=player, kind="collectible").first()
    if not item:
        raise UserError("Choose one of your collectibles to trade.")
    if item.price < offer["price"] * 0.8:
        raise UserError(f"Alex needs an item priced at least {math.ceil(offer['price'] * 0.8)} gems for this 1-for-1 swap.")
    key = rid(player, request_id)
    with transaction.atomic():
        done = InventoryItem.objects.filter(request_id=key).first()
        if done:
            return item_row(done)
        p = lock_player(player.id)
        old = InventoryItem.objects.select_for_update().filter(id=item.id, player=p, kind="collectible").first()
        if not old:
            raise UserError("Choose one of your collectibles to trade.")
        offered = item_row(old)
        old.delete()
        new = InventoryItem.objects.create(player=p, kind="collectible", item_key=offer["key"], name=offer["name"], price=offer["price"], symbol=offer["symbol"],
                                           metadata={"description": offer["description"], "rarity": "Trader exchange"}, acquired_from="Trader Alex", request_id=key)
        LossLedger.objects.create(player=p, game="trade", description=f"Traded {offered['name']} to Trader Alex for {new.name}",
                                  snapshot={"offered": offered, "received": item_row(new)})
    return item_row(new)


def save_preferences(player, prefs) -> dict:
    if not isinstance(prefs, dict) or any(not isinstance(prefs.get(k), bool) for k in PREF_FIELDS):
        raise UserError("Every preference must be on or off.")
    ensure_world(player)
    PlayerPreferences.objects.filter(player=player).update(updated_at=timezone.now(), **{f: prefs[k] for k, f in PREF_FIELDS.items()})
    return {k: prefs[k] for k in PREF_FIELDS}


def buy_collectible_batch(player, request_id, budget) -> dict:
    if not isinstance(budget, int) or isinstance(budget, bool) or not MIN_BUDGET <= budget <= MAX_BUDGET:
        raise UserError(f"Spend between {MIN_BUDGET} and {MAX_BUDGET} gems.")
    key = rid(player, request_id)

    def existing():
        rows = list(InventoryItem.objects.filter(player=player, request_id__startswith=f"{key}:").order_by("request_id"))
        return {"budget": budget, "spent": sum(r.price for r in rows), "items": [item_row(r) for r in rows]} if rows else None

    found = existing()
    if found:
        return found
    drawn = draw_collectibles(budget, random_int)["items"]
    total = sum(i["price"] for i in drawn)
    if not 1 <= len(drawn) <= 1000 or not 1 <= total <= budget:
        raise UserError("Unknown shop product.")
    with transaction.atomic():
        found = existing()
        if found:
            return found
        p = lock_player(player.id)
        if p.gems < budget:
            raise UserError("Not enough gems for that budget.")
        move_gems(p, -total * 100, f"Mystery collectibles x{len(drawn)}", key)
        InventoryItem.objects.bulk_create([
            InventoryItem(player=p, kind="collectible", item_key=i["key"], name=i["name"], price=i["price"], symbol=i["symbol"],
                          metadata={"rarity": i["rarity"], "description": f"{i['rarity']} procedurally generated collectible."},
                          request_id=f"{key}:{n:04d}", created_at=timezone.now())
            for n, i in enumerate(drawn, start=1)])
        rows = list(InventoryItem.objects.filter(player=p, request_id__startswith=f"{key}:").order_by("request_id"))
    return {"budget": budget, "spent": total, "items": [item_row(r) for r in rows]}
