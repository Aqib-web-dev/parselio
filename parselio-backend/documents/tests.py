import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.serializers import ParselioTokenObtainPairSerializer
from documents.models import Document, DocumentChunk
from documents.serializers import DocumentSerializer, MAX_DOCUMENT_SIZE_BYTES
from tenants.models import Membership, Team, TeamMembership, Tenant
from unittest.mock import patch

from documents.tasks import process_document_upload

pytestmark = pytest.mark.django_db


def create_user(username):
    """Create a user for document permission tests."""
    return get_user_model().objects.create_user(username=username, password="testpass123")


def create_tenant(slug="acme"):
    """Create one company for tests."""
    return Tenant.objects.create(name=slug.title(), slug=slug)


def create_team(tenant, slug="legal"):
    """Create one team inside a company."""
    return Team.objects.create(tenant=tenant, name=slug.title(), slug=slug)


def create_membership(tenant, username, role=Membership.Role.MEMBER):
    """Create one user-company membership."""
    user = create_user(username)
    membership = Membership.objects.create(tenant=tenant, user=user, role=role)
    return user, membership


def authenticated_client(user):
    """Return an APIClient carrying a real JWT so ParselioJWTAuthentication runs and sets request.tenant/membership."""
    token = ParselioTokenObtainPairSerializer.get_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def document_payload(**overrides):
    """Return valid document input and allow tests to change one rule at a time."""
    payload = {
        "visibility": Document.Visibility.TEAM,
        "team": None,
        "title": "Legal Policy",
        "original_filename": "legal-policy.pdf",
        "file_key": "uploads/legal-policy.pdf",
        "file_size": 500000,
        "content_type": "application/pdf",
    }
    payload.update(overrides)
    return payload


def test_document_api_rejects_anonymous_users():
    """Anonymous users should get 401 (not authenticated) instead of reaching tenant filtering."""
    client = APIClient()
    client.raise_request_exception = False

    response = client.get(reverse("document-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_database_allows_company_wide_document_without_team():
    """Company-wide documents should be stored with no team."""
    tenant = create_tenant()

    document = Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.COMPANY,
        team=None,
        title="Company Handbook",
        original_filename="handbook.pdf",
        file_key="uploads/handbook.pdf",
    )

    assert document.team is None


def test_database_rejects_company_wide_document_with_team():
    """The database should reject company-wide documents that point to a team."""
    tenant = create_tenant()
    team = create_team(tenant)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Document.objects.create(
                tenant=tenant,
                visibility=Document.Visibility.COMPANY,
                team=team,
                title="Wrong Handbook",
                original_filename="wrong.pdf",
                file_key="uploads/wrong.pdf",
            )


def test_database_rejects_duplicate_chunk_index_inside_one_document():
    """One document should not have two chunks with the same chunk_index."""
    tenant = create_tenant()
    team = create_team(tenant)
    document = Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.TEAM,
        team=team,
        title="Legal Policy",
        original_filename="legal-policy.pdf",
        file_key="uploads/legal-policy.pdf",
    )
    DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=0, text="First chunk")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=0, text="Duplicate chunk")


def test_document_serializer_allows_owner_to_upload_team_document():
    """Company owners should be allowed to upload to any team."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert serializer.is_valid(), serializer.errors
    document = serializer.save(tenant=tenant)
    assert document.team == team
    assert not hasattr(document, "file_size")


def test_document_serializer_counts_chunks_in_output():
    """Document output should include calculated chunk_count."""
    tenant = create_tenant()
    team = create_team(tenant)
    document = Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.TEAM,
        team=team,
        title="Legal Policy",
        original_filename="legal-policy.pdf",
        file_key="uploads/legal-policy.pdf",
    )
    DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=0, text="First chunk")
    DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=1, text="Second chunk")

    data = DocumentSerializer(document).data

    assert data["chunk_count"] == 2
    assert "file_size" not in data
    assert "content_type" not in data


def test_document_serializer_rejects_file_larger_than_limit():
    """Serializer validation should reject upload metadata above the size limit."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id), file_size=MAX_DOCUMENT_SIZE_BYTES + 1),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "file_size" in serializer.errors


def test_document_serializer_rejects_unsupported_content_type():
    """Serializer validation should reject file types Parselio does not accept."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id), content_type="image/png"),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "content_type" in serializer.errors


def test_document_serializer_rejects_company_document_with_team():
    """Company-wide document input should not include a team."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(visibility=Document.Visibility.COMPANY, team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "team" in serializer.errors


