from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0003_documentchunk_embedding"),
        # match your actual latest documents migration filename
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX documentchunk_embedding_hnsw_idx
                ON documents_documentchunk
                USING hnsw (embedding vector_cosine_ops);
            """,
            reverse_sql="DROP INDEX documentchunk_embedding_hnsw_idx;",
        ),
    ]
