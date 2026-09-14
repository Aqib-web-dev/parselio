from rest_framework.exceptions import NotFound
from billing.services import record_usage
from documents.services import retrieve, rerank, generate_answer, generate_answer_stream
from documents.pricing import calculate_cost
from .models import Message

from .models import Conversation

MAX_HISTORY_MESSAGES = 10


def get_or_create_conversation(tenant, user, conversation_id):
    """Fetch an existing conversation scoped to this tenant/user, or start a new one."""
    if conversation_id:
        try:
            return Conversation.objects.get(id=conversation_id, tenant=tenant, user=user)
        except Conversation.DoesNotExist:
            raise NotFound("Conversation not found.")
    return Conversation.objects.create(tenant=tenant, user=user)


def recent_history(conversation):
    """Last MAX_HISTORY_MESSAGES messages in this conversation, oldest first."""
    return list(conversation.messages.order_by("-created_at")[:MAX_HISTORY_MESSAGES])[::-1]

def build_citations(chunks):
    """Turn a list of ranked DocumentChunk rows into the citation dicts the API returns."""
    return [
        {"number": i + 1, "chunk_id": c.id, "document_id": c.document_id, "text": c.text}
        for i, c in enumerate(chunks)
    ]


def send_message(tenant, user, conversation, query):
    """Run the full RAG pipeline for one chat message and persist the result."""
    history = recent_history(conversation)
    candidates = retrieve(tenant, user, query)
    top_chunks = rerank(query, candidates)
    answer_text, usage = generate_answer(query, top_chunks, history=history)
    cost = calculate_cost(usage["model"], usage["input_tokens"], usage["output_tokens"])

    Message.objects.create(conversation=conversation, role=Message.Role.USER, content=query)
    Message.objects.create(
        conversation=conversation, role=Message.Role.ASSISTANT, content=answer_text,
        input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"], cost_usd=cost,
    )
    record_usage(tenant, tokens_used=usage["input_tokens"] + usage["output_tokens"])

    return {
        "answer": answer_text,
        "conversation_id": conversation.id,
        "citations": build_citations(top_chunks),
    }