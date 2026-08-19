from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):
    # Runs `CREATE EXTENSION IF NOT EXISTS vector` on whichever Postgres database
    # this migrates onto — the test DB, a teammate's machine, or production —
    # so the extension no longer depends on a manual `psql` step.

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        VectorExtension(),
    ]
