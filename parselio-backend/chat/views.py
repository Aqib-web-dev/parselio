import json

from django.db.models import query
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from billing.services import record_usage
from documents.services import retrieve, rerank, generate_answer, generate_answer_stream
from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .throttles import TenantRateThrottle
from .models import Conversation, Message
from documents.pricing import calculate_cost
from django.db.models import Sum
from django.db.models.functions import TruncDate
from tenants.permissions import IsTenantAdmin

MAX_HISTORY_MESSAGES = 10


def _get_or_create_conversation(request, conversation_id):
    if conversation_id:
        return Conversation.objects.get(id=conversation_id, tenant=request.tenant, user=request.user)
    return Conversation.objects.create(tenant=request.tenant, user=request.user)


def _recent_history(conversation):
    return list(conversation.messages.order_by("-created_at")[:MAX_HISTORY_MESSAGES])[::-1]


class ChatView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TenantRateThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        conversation = _get_or_create_conversation(request, serializer.validated_data.get("conversation_id"))
        history = _recent_history(conversation)

        candidates = retrieve(request.tenant, request.user, query)
        top_chunks = rerank(query, candidates)
        answer_text, usage = generate_answer(query, top_chunks, history=history)
        cost = calculate_cost(usage["model"], usage["input_tokens"], usage["output_tokens"])

        Message.objects.create(conversation=conversation, role=Message.Role.USER, content=query)
        Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT, content=answer_text,
        input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"], cost_usd=cost,
        )
        record_usage(request.tenant, tokens_used=usage["input_tokens"] + usage["output_tokens"])

        response_data = {
            "answer": answer_text,
            "conversation_id": conversation.id,
            "citations": [
                {"number": i + 1, "chunk_id": c.id, "document_id": c.document_id, "text": c.text}
                for i, c in enumerate(top_chunks)
            ],
        }
        return Response(ChatResponseSerializer(response_data).data, status=200)

class ChatStreamView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TenantRateThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        conversation = _get_or_create_conversation(request, serializer.validated_data.get("conversation_id"))
        history = _recent_history(conversation)

        candidates = retrieve(request.tenant, request.user, query)
        top_chunks = rerank(query, candidates)

        def event_stream():
            full_answer = ""
            for token in generate_answer_stream(query, top_chunks, history=history):
                full_answer += token
                yield f"data: {token}\n\n"
            Message.objects.create(conversation=conversation, role=Message.Role.USER, content=query)
            Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT, content=full_answer)
            record_usage(request.tenant, tokens_used=len(full_answer.split()))

            meta = {
                "conversation_id": str(conversation.id),
                "citations": [
                    {"number": i + 1, "chunk_id": str(c.id), "document_id": str(c.document_id), "text": c.text}
                    for i, c in enumerate(top_chunks)
                ],
            }
            yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
            yield "event: done\ndata: {}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

class UsageSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsTenantAdmin]

    def get(self, request):
        start = request.query_params.get("start")
        end = request.query_params.get("end")

        qs = Message.objects.filter(
            conversation__tenant=request.tenant,
            role=Message.Role.ASSISTANT,
            cost_usd__isnull=False,
        )
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)

        rows = (
            qs.annotate(day=TruncDate("created_at"))
              .values("day")
              .annotate(
                  total_cost_usd=Sum("cost_usd"),
                  total_input_tokens=Sum("input_tokens"),
                  total_output_tokens=Sum("output_tokens"),
                  message_count=Sum(1),
              )
              .order_by("day")
        )
        return Response(list(rows))