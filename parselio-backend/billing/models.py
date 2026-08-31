from django.db import models
from tenants.models import TenantScopedModel


class TenantUsage(TenantScopedModel):
    """Per-tenant, per-billing-period usage counters for the chat/AI pipeline."""

    billing_period = models.DateField()
    queries_count = models.PositiveIntegerField(default=0)
    tokens_used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "billing_period"],
                name="unique_usage_per_tenant_period",
            ),
        ]

    def __str__(self):
        return f"{self.tenant} usage for {self.billing_period}"