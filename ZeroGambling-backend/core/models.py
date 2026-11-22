"""Database tables (port of Lovable's Postgres schema, drizzle/migrations 0000-0006).

A Player is the single source of truth for gems and progress. Guests are identified by the hash of a
browser-held token; a signed-in account links to exactly one Player (adopting this browser's guest
progress once). Every gem movement is a WalletLedger row; balances are kept in exact cents."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone as dj_tz


def utc_today():
    return dj_tz.now().date()


class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=128, unique=True)
    display_name = models.CharField(max_length=60, default="Player")
    gem_cents = models.BigIntegerField(default=0)
    is_demo = models.BooleanField(default=False)
    account = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="player")
    created_at = models.DateTimeField(default=dj_tz.now)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(gem_cents__gte=0), name="player_gem_cents_non_negative")]

    @property
    def gems(self) -> int:
        return self.gem_cents // 100

    def __str__(self):
        return f"{self.display_name} ({self.gems} gems)"


class AccountProfile(models.Model):
    """The public face of an account: username, display name, streak and timezone."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.CASCADE, related_name="zg_profile")
    username = models.CharField(max_length=30)
    display_name = models.CharField(max_length=60, null=True, blank=True)
    streak_days = models.IntegerField(default=0)
    timezone = models.CharField(max_length=60, default="America/Toronto")
    created_at = models.DateTimeField(default=dj_tz.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("username"), name="profile_username_lower_unique")]

    def __str__(self):
        return self.username


class ChallengeRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="challenge_runs")
    game_id = models.IntegerField()
    version = models.IntegerField()
    seed = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=200)
    level = models.IntegerField()
    modifiers = models.JSONField(default=list)
    public_data = models.JSONField()
    private_data = models.JSONField()
    play_state = models.JSONField(default=dict)
    status = models.CharField(max_length=10, default="issued")  # issued | active | passed | failed | skipped
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=1)
    hints = models.IntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    issued_at = models.DateTimeField(default=dj_tz.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "game_id", "fingerprint"], name="run_unique_fingerprint")]
        indexes = [models.Index(fields=["player", "game_id", "status"])]


class ChallengeMastery(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="mastery")
    game_id = models.IntegerField()
    level = models.IntegerField(default=1)
    peak_level = models.IntegerField(default=1)
    best_score = models.IntegerField(default=0)
    plays = models.IntegerField(default=0)
    passes = models.IntegerField(default=0)
    xp = models.IntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "game_id"], name="mastery_unique_game")]


class Completion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="completions")
    run = models.OneToOneField(ChallengeRun, on_delete=models.CASCADE, related_name="completion")
    game_id = models.IntegerField()
    level = models.IntegerField()
    score = models.IntegerField()
    passed = models.BooleanField()
    xp_awarded = models.IntegerField()
    gems_awarded = models.IntegerField()
    new_level = models.IntegerField()
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=dj_tz.now)


class WalletLedger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="ledger")
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    delta_cents = models.BigIntegerField(null=True, blank=True)
    balance_after_cents = models.BigIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=200)
    ref = models.CharField(max_length=200, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=dj_tz.now)


class CasinoSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="casino_sessions")
    request_id = models.CharField(max_length=200, unique=True)
    game = models.CharField(max_length=20)
    option = models.CharField(max_length=60)
    variant = models.CharField(max_length=30, default="european")
    rules_version = models.IntegerField(default=1)
    stake = models.IntegerField()
    stake_cents = models.BigIntegerField()
    total_committed_cents = models.BigIntegerField()
    asset_type = models.CharField(max_length=20, default="gems")
    asset_id = models.UUIDField(null=True, blank=True)
    quote = models.JSONField(default=dict)
    state = models.JSONField(default=dict)
    status = models.CharField(max_length=10, default="active")  # active | settled
    result = models.JSONField(null=True, blank=True)
    version = models.IntegerField(default=1)
    action_log = models.JSONField(default=list)
    created_at = models.DateTimeField(default=dj_tz.now)
    finished_at = models.DateTimeField(null=True, blank=True)


