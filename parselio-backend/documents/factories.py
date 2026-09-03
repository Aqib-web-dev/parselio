import factory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.serializers import ParselioTokenObtainPairSerializer
from tenants.models import Membership, Team, Tenant
from documents.models import Document, DocumentChunk


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"Acme Test Co {n}")
    slug = factory.Sequence(lambda n: f"acme-test-{n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"testuser{n}")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    tenant = factory.SubFactory(TenantFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f"Team {n}")
    slug = factory.Sequence(lambda n: f"team-{n}")


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    tenant = factory.SubFactory(TenantFactory)
    title = factory.Sequence(lambda n: f"Test Document {n}")
    original_filename = "test.txt"
    visibility = Document.Visibility.COMPANY
    team = None

    class Params:
        team_visibility = factory.Trait(
            visibility=Document.Visibility.TEAM,
            team=factory.SubFactory(TeamFactory),
        )


class DocumentChunkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentChunk

    document = factory.SubFactory(DocumentFactory)
    tenant = factory.SelfAttribute("document.tenant")
    chunk_index = factory.Sequence(lambda n: n)
    text = factory.Sequence(lambda n: f"Test chunk text {n}")
    embedding = factory.LazyFunction(lambda: [0.0] * 768)


def authenticated_client(user):
    """APIClient carrying a real JWT so ParselioJWTAuthentication actually runs."""
    token = ParselioTokenObtainPairSerializer.get_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client
