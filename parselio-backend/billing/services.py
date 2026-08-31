from datetime import date
from django.db import transaction

from .models import TenantUsage


def current_billing_period():
    """First day of the current month — the period key TenantUsage rows are scoped to."""
    today = date.today()
    return today.replace(day=1)


def record_usage(tenant, tokens_used):
    """Atomically increment this tenant's usage for the current billing period.

    Locks the row for the duration of the read-modify-write so concurrent
    calls (e.g. simultaneous chat requests) cannot lose an increment.
    """
    period = current_billing_period()

    with transaction.atomic():                                    # 1. open a transaction
        usage, _created = TenantUsage.objects.select_for_update().get_or_create(  # 2. lock (or create) the row
            tenant=tenant,
            billing_period=period,
        )
        usage.queries_count += 1                                     # 3. modify in Python, safely — no other
        usage.tokens_used += tokens_used                             #    writer can be mid-update on this row
        usage.save()                                                 # 4. write back, still holding the lock
    # 5. lock released automatically here, at the `with` block's exit (commit)