"""JSON API for the Next.js frontend. One POST endpoint per Lovable server function, with the same inputs
and outputs; views only parse the request and call the services. Guests send their browser token in the
body; a signed-in account also sends "Authorization: Bearer <token>"."""
import logging
from functools import wraps

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import accounts, services, slide, world
from .authentication import BearerToken
from .economy import UserError

log = logging.getLogger(__name__)


def endpoint(methods=("POST",)):
    def wrap(view):
        @api_view(list(methods))
        @authentication_classes([BearerToken])
        @permission_classes([AllowAny])
        @wraps(view)
        def inner(request, *args, **kwargs):
            try:
                return Response(view(request, request.data if isinstance(request.data, dict) else {}, *args, **kwargs))
            except accounts.AccountError as e:
                return Response({"detail": str(e), "code": e.code}, status=400)
            except UserError as e:
                return Response({"detail": str(e)}, status=400)
            except Exception:  # noqa: BLE001 - never leak internals to the browser
                log.exception("API error")
                return Response({"detail": "Something went wrong on the server. Please try again."}, status=500)
        return inner
    return wrap


def caller(request, d, demo=False):
    return services.resolve_caller(request.user, d.get("token"), demo=demo)


def need_account(request):
    if not request.user or not request.user.is_authenticated:
        raise UserError("Please sign in again.")
    return request.user


def as_int(value, name):
    if not isinstance(value, int) or isinstance(value, bool):
        raise UserError(f"{name} must be a whole number.")
    return value


# ---------- player state ----------
@endpoint(("GET",))
def health(request, d):
    return {"ok": True}


@endpoint()
def summary(request, d):
    return services.player_summary(caller(request, d, demo=bool(d.get("demo"))))


@endpoint()
def world_state(request, d):
    return world.get_world(caller(request, d, demo=bool(d.get("demo"))))


@endpoint()
def preferences(request, d):
    return world.save_preferences(caller(request, d), d.get("preferences"))


# ---------- challenges ----------
@endpoint()
def issue_run(request, d):
    return services.issue_run(caller(request, d), as_int(d.get("gameId"), "gameId"), bool(d.get("fresh")))


@endpoint()
def run_action(request, d):
    if d.get("action") not in ("start", "guess", "hint", "skip", "submit"):
        raise UserError("Unknown action.")
    return services.run_action(caller(request, d), d.get("runId"), d.get("requestId"), d["action"], d.get("payload"))


@endpoint()
def reset_progress(request, d):
    services.reset_progress(caller(request, d), as_int(d.get("gameId"), "gameId"))
    return {"ok": True}


# ---------- casino ----------
@endpoint()
def start_wager(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    return world.start_wager(p, d["requestId"], d.get("game"), d.get("option"), d.get("asset"), d.get("config"))


@endpoint()
def act_on_wager(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    payload = {"holds": d.get("holds") or [], "tile": d.get("tile"), "insuranceCents": d.get("insuranceCents")}
    return world.act_on_wager(p, d.get("sessionId"), d["requestId"], d.get("action"), payload)


# ---------- shop ----------
@endpoint()
def buy_product(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    return world.buy_product(p, d["requestId"], d.get("productKey"))


@endpoint()
def buy_collectibles(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    return world.buy_collectible_batch(p, d["requestId"], d.get("budget"))


@endpoint()
def trade_item(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    return world.trade_item(p, d["requestId"], d.get("itemId"), d.get("offerKey"))


# ---------- slide game ----------
@endpoint()
def start_slide_run(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    return slide.start_run(p, d["requestId"])


@endpoint()
def finish_slide_run(request, d):
    return slide.finish_run(caller(request, d), d.get("runId"), d.get("result"), d.get("distanceM"))


@endpoint()
def upgrade_glider(request, d):
    p = caller(request, d)
    services.check_request_id(d.get("requestId"))
    return slide.upgrade_glider(p, d["requestId"])


# ---------- accounts ----------
@endpoint()
def sign_up(request, d):
    return accounts.sign_up(d.get("email"), d.get("password"), d.get("username"))


@endpoint()
def sign_in(request, d):
    return accounts.sign_in(d.get("email"), d.get("password"))


@endpoint()
def sign_out(request, d):
    if request.user and request.user.is_authenticated:
        accounts.sign_out(request.user)
    return {"ok": True}


@endpoint(("GET",))
def me(request, d):
    if not request.user or not request.user.is_authenticated:
        return {"account": None, "profile": None}
    return {"account": accounts.account_json(request.user), "profile": accounts.profile_json(request.user)}


@endpoint()
def recover(request, d):
    accounts.request_password_reset(d.get("email"), d.get("redirectTo"))
    return {"ok": True}


@endpoint()
def recover_confirm(request, d):
    return accounts.confirm_password_reset(d.get("uid"), d.get("token"), d.get("password"))


@endpoint()
def update_user(request, d):
    return {"account": accounts.update_user(need_account(request), d.get("email"), d.get("password"), d.get("currentPassword"))}


@endpoint()
def update_profile(request, d):
    return {"profile": accounts.update_profile(need_account(request), d.get("username"))}


@endpoint()
def claim_player(request, d):
    user = need_account(request)
    p = services.player_for_account(user, d.get("guestToken"))
    return {"playerId": str(p.id), "adoptedGuest": not p.token_hash.startswith("account:")}


@endpoint()
def delete_account(request, d):
    accounts.delete_account(need_account(request))
    return {"deleted": True}
