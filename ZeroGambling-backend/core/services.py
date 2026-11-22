"""Players, the wallet and the challenge service (port of service.server.ts, account.server.ts and the
zg_settle_run / trophy Postgres functions). Every mutation runs in one transaction with the player row
locked, so retries and double clicks can't mint or charge twice."""
import hashlib
import json
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import challenge_catalog as catalog
from .challenges import MODULES
from .economy import ECONOMY, UserError, compute_reward, next_level
from .jscompat import Rng
from .models import ActionRequest, ChallengeMastery, ChallengeRun, Completion, Player, Trophy, WalletLedger


def iso(dt):
    if dt is None:
        return None
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def rid(player, request_id: str) -> str:
    return f"{player.id}:{request_id}"


def check_request_id(request_id):
    if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
        raise UserError("Missing request id")


# ---------- wallet ----------
def lock_player(player_id) -> Player:
    return Player.objects.select_for_update().get(id=player_id)


def _trunc_gems(cents: int) -> int:
    return (abs(cents) // 100) * (1 if cents >= 0 else -1)


def move_gems(player: Player, delta_cents: int, reason: str, ref) -> Player:
    """Changes a locked player's balance and writes the ledger row. Callers check the balance first and
    give their own message; this is the backstop that keeps the wallet from going negative."""
    if player.gem_cents + delta_cents < 0:
        raise UserError("Not enough gems.")
    player.gem_cents += delta_cents
    player.save(update_fields=["gem_cents"])
    WalletLedger.objects.create(player=player, delta=_trunc_gems(delta_cents), balance_after=player.gems, delta_cents=delta_cents,
                                balance_after_cents=player.gem_cents, reason=reason, ref=ref)
    return player


# ---------- players and accounts ----------
def can_claim(p) -> bool:
    """Pure rule: a guest player may be claimed only if it's not already linked and not a judge demo."""
    return bool(p) and not p.account_id and not p.is_demo


def resolve_player(token, demo=False) -> Player:
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        raise UserError("Invalid profile token")
    token_hash = sha256(token)
    found = Player.objects.filter(token_hash=token_hash).first()
    if found:
        return found
    try:
        with transaction.atomic():
            if demo:
                p = Player.objects.create(token_hash=token_hash, display_name="Judge demo", gem_cents=4200, is_demo=True)
                WalletLedger.objects.create(player=p, delta=42, balance_after=42, delta_cents=4200, balance_after_cents=4200,
                                            reason="Seeded judge demo profile", ref=f"seed:{p.id}")
            else:
                p = Player.objects.create(token_hash=token_hash, display_name="Player")
            return p
    except IntegrityError:
        return Player.objects.get(token_hash=token_hash)


def player_for_account(user, guest_token=None) -> Player:
    """Links the signed-in account to a game player, adopting this browser's guest progress once."""
    linked = Player.objects.filter(account=user).first()
    if linked:
        return linked
    if guest_token:
        guest = resolve_player(guest_token)
        if can_claim(guest) and Player.objects.filter(id=guest.id, account__isnull=True).update(account=user):
            return Player.objects.get(id=guest.id)
    try:
        with transaction.atomic():
            return Player.objects.create(token_hash=f"account:{user.id}", display_name="Player", account=user)
    except IntegrityError:
        again = Player.objects.filter(account=user).first()
        if again:
            return again
        raise UserError("Could not set up your account profile.")


def resolve_caller(user, token, demo=False) -> Player:
    """A signed-in account's linked player, otherwise the browser-token guest player."""
    if user is not None and user.is_authenticated:
        return player_for_account(user, token)
    p = resolve_player(token, demo)
    # A guest token that was adopted by an account never reopens that account's data when signed out.
    if p.account_id:
        raise UserError("This profile belongs to an account. Sign in to continue, or reload to start a guest profile.")
    return p


# ---------- challenges ----------
def get_mastery(player, game_id):
    m = ChallengeMastery.objects.filter(player=player, game_id=game_id).first()
    return m or ChallengeMastery(player=player, game_id=game_id)


def to_view(run: ChallengeRun, completion, reveal_ephemeral=False) -> dict:
    priv = run.private_data or {}
    finished = run.status not in ("issued", "active")
    show_stim = (not priv.get("ephemeral") or reveal_ephemeral) if run.status == "active" else finished
    ps = dict(run.play_state or {})
    hint_text = ps.pop("hintText", None) or []
    result = run.result
    receipt = None
    if completion:
        receipt = {"completionId": str(completion.id), "gameId": completion.game_id, "score": completion.score, "xpAwarded": completion.xp_awarded,
                   "gemsAwarded": completion.gems_awarded, "levelPlayed": completion.level, "newLevel": completion.new_level,
                   "balance": (result or {}).get("balance", 0)}
    public = run.public_data or {}
    time_limit = public.get("timeLimitSec") if public.get("timeLimitSec") is not None else priv.get("timeLimitSec")
    return {
        "id": str(run.id), "gameId": run.game_id, "version": run.version, "level": run.level, "modifiers": run.modifiers or [],
        "publicData": public, "stimulus": priv.get("stimulus") if show_stim else None, "playState": ps,
        "status": "void" if result and result.get("void") else run.status, "attempts": run.attempts, "maxAttempts": run.max_attempts,
        "hints": run.hints, "hintText": hint_text, "timeLimitSec": time_limit, "startedAt": iso(run.started_at), "serverNow": iso(timezone.now()),
        "result": {**result, "receipt": receipt} if result else None,
    }


def load_view(player, run_id, reveal_ephemeral=False):
    run = ChallengeRun.objects.filter(id=run_id, player=player).first()
    if not run:
        raise UserError("Challenge not found for this profile")
    return to_view(run, Completion.objects.filter(run=run).first(), reveal_ephemeral)


def issue_run(player, game_id, fresh=False):
    entry = catalog.get_entry(game_id)
    mod = MODULES.get(game_id)
    if not entry or not mod:
        raise UserError("That challenge is not in the active catalog")
    runs = ChallengeRun.objects.filter(player=player, game_id=game_id).order_by("-issued_at")
    open_run = runs.filter(status__in=["issued", "active"]).first()
    if open_run:
        return load_view(player, open_run.id)
    if not fresh:
        # Returning to a game (or refreshing) shows the last receipt instead of silently issuing a new puzzle.
        last = runs.first()
        if last:
            return load_view(player, last.id)
    m = get_mastery(player, game_id)
    for attempt in range(10):
        seed = secrets.token_hex(16)
        g = mod.generate(Rng(seed), m.level)
        fingerprint = sha256(json.dumps({"gameId": game_id, "v": mod.version, "level": m.level, "s": g["stimulus"], "a": g["answer"]},
                                        separators=(",", ":"), ensure_ascii=False))
        exhausted = attempt == 9
        if exhausted:
            fingerprint = f"{fingerprint}:repeat:{seed}"
        public = {**g["publicData"], "timeLimitSec": g.get("timeLimitSec")}
        try:
            with transaction.atomic():
                run = ChallengeRun.objects.create(
                    player=player, game_id=game_id, version=mod.version, seed=seed, fingerprint=fingerprint, level=m.level,
                    modifiers=g["modifiers"], public_data=public,
                    private_data={"stimulus": g["stimulus"], "answer": g["answer"], "ephemeral": bool(g.get("ephemeral")),
                                  "answerReveal": g.get("answerReveal"), "repeated": exhausted},
                    max_attempts=g["maxAttempts"], play_state={})
            return to_view(run, None)
        except IntegrityError:
            continue
    raise UserError("Could not issue a challenge")


def _award_trophies(completion):
    if completion.passed and completion.new_level > completion.level:
        for threshold in (10, 25, 40):
            if completion.level < threshold <= completion.new_level:
                Trophy.objects.get_or_create(player_id=completion.player_id, game_id=completion.game_id, milestone=threshold,
                                             defaults={"name": f"Breakthrough {threshold}"})


def settle_run(player, run, ev):
    """zg_settle_run: run status, completion, mastery, wallet and trophies, exactly once."""
    m = get_mastery(player, run.game_id)
    since = timezone.now() - timedelta(minutes=ECONOMY["repeatWindowMinutes"])
    recent = Completion.objects.filter(player=player, game_id=run.game_id, passed=True, created_at__gte=since).count()
    is_void = bool(ev.get("void"))
    elapsed = (timezone.now() - run.started_at).total_seconds() if run.started_at else None
    reward = compute_reward(ev["passed"], is_void, run.level, m.peak_level, run.hints, recent, bool(run.private_data.get("repeated")),
                            game_id=run.game_id, elapsed_sec=elapsed)
    new_level = next_level(run.level, m.peak_level, ev["passed"], is_void)
    result = {**ev, "reward": reward}
    if run.private_data.get("answerReveal") is not None:
        result["answerReveal"] = run.private_data["answerReveal"]
    passed = ev["passed"] and not is_void
    with transaction.atomic():
        p = lock_player(player.id)
        updated = ChallengeRun.objects.filter(id=run.id, player=p, status__in=["issued", "active"]).update(
            status="passed" if passed else "failed", result=result, finished_at=timezone.now())
        if not updated:
            return None
        completion = Completion.objects.create(player=p, run=run, game_id=run.game_id, level=run.level, score=ev["score"], passed=passed,
                                               xp_awarded=reward["xp"], gems_awarded=reward["gems"], new_level=new_level, metrics=ev.get("metrics") or {})
        mastery, _ = ChallengeMastery.objects.select_for_update().get_or_create(player=p, game_id=run.game_id)
        mastery.level = new_level
        mastery.peak_level = max(mastery.peak_level, new_level)
        mastery.best_score = max(mastery.best_score, ev["score"])
        mastery.plays += 1
        mastery.passes += 1 if passed else 0
        mastery.xp += reward["xp"]
        mastery.save()
        if reward["gems"]:
            move_gems(p, reward["gems"] * 100, f"Challenge #{run.game_id} level {run.level}", f"run:{run.id}")
        _award_trophies(completion)
        ChallengeRun.objects.filter(id=run.id).update(result={**result, "balance": p.gems})
        return {"completionId": str(completion.id), "balance": p.gems}


def _record(player, request_key, error=None):
    ActionRequest.objects.get_or_create(request_id=request_key, defaults={"player": player, "response": {"error": error} if error else {"ok": True}})


def run_action(player, run_id, request_id, action, payload):
    check_request_id(request_id)
    key = rid(player, request_id)
    prior = ActionRequest.objects.filter(request_id=key).first()
    if prior:
        view = load_view(player, run_id)
        err = (prior.response or {}).get("error")
        return {"run": view, **({"error": err} if err else {})}
    run = ChallengeRun.objects.filter(id=run_id, player=player).first()
    if not run:
        raise UserError("Challenge not found for this profile")
    mod = MODULES[run.game_id]
    g = {"publicData": run.public_data, "stimulus": run.private_data["stimulus"], "answer": run.private_data["answer"]}
    finished = run.status not in ("issued", "active")
    ps = run.play_state or {}
    reveal, err = False, None
    payload = payload if payload is not None else {}

    if finished:
        err = "This challenge is already finished."
    elif action == "start":
        if run.status == "issued":
            reveal = bool(ChallengeRun.objects.filter(id=run.id, status="issued").update(
                status="active", started_at=timezone.now(), play_state={**ps, "revealed": True}))
    elif action == "hint":
        hint = getattr(mod, "hint", None)
        text = hint(g, run.hints) if hint else None
        if not text:
            err = "No hint available for this challenge."
        else:
            ChallengeRun.objects.filter(id=run.id, hints=run.hints).update(hints=run.hints + 1, play_state={**ps, "hintText": [*(ps.get("hintText") or []), text]})
    elif action == "skip":
        result = {"score": 0, "passed": False, "feedback": ["Skipped. The puzzle is consumed and won't be issued again; no gems lost."], "metrics": {}, "reward": None}
        if run.private_data.get("answerReveal") is not None:
            result["answerReveal"] = run.private_data["answerReveal"]
        ChallengeRun.objects.filter(id=run.id, status__in=["issued", "active"]).update(status="skipped", finished_at=timezone.now(), result=result)
    elif run.status != "active":
        err = "Press Ready first."
    elif action == "guess":
        guess = getattr(mod, "guess", None)
        if not guess:
            err = "This game takes a single submission."
        else:
            out = guess(g, ps, payload, run.attempts, run.max_attempts)
            if out.get("error"):
                err = out["error"]
            else:
                new_state = {**out["state"], "revealed": True, "hintText": ps.get("hintText") or []}
                if not ChallengeRun.objects.filter(id=run.id, attempts=run.attempts).update(attempts=run.attempts + 1, play_state=new_state):
                    err = "That guess was already recorded in another tab."
                elif out.get("done"):
                    run.refresh_from_db()
                    settle_run(player, run, out["done"])
    elif action == "submit":
        evaluate = getattr(mod, "evaluate", None)
        if not evaluate:
            err = "Use guesses for this game."
        else:
            elapsed = (timezone.now() - run.started_at).total_seconds() * 1000 if run.started_at else None
            limit = (run.public_data or {}).get("timeLimitSec")
            if limit and elapsed is not None and elapsed > (limit + 5) * 1000:
                ev = {"score": 0, "passed": False, "feedback": [f"Time ran out ({limit} s limit)."], "metrics": {}}
            else:
                ev = evaluate(g, payload, {"level": run.level, "serverElapsedMs": elapsed})
            settle_run(player, run, ev)
    else:
        err = "Unknown action."

    _record(player, key, err)
    view = load_view(player, run_id, reveal)
    return {"run": view, "error": err} if err else {"run": view}


def round_view(r):
    return {"id": str(r.id), "game": r.game, "option": r.option, "stake": r.stake, "outcome": r.outcome, "won": r.won,
            "totalReturn": r.total_return, "net": r.total_return - r.stake, "at": iso(r.created_at)}


def player_summary(player):
    passes = Completion.objects.filter(player=player, passed=True).count()
    return {
        "player": {"id": str(player.id), "name": player.display_name, "gems": player.gems, "gemCents": player.gem_cents, "isDemo": player.is_demo,
                   "createdAt": iso(player.created_at), "lifetimePasses": passes},
        "mastery": [{"gameId": m.game_id, "level": m.level, "peak": m.peak_level, "best": m.best_score, "plays": m.plays, "passes": m.passes, "xp": m.xp}
                    for m in ChallengeMastery.objects.filter(player=player).order_by("game_id")],
        "completions": [{"id": str(c.id), "gameId": c.game_id, "level": c.level, "score": c.score, "passed": c.passed, "xp": c.xp_awarded,
                         "gems": c.gems_awarded, "newLevel": c.new_level, "at": iso(c.created_at)}
                        for c in Completion.objects.filter(player=player).order_by("-created_at")[:40]],
        "ledger": [{"id": str(entry.id), "delta": entry.delta, "balance": entry.balance_after,
                    "deltaCents": entry.delta_cents if entry.delta_cents is not None else entry.delta * 100,
                    "balanceCents": entry.balance_after_cents if entry.balance_after_cents is not None else entry.balance_after * 100,
                    "reason": entry.reason, "at": iso(entry.created_at)}
                   for entry in WalletLedger.objects.filter(player=player).order_by("-created_at")[:40]],
        "rounds": [round_view(r) for r in player.casino_rounds.order_by("-created_at")[:10]],
    }


def reset_progress(player, game_id):
    """Removes current skill progress only; completions, peak level and wallet history stay."""
    ChallengeMastery.objects.filter(player=player, game_id=game_id).update(level=1)
    ChallengeRun.objects.filter(player=player, game_id=game_id, status__in=["issued", "active"]).update(status="skipped", finished_at=timezone.now())
