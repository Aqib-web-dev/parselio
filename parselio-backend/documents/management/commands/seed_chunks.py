import random
import uuid

from django.core.management.base import BaseCommand

from documents.models import Document, DocumentChunk
from tenants.models import Tenant


class Command(BaseCommand):
    help = "Seed one tenant/document/N chunks with random 768-dim vectors, for testing query speed."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=2000)

    def handle(self, *args, **options):
        count = options["count"]

        tenant, _ = Tenant.objects.get_or_create(
            slug="seed-tenant",
            defaults={"name": "Seed Tenant", "id": uuid.uuid4()},
        )
        document = Document.objects.create(
            tenant=tenant,
            visibility=Document.Visibility.COMPANY,
            title="Seed Document",
            original_filename="seed.txt",
            status=Document.Status.READY,
        )

        chunks = [
            DocumentChunk(
                tenant=tenant,
                document=document,
                chunk_index=i,
                text=f"seed chunk {i}",
                embedding=[random.random() for _ in range(768)],
            )
            for i in range(count)
        ]
        DocumentChunk.objects.bulk_create(chunks, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded tenant {tenant.id} with {count} chunks on document {document.id}"
        ))