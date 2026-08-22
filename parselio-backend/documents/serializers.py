from rest_framework import serializers

from tenants.models import Membership, TeamMembership

from .models import Document, DocumentChunk


MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


class DocumentChunkSerializer(serializers.ModelSerializer):
    """Convert searchable document chunks to API JSON."""

    class Meta:
        model = DocumentChunk
        fields = ["id", "tenant", "document", "chunk_index", "text", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    """Validate document upload input and convert saved documents to API JSON."""

    file_size = serializers.IntegerField(write_only=True, required=True)
    content_type = serializers.CharField(write_only=True, required=True)
    chunk_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "tenant",
            "visibility",
            "team",
            "title",
            "original_filename",
            "file_key",
            "status",
            "file_size",
            "content_type",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "status", "chunk_count", "created_at", "updated_at"]

    def validate_file_size(self, value):
        """Reject uploaded files larger than the allowed size."""
        if value > MAX_DOCUMENT_SIZE_BYTES:
            raise serializers.ValidationError("Document file size must be 10 MB or smaller.")
        return value

    def validate_content_type(self, value):
        """Reject uploaded files whose content type is not allowed."""
        if value not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError("Only PDF, DOCX, and plain text files are allowed.")
        return value

    def validate(self, attrs):
        """Check document visibility, team ownership, and upload permission together."""
        tenant = self._get_tenant()
        user = self._get_user()
        visibility = attrs.get("visibility", getattr(self.instance, "visibility", Document.Visibility.TEAM))
        team = attrs.get("team", getattr(self.instance, "team", None))

        if visibility == Document.Visibility.COMPANY and team is not None:
            raise serializers.ValidationError({"team": "Company-wide documents must not have a team."})

        if visibility == Document.Visibility.TEAM and team is None:
            raise serializers.ValidationError({"team": "Team-specific documents must have a team."})

        if tenant is not None and team is not None and team.tenant_id != tenant.id:
            raise serializers.ValidationError({"team": "Selected team must belong to the request tenant."})

        if tenant is not None and user is not None:
            self._validate_upload_permission(user=user, tenant=tenant, visibility=visibility, team=team)

        return attrs

    def create(self, validated_data):
        """Remove temporary upload fields before creating the document row."""
        validated_data.pop("file_size", None)
        validated_data.pop("content_type", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Remove temporary upload fields before updating the document row."""
        validated_data.pop("file_size", None)
        validated_data.pop("content_type", None)
        return super().update(instance, validated_data)

    def _get_tenant(self):
        """Read the current tenant from serializer context or request."""
        request = self.context.get("request")
        return self.context.get("tenant") or getattr(request, "tenant", None)

    def _get_user(self):
        """Read the current user from serializer context or request."""
        request = self.context.get("request")
        return self.context.get("user") or getattr(request, "user", None)

    def _validate_upload_permission(self, user, tenant, visibility, team):
        """Raise a validation error if the user cannot upload this document."""
        membership = Membership.objects.filter(user=user, tenant=tenant).first()

        if membership is None:
            raise serializers.ValidationError("User is not a member of this tenant.")

        if membership.role == Membership.Role.OWNER:
            return

        if visibility == Document.Visibility.COMPANY:
            if membership.role != Membership.Role.ADMIN:
                raise serializers.ValidationError("Only company owners or admins can upload company-wide documents.")
            return

        allowed_team_roles = [TeamMembership.Role.CONTRIBUTOR, TeamMembership.Role.MANAGER]
        has_team_upload_permission = TeamMembership.objects.filter(
            membership=membership,
            team=team,
            role__in=allowed_team_roles,
        ).exists()

        if not has_team_upload_permission:
            raise serializers.ValidationError("User cannot upload documents to this team.")
