"""API routes. No trailing slashes, so the Next.js /api proxy can forward paths unchanged.
Each route matches a server function in ZeroGambling-frontend/lib/*.functions.ts."""
from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health),
    # player state (zg.functions / world.functions)
    path("summary", views.summary),
    path("world", views.world_state),
    path("preferences", views.preferences),
    # challenges
    path("challenges/issue", views.issue_run),
    path("challenges/action", views.run_action),
    path("challenges/reset", views.reset_progress),
    # casino
    path("casino/start", views.start_wager),
    path("casino/act", views.act_on_wager),
    # shop and Trader Alex
    path("shop/buy", views.buy_product),
    path("shop/collectibles", views.buy_collectibles),
    path("shop/trade", views.trade_item),
    # slide game
    path("slide/start", views.start_slide_run),
    path("slide/finish", views.finish_slide_run),
    path("slide/glider/upgrade", views.upgrade_glider),
    # accounts (account.functions + auth client)
    path("auth/signup", views.sign_up),
    path("auth/signin", views.sign_in),
    path("auth/signout", views.sign_out),
    path("auth/me", views.me),
    path("auth/recover", views.recover),
    path("auth/recover/confirm", views.recover_confirm),
    path("auth/user", views.update_user),
    path("auth/profile", views.update_profile),
    path("account/claim", views.claim_player),
    path("account/delete", views.delete_account),
]
