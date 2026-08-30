from rest_framework.throttling import SimpleRateThrottle


class TenantRateThrottle(SimpleRateThrottle):
    scope = "chat"

    def get_cache_key(self, request, view):
        if not getattr(request, "tenant", None):
            return None   # unauthenticated request — let IsAuthenticated reject it instead
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.tenant.id,
        }