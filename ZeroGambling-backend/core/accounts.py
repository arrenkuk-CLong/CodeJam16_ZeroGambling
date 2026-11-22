"""Accounts: sign-up, sign-in, password reset, username/email/password changes and deletion (replaces the
Supabase auth that Lovable used). An account signs in with email + password and gets a bearer token;
its profile (username, display name, streak, timezone) lives in AccountProfile."""
import re

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.authtoken.models import Token

from .economy import UserError
from .models import AccountProfile, Player
from .services import iso

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$", re.ASCII)
User = get_user_model()


class AccountError(UserError):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def account_json(user):
    return {"id": str(user.pk), "email": user.email, "created_at": iso(user.date_joined)}


def profile_json(user):
    p = AccountProfile.objects.filter(user=user).first()
    if not p:
        return None
    return {"id": str(user.pk), "username": p.username, "display_name": p.display_name, "streak_days": p.streak_days, "timezone": p.timezone}


def session_json(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"token": token.key, "account": account_json(user), "profile": profile_json(user)}


def _clean_email(email):
    email = (email or "").strip()
    try:
        validate_email(email)
    except ValidationError:
        raise AccountError("Enter a valid email")
    if len(email) > 255:
        raise AccountError("Enter a valid email")
    return email


def _check_password(password):
    if not isinstance(password, str) or len(password) < 8:
        raise AccountError("Password should be at least 8 characters.")
    if len(password) > 72:
        raise AccountError("Password should be at most 72 characters.")


def _unique_username(requested, user_id):
    """Same rule as Lovable's create_account_profile trigger: sanitise, fall back, add _n on a clash."""
    base = re.sub(r"[^A-Za-z0-9_]", "", requested or "")
    if len(base) < 3:
        base = f"user_{str(user_id).replace('-', '')[:8]}"
    base = base[:24]
    candidate, n = base, 0
    while AccountProfile.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}_{n}"
    return candidate


def sign_up(email, password, username):
    email = _clean_email(email)
    _check_password(password)
    if not isinstance(username, str) or not USERNAME_RE.match(username.strip()):
        raise AccountError("3–30 letters, numbers or underscores")
    if User.objects.filter(email__iexact=email).exists():
        raise AccountError("User already registered")
    with transaction.atomic():
        user = User.objects.create_user(username=email.lower(), email=email, password=password)
        name = _unique_username(username.strip(), user.pk)
        AccountProfile.objects.create(user=user, username=name, display_name=name)
    return session_json(user)


def sign_in(email, password):
    user = User.objects.filter(email__iexact=(email or "").strip()).first()
    if not user or not isinstance(password, str) or not authenticate(username=user.username, password=password):
        raise AccountError("Invalid login credentials")
    return session_json(user)


def sign_out(user):
    Token.objects.filter(user=user).delete()


def _safe_redirect(redirect_to):
    origins = getattr(settings, "FRONTEND_ORIGINS", ["http://localhost:3000"])
    if isinstance(redirect_to, str) and any(redirect_to == o or redirect_to.startswith(o + "/") for o in origins):
        return redirect_to
    return origins[0].rstrip("/") + "/reset-password"


def request_password_reset(email, redirect_to):
    """Always succeeds, so nobody can probe which emails have accounts."""
    user = User.objects.filter(email__iexact=(email or "").strip()).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{_safe_redirect(redirect_to)}#type=recovery&uid={uid}&token={token}"
        send_mail("Reset your ZeroGambling password", f"Choose a new password here:\n\n{link}\n\nIf you didn't ask for this, ignore this email.",
                  None, [user.email])


def confirm_password_reset(uid, token, password):
    _check_password(password)
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid or "")))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if not user or not default_token_generator.check_token(user, token or ""):
        raise AccountError("This reset link is invalid or has expired. Ask for a new one.")
    user.set_password(password)
    user.save()
    return session_json(user)


def update_user(user, email=None, password=None, current_password=None):
    if email is not None:
        email = _clean_email(email)
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise AccountError("A user with this email address has already been registered")
        user.email, user.username = email, email.lower()
    if password is not None:
        _check_password(password)
        if not current_password or not user.check_password(current_password):
            raise AccountError("Current password is incorrect.")
        user.set_password(password)
    user.save()
    return account_json(user)


def update_profile(user, username):
    clean = (username or "").strip()
    if not USERNAME_RE.match(clean):
        raise AccountError("Use 3–30 letters, numbers or underscores.")
    try:
        with transaction.atomic():
            if AccountProfile.objects.filter(username__iexact=clean).exclude(user=user).exists():
                raise IntegrityError
            AccountProfile.objects.update_or_create(user=user, defaults={"username": clean, "display_name": clean})
    except IntegrityError:
        raise AccountError("That username is already taken.", code="23505")
    return profile_json(user)


def delete_account(user):
    with transaction.atomic():
        Player.objects.filter(account=user).delete()  # every game table cascades from the player
        user.delete()
