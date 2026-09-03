from rest_framework.permissions import BasePermission
from .models import Membership


class IsTenantAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.membership is not None
            and request.company_role in (Membership.Role.OWNER, Membership.Role.ADMIN)
        )