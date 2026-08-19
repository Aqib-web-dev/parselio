from django.db import models

from tenants.models import Team, TenantScopedModel
from pgvector.django import VectorField 

class Document(TenantScopedModel):
    """Uploaded company document that can be company-wide or team-specific."""

    class Visibility(models.TextChoices):
        COMPANY = "company", "Company"
        TEAM = "team", "Team"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.TEAM)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file_key = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(visibility="company", team__isnull=True)
                    | models.Q(visibility="team", team__isnull=False)
                ),
                name="document_visibility_matches_team",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "team"]),
            models.Index(fields=["tenant", "visibility"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    def __str__(self):
        return self.title


class DocumentChunk(TenantScopedModel):
    """Searchable text chunk extracted from one uploaded document."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=768, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "chunk_index"], name="unique_chunk_index_per_document"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document"]),
        ]
