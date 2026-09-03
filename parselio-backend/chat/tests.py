from unittest import mock

import pytest

from documents.factories import MembershipFactory, DocumentChunkFactory, authenticated_client
from chat.models import Conversation

pytestmark = pytest.mark.django_db


def test_chat_returns_answer_with_mocked_pipeline():
    membership = MembershipFactory()
    chunk = DocumentChunkFactory(document__tenant=membership.tenant)
    client = authenticated_client(membership.user)

    mocked_usage = {"model": "groq/openai/gpt-oss-120b", "input_tokens": 10, "output_tokens": 5}

    with mock.patch("chat.views.retrieve", return_value=[chunk]), \
         mock.patch("chat.views.rerank", return_value=[chunk]), \
         mock.patch("chat.views.generate_answer", return_value=("Mocked answer.", mocked_usage)):

        response = client.post("/api/v1/chat/", {"query": "What is the leave policy?"}, format="json")

    assert response.status_code == 200
    assert response.data["answer"] == "Mocked answer."
    assert response.data["citations"][0]["chunk_id"] == str(chunk.id)


def test_chat_rejects_conversation_id_from_another_tenant():
    """
    Known gap: chat/views.py's _get_or_create_conversation does not catch
    Conversation.DoesNotExist, so a cross-tenant conversation_id currently
    crashes with an uncaught exception instead of a clean 404. No cross-tenant
    data is ever returned (isolation itself holds), but the error handling is
    rough. This test documents today's real behavior rather than hiding it.
    """
    victim_membership = MembershipFactory()
    attacker_membership = MembershipFactory()

    victim_conversation = Conversation.objects.create(
        tenant=victim_membership.tenant, user=victim_membership.user
    )

    attacker_client = authenticated_client(attacker_membership.user)

    with pytest.raises(Conversation.DoesNotExist):
        attacker_client.post(
            "/api/v1/chat/",
            {"query": "anything", "conversation_id": str(victim_conversation.id)},
            format="json",
        )