class CasinoRound(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="casino_rounds")
    request_id = models.CharField(max_length=200, unique=True)
    session = models.ForeignKey(CasinoSession, null=True, blank=True, on_delete=models.SET_NULL)
    game = models.CharField(max_length=20)
    option = models.CharField(max_length=60)
    variant = models.CharField(max_length=30, default="european")
    rules_version = models.IntegerField(default=1)
    stake = models.IntegerField()
    outcome = models.JSONField()
    won = models.BooleanField()
    total_return = models.IntegerField()
    net = models.IntegerField(null=True, blank=True)
    stake_cents = models.BigIntegerField(null=True, blank=True)
    return_cents = models.BigIntegerField(null=True, blank=True)
    net_cents = models.BigIntegerField(null=True, blank=True)
    asset_type = models.CharField(max_length=20, default="gems")
    asset_label = models.CharField(max_length=200, default="Virtual gems")
    created_at = models.DateTimeField(default=dj_tz.now)


class ActionRequest(models.Model):
    """Idempotency: every client request ID is stored once with its response."""
    request_id = models.CharField(max_length=200, primary_key=True)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="action_requests")
    response = models.JSONField()
    created_at = models.DateTimeField(default=dj_tz.now)


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="inventory")
    kind = models.CharField(max_length=12)  # equipment | collectible
    item_key = models.CharField(max_length=60)
    name = models.CharField(max_length=120)
    price = models.IntegerField()
    symbol = models.CharField(max_length=8, default="◈")
    metadata = models.JSONField(default=dict)
    level = models.IntegerField(default=0)
    acquired_from = models.CharField(max_length=40, default="shop")
    request_id = models.CharField(max_length=220, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=dj_tz.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player"], condition=Q(item_key="glider"), name="inventory_one_glider"),
            models.CheckConstraint(condition=Q(level__gte=0) & Q(level__lte=20), name="inventory_level_range"),
            models.CheckConstraint(condition=Q(price__gte=0), name="inventory_price_non_negative"),
        ]


class Trophy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="trophies")
    game_id = models.IntegerField()
    milestone = models.IntegerField()  # 10, 25 or 40
    name = models.CharField(max_length=60)
    created_at = models.DateTimeField(default=dj_tz.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "game_id", "milestone"], name="trophy_unique_milestone")]


class LossLedger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="losses")
    game = models.CharField(max_length=20)
    description = models.CharField(max_length=400)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=dj_tz.now)


class PlayerPreferences(models.Model):
    player = models.OneToOneField(Player, primary_key=True, on_delete=models.CASCADE, related_name="preferences")
    reduced_motion = models.BooleanField(default=False)
    sound = models.BooleanField(default=True)
    session_reminders = models.BooleanField(default=True)
    allow_skill_stakes = models.BooleanField(default=True)
    allow_equipment_stakes = models.BooleanField(default=True)
    allow_slide_stakes = models.BooleanField(default=True)
    allow_log_stakes = models.BooleanField(default=False)
    confirm_stakes = models.BooleanField(default=True)
    updated_at = models.DateTimeField(default=dj_tz.now)


class SlideRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="slide_runs")
    request_id = models.CharField(max_length=200, unique=True, null=True, blank=True)
    glider_level = models.IntegerField(null=True, blank=True)
    steer = models.FloatField()
    length_m = models.IntegerField(default=1000)
    rows = models.JSONField()
    limit_m = models.FloatField()
    seed = models.IntegerField()
    status = models.CharField(max_length=10, default="open")  # open | survived | crashed | abandoned
    distance_m = models.IntegerField(default=0)
    checkpoint_m = models.IntegerField(default=0)
    gems_awarded = models.IntegerField(default=0)
    local_date = models.DateField(default=utc_today)
    created_at = models.DateTimeField(default=dj_tz.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["player", "-created_at"])]