def test_document_serializer_rejects_team_document_without_team():
    """Team-specific document input should include a team."""
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=None),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "team" in serializer.errors


def test_document_serializer_rejects_team_from_another_tenant():
    """A document upload should not use a team from another company."""
    tenant = create_tenant("acme")
    other_tenant = create_tenant("beta")
    other_team = create_team(other_tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(other_team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "team" in serializer.errors


def test_document_serializer_allows_contributor_to_upload_team_document():
    """Team contributors should be allowed to upload documents to their team."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, membership = create_membership(tenant, "contributor")
    TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.CONTRIBUTOR)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert serializer.is_valid(), serializer.errors


def test_document_serializer_rejects_viewer_upload_to_team_document():
    """Team viewers should not be allowed to upload documents."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, membership = create_membership(tenant, "viewer")
    TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.VIEWER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


def test_document_serializer_allows_admin_to_upload_company_document():
    """Company admins should be allowed to upload company-wide documents."""
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "admin", Membership.Role.ADMIN)

    serializer = DocumentSerializer(
        data=document_payload(visibility=Document.Visibility.COMPANY, team=None),
        context={"tenant": tenant, "user": user},
    )

    assert serializer.is_valid(), serializer.errors

def test_document_detail_rejects_cross_tenant_access():
    """A member of another tenant must get 404, not 403, on a document they don't own."""
    tenant = create_tenant("acme")
    other_tenant = create_tenant("beta")
    team = create_team(tenant)
    document = Document.objects.create(
        tenant=tenant, visibility=Document.Visibility.TEAM, team=team,
        title="Legal Policy", original_filename="legal.pdf", file_key="uploads/legal.pdf",
    )
    user, _membership = create_membership(other_tenant, "outsider")
    client = authenticated_client(user)

    response = client.get(reverse("document-detail", args=[document.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_document_upload_rejects_member_uploading_company_document():
    """A plain member (not owner/admin) must be denied a company-wide upload."""
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "regular")  # default role: MEMBER

    client = authenticated_client(user)

    response = client.post(
        reverse("document-list"),
        document_payload(visibility=Document.Visibility.COMPANY, team=""),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN

@patch("documents.views.generate_presigned_upload")
def test_upload_url_returns_presigned_url_for_valid_request(mock_presign):
    mock_presign.return_value = "https://fake-bucket.s3.amazonaws.com/fake-key?X-Amz-Signature=abc"
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "owner", role=Membership.Role.OWNER)
    client = authenticated_client(user)  # real JWT -> request.tenant/membership get set

    response = client.post(
        reverse("document-upload-url"),
        {
            "title": "Q3 Report", "original_filename": "q3.pdf",
            "content_type": "application/pdf", "file_size": 500_000,
            "visibility": "company", "team": "",
        },
    )

    assert response.status_code == 201
    assert response.data["upload_url"] == mock_presign.return_value
    mock_presign.assert_called_once()


# ---------------------------------------------------------------------------
# Day 9 — Celery background task: process_document_upload
#
# These run under pytest, where CELERY_TASK_ALWAYS_EAGER is True
# (see parselio/settings/dev.py), so calling the task runs its body inline —
# no Redis and no worker needed. We call the task function directly, which is
# the cleanest way to assert on its logic.
# ---------------------------------------------------------------------------

from documents.tasks import process_document_upload  # noqa: E402


def create_document(tenant, team, status=Document.Status.UPLOADED):
    """Create one team document in a given status, for task tests."""
    return Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.TEAM,
        team=team,
        title="Legal Policy",
        original_filename="legal-policy.pdf",
        file_key="uploads/legal-policy.pdf",
        status=status,
    )


def test_process_document_upload_moves_uploaded_document_to_ready():
    """Happy path: an uploaded document is walked all the way to ready."""
    tenant = create_tenant()
    team = create_team(tenant)
    document = create_document(tenant, team, status=Document.Status.UPLOADED)

    with patch("documents.tasks.extract_text_from_document", return_value="Some real extracted text."):
        # Stub S3 download + parse — this test asserts on the task's own status
        # transitions, not on real extraction, so it must never touch AWS.
        process_document_upload(document.id)  # eager: runs the body inline, start to finish

    document.refresh_from_db()
    assert document.status == Document.Status.READY


def test_process_document_upload_is_idempotent_on_already_processed_document():
    """Idempotency guard: re-running on a ready document is a no-op, not a re-process."""
    tenant = create_tenant()
    team = create_team(tenant)
    document = create_document(tenant, team, status=Document.Status.READY)

    process_document_upload(document.id)  # should hit the guard and return immediately

    document.refresh_from_db()
    assert document.status == Document.Status.READY  # unchanged — no redo


def test_process_document_upload_ignores_missing_document():
    """A task for a row that no longer exists must return quietly, not raise."""
    # Passing an id that doesn't exist — the task's except DoesNotExist branch
    # should swallow it and return None, so nothing blows up.
    result = process_document_upload(999_999)

    assert result is None


class _StopRetry(Exception):
    """Sentinel so the test can let `self.retry(...)` fire without Celery re-running the task."""


def test_process_document_upload_marks_failed_when_processing_raises():
    """If the processing body raises, the document must land in FAILED before retrying.

    We force the READY-setting save to blow up, and stub the task's own retry to
    raise a sentinel we catch. What we assert on is the observable outcome: the
    document is left in FAILED, and a retry was requested.
    """
    tenant = create_tenant()
    team = create_team(tenant)
    document = create_document(tenant, team, status=Document.Status.UPLOADED)

    real_save = Document.save
    call = {"n": 0}

    def flaky_save(self, *args, **kwargs):
        # 1st save = PROCESSING (ok), 2nd = READY (boom), 3rd = FAILED (ok)
        call["n"] += 1
        if call["n"] == 2:
            raise RuntimeError("simulated processing failure")
        return real_save(self, *args, **kwargs)

    # `self.retry(...)` inside the task -> raise our sentinel instead of re-running.
    retry_calls = []

    def fake_retry(*args, **kwargs):
        retry_calls.append(kwargs)
        raise _StopRetry

    with patch("documents.tasks.extract_text_from_document", return_value="Some real extracted text."), \
         patch("documents.tasks.Document.save", flaky_save), \
         patch("documents.tasks.process_document_upload.retry", side_effect=fake_retry):
        with pytest.raises(_StopRetry):
            process_document_upload(document.id)

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED  # the observable outcome
    assert len(retry_calls) == 1  # a retry was requested after the failure


@patch("documents.views.process_document_upload.delay")
def test_confirm_upload_queues_task_and_returns_202(mock_delay):
    """The confirm-upload endpoint queues the task and returns 202 Accepted."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, membership = create_membership(tenant, "contributor")
    TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.CONTRIBUTOR)
    document = create_document(tenant, team, status=Document.Status.UPLOADED)
    client = authenticated_client(user)

    response = client.post(reverse("document-confirm-upload", args=[document.id]))

    assert response.status_code == 202
    assert response.data["status"] == Document.Status.UPLOADED  # status at queue time
    mock_delay.assert_called_once_with(document.id)  # task was handed off with the id

def test_process_document_creates_chunks():
    tenant = create_tenant()
    doc = Document.objects.create(
        tenant=tenant, visibility=Document.Visibility.COMPANY,
        title="Handbook", original_filename="handbook.pdf",
        file_key="tenants/x/documents/y/handbook.pdf",
        status=Document.Status.UPLOADED,
    )
    long_text = "This is a sentence. " * 500      # ~10,000 chars → forces multiple chunks

    with patch("documents.tasks.extract_text_from_document", return_value=long_text):
        # Replace the real S3+parse call with a stub returning known text — the test never touches AWS.
        process_document_upload(str(doc.id))       # runs inline (eager mode under pytest)

    doc.refresh_from_db()
    assert doc.status == Document.Status.READY     # happy path finished
    chunks = list(doc.chunks.order_by("chunk_index"))
    assert len(chunks) > 1                         # long text produced several chunks
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))  # 0,1,2,... contiguous
    assert all(c.tenant_id == doc.tenant_id for c in chunks)            # tenant flowed onto every chunk


def test_empty_text_marks_failed():
    tenant = create_tenant()
    doc = Document.objects.create(
        tenant=tenant, visibility=Document.Visibility.COMPANY,
        title="Scan", original_filename="scan.pdf",
        file_key="k", status=Document.Status.UPLOADED,
    )
    with patch("documents.tasks.extract_text_from_document", return_value="   "):
        process_document_upload(str(doc.id))       # simulate a scanned PDF → empty extraction
    doc.refresh_from_db()
    assert doc.status == Document.Status.FAILED     # policy: empty text fails, not "ready with 0 chunks"
    assert doc.chunks.count() == 0