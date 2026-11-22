from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class BearerToken(TokenAuthentication):
    """"Authorization: Bearer <key>" for signed-in accounts. Like Lovable's bearerAccountId, an invalid or
    stale token simply means "not signed in", so guests keep working."""
    keyword = "Bearer"

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None
