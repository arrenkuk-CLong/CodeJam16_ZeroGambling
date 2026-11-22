"""Slide game server (port of slide.server.ts and the zg_slide_* / zg_glider_upgrade functions): deals runs,
caps reported distances, pays the highest checkpoint and upgrades gliders. Balance numbers: slide_balance.py."""
import math
import random
import secrets

from django.db import transaction
from django.utils import timezone

from . import slide_balance as sb
from .economy import UserError
from .jscompat import js_round
from .models import ActionRequest, CasinoSession, InventoryItem, SlideRun
from .services import iso, lock_player, move_gems, rid


def steer_pct(level) -> int:
    return js_round(100 * sb.steer(level) / sb.STEER_MAX)


def run_json(r: SlideRun) -> dict:
    return {
        "id": str(r.id), "lengthM": r.length_m, "gliderLevel": r.glider_level, "seed": r.seed, "rows": r.rows, "lanes": list(sb.LANES), "steer": r.steer,
        "hit": {"obstacleHalf": sb.OBSTACLE_HALF, "ballR": sb.BALL_R, "hitR": sb.HIT_R, "wallU": sb.WALL_U, "depthM": sb.OBSTACLE_DEPTH_M},
        "speed": {"start": sb.SPEED_START, "max": sb.SPEED_MAX, "rampM": sb.TRACK_M}, "checkpointEveryM": sb.CHECKPOINT_EVERY_M,
    }


def glider_of(player):
    return InventoryItem.objects.filter(player=player, item_key="glider").first()


def glider_reserved(player, glider) -> bool:
    active = CasinoSession.objects.filter(player=player, status="active").first()
    return bool(active) and (active.asset_type == "glider" or (glider is not None and active.asset_id == glider.id))


def game_summary(player) -> dict:
    glider = glider_of(player)
    level = glider.level if glider else None
    top = level is not None and level >= sb.GLIDER_MAX_LEVEL
    nxt = None if top else 0 if level is None else level + 1
    today = timezone.now().date()
    finished = SlideRun.objects.filter(player=player).exclude(status="open")
    best = SlideRun.objects.filter(player=player, status__in=["survived", "crashed"]).order_by("-distance_m").first()
    return {
        "gliderLevel": level, "maxLevel": sb.GLIDER_MAX_LEVEL, "steerPct": steer_pct(level), "expectedM": js_round(sb.reach_m(level)),
        "nextSteerPct": None if nxt is None else steer_pct(nxt), "nextExpectedM": None if nxt is None else js_round(sb.reach_m(nxt)),
        "upgradeCost": None if level is None or top else sb.upgrade_cost(level), "gliderPrice": sb.GLIDER_PRICE,
        "trackM": sb.TRACK_M, "checkpoints": sb.checkpoints(),
        "rewardedRunsToday": SlideRun.objects.filter(player=player, local_date=today, gems_awarded__gt=0).count(),
        "rewardedRunsPerDay": sb.REWARDED_RUNS_PER_DAY, "best": best.distance_m if best else 0,
        "runs": [{"id": str(r.id), "status": r.status, "distanceM": r.distance_m, "checkpointM": r.checkpoint_m, "gems": r.gems_awarded, "date": iso(r.created_at)}
                 for r in finished.order_by("-created_at")[:5]],
        "reserved": glider_reserved(player, glider),
    }


def start_run(player, request_id) -> dict:
    """Every run starts at 0 m. The glider level fixes steering; the server deals rows and the physical cap."""
    glider = glider_of(player)
    level = glider.level if glider else None
    steer = js_round(sb.steer(level) * 10000) / 10000
    rows = sb.make_rows(random.Random(secrets.randbits(64)))
    limit = sb.perfect_reach(rows, steer * sb.REPORT_STEER_SLACK)
    key = rid(player, request_id)
    with transaction.atomic():
        existing = SlideRun.objects.filter(request_id=key).first()
        if existing:
            return run_json(existing)
        p = lock_player(player.id)
        SlideRun.objects.filter(player=p, status="open").update(status="abandoned", finished_at=timezone.now())
        run = SlideRun.objects.create(player=p, request_id=key, glider_level=level, steer=steer, rows=rows, limit_m=limit,
                                      seed=1 + secrets.randbelow(2147483646))
    return run_json(run)


