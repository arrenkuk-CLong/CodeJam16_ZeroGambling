from django.contrib import admin

from . import models

# Read-mostly views so the team can inspect players, the ledger and casino rounds during the demo.
for m in (models.AccountProfile, models.ChallengeRun, models.ChallengeMastery, models.Completion, models.CasinoSession,
          models.ActionRequest, models.InventoryItem, models.Trophy, models.LossLedger, models.PlayerPreferences, models.SlideRun):
    admin.site.register(m)


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "gems", "is_demo", "account", "created_at")
    list_filter = ("is_demo",)


@admin.register(models.WalletLedger)
class WalletLedgerAdmin(admin.ModelAdmin):
    list_display = ("created_at", "player", "reason", "delta_cents", "balance_after_cents")


@admin.register(models.CasinoRound)
class CasinoRoundAdmin(admin.ModelAdmin):
    list_display = ("created_at", "player", "game", "variant", "asset_type", "stake_cents", "return_cents", "net_cents")
    list_filter = ("game", "asset_type")
