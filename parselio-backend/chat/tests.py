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

    # Day 27 refactor: retrieve/rerank/generate_answer now live in chat.services
    # (imported there from documents.services), not chat.views — patch the new home.
    with mock.patch("chat.services.retrieve", return_value=[chunk]), \
         mock.patch("chat.services.rerank", return_value=[chunk]), \
         mock.patch("chat.services.generate_answer", return_value=("Mocked answer.", mocked_usage)):

        response = client.post("/api/v1/chat/", {"query": "What is the leave policy?"}, format="json")

    assert response.status_code == 200
    assert response.data["answer"] == "Mocked answer."
    assert response.data["citations"][0]["chunk_id"] == str(chunk.id)


def test_chat_rejects_conversation_id_from_another_tenant():
    """
    Day 27 fix: chat/services.py's get_or_create_conversation now catches
    Conversation.DoesNotExist and raises DRF's NotFound, so a cross-tenant
    conversation_id returns a clean 404 instead of crashing with an
    uncaught exception. No cross-tenant data is ever returned either way —
    this test now confirms the correct HTTP-level behavior too.
    """
    victim_membership = MembershipFactory()
    attacker_membership = MembershipFactory()

    victim_conversation = Conversation.objects.create(
        tenant=victim_membership.tenant, user=victim_membership.user
    )

    attacker_client = authenticated_client(attacker_membership.user)

    response = attacker_client.post(
        "/api/v1/chat/",
        {"query": "anything", "conversation_id": str(victim_conversation.id)},
        format="json",
    )

    assert response.status_code == 404
