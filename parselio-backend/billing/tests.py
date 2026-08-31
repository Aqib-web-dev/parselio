import threading
from django.test import TransactionTestCase

from tenants.models import Tenant
from .models import TenantUsage
from .services import record_usage, current_billing_period


class RecordUsageConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Race Co", slug="race-co")

    def test_concurrent_increments_are_not_lost(self):
        N = 20

        def worker():
            record_usage(self.tenant, tokens_used=10)

        threads = [threading.Thread(target=worker) for _ in range(N)]
        [t.start() for t in threads]     # fire all N at once
        [t.join() for t in threads]      # wait for all to finish

        usage = TenantUsage.objects.get(
            tenant=self.tenant, billing_period=current_billing_period()
        )
        self.assertEqual(usage.queries_count, N)      # the actual assertion
        self.assertEqual(usage.tokens_used, N * 10)