def settle_report(run, result, distance_m, elapsed_s) -> dict:
    """Pure settlement rule: caps the reported distance and works out the paying checkpoint."""
    distance, status = max(0, math.trunc(distance_m)), result
    if status == "survived":
        distance = run["length_m"]
    if distance > float(run["limit_m"]):
        distance, status = math.trunc(float(run["limit_m"])), "crashed"
    distance = min(distance, run["length_m"])
    if elapsed_s + 1 < sb.min_seconds(distance) * 0.9:
        raise UserError("That run finished faster than the slide allows.")
    checkpoint = sb.checkpoint_m(distance)
    return {"status": status, "distance": distance, "checkpoint": checkpoint, "gems": sb.checkpoint_gems(checkpoint)}


def _shape(r: SlideRun) -> dict:
    return {"status": r.status, "distanceM": r.distance_m, "checkpointM": r.checkpoint_m, "gems": r.gems_awarded}


def finish_run(player, run_id, result, distance_m) -> dict:
    if result not in ("survived", "crashed"):
        raise UserError("Report a finish or a crash.")
    if not isinstance(distance_m, (int, float)) or isinstance(distance_m, bool) or not 0 <= distance_m <= 100000:
        raise UserError("Distance must be between 0 and 100000 m.")
    run = SlideRun.objects.filter(id=run_id, player=player).first()
    if not run:
        raise UserError("Run not found.")
    if run.status != "open":
        return _shape(run)
    elapsed = (timezone.now() - run.created_at).total_seconds()
    if elapsed > sb.RUN_EXPIRES_MIN * 60:
        SlideRun.objects.filter(id=run.id, status="open").update(status="abandoned", finished_at=timezone.now())
        raise UserError("This run timed out. Start a new one.")
    s = settle_report({"length_m": run.length_m, "limit_m": run.limit_m}, result, distance_m, elapsed)
    with transaction.atomic():
        p = lock_player(player.id)
        r = SlideRun.objects.select_for_update().get(id=run.id, player=p)
        if r.status != "open":
            return _shape(r)
        paid = SlideRun.objects.filter(player=p, local_date=r.local_date, gems_awarded__gt=0).count()
        award = max(0, s["gems"]) if paid < sb.REWARDED_RUNS_PER_DAY else 0
        r.status, r.distance_m, r.checkpoint_m, r.gems_awarded, r.finished_at = s["status"], s["distance"], s["checkpoint"], award, timezone.now()
        r.save()
        if award > 0:
            move_gems(p, award * 100, f"Slide checkpoint {s['checkpoint']} m", f"slide:{r.id}")
        return _shape(r)


def upgrade_glider(player, request_id) -> dict:
    glider = glider_of(player)
    if not glider:
        raise UserError("Buy a glider in the shop first.")
    if glider.level >= sb.GLIDER_MAX_LEVEL:
        raise UserError(f"Your glider is already at the top level ({sb.GLIDER_MAX_LEVEL}).")
    cost, from_level, key = sb.upgrade_cost(glider.level), glider.level, rid(player, request_id)
    with transaction.atomic():
        prior = ActionRequest.objects.filter(request_id=key).first()
        if prior:
            return {"level": prior.response.get("level")}
        p = lock_player(player.id)
        g = InventoryItem.objects.select_for_update().filter(player=p, item_key="glider").first()
        if not g:
            raise UserError("Buy a glider in the shop first.")
        if g.level != from_level:
            raise UserError("Your glider changed. Refresh and try again.")
        if g.level >= sb.GLIDER_MAX_LEVEL:
            raise UserError(f"Your glider is already at the top level ({sb.GLIDER_MAX_LEVEL}).")
        if glider_reserved(p, g):
            raise UserError("Your glider is committed to an open wager. Finish the round first.")
        if p.gems < cost:
            raise UserError("Not enough gems for this upgrade.")
        move_gems(p, -cost * 100, f"Glider level {g.level + 1}", key)
        g.level += 1
        g.save(update_fields=["level"])
        ActionRequest.objects.create(request_id=key, player=p, response={"id": str(g.id), "level": g.level})
    return {"level": g.level}
