from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json

from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .throttles import TenantRateThrottle
from .services import get_or_create_conversation, recent_history, send_message, build_citations
from .models import Message
from billing.services import record_usage
from documents.services import retrieve, rerank, generate_answer_stream
from django.db.models import Sum
from django.db.models.functions import TruncDate
from tenants.permissions import IsTenantAdmin


class ChatView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TenantRateThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = get_or_create_conversation(
            request.tenant, request.user, serializer.validated_data.get("conversation_id")
        )
        result = send_message(request.tenant, request.user, conversation, serializer.validated_data["query"])
        return Response(ChatResponseSerializer(result).data, status=200)


class ChatStreamView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TenantRateThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        conversation = get_or_create_conversation(
            request.tenant, request.user, serializer.validated_data.get("conversation_id")
        )
        history = recent_history(conversation)
        candidates = retrieve(request.tenant, request.user, query)
        top_chunks = rerank(query, candidates)

        def event_stream():
            full_answer = ""
            for token in generate_answer_stream(query, top_chunks, history=history):
                full_answer += token
                yield f"data: {token}\n\n"
            Message.objects.create(conversation=conversation, role=Message.Role.USER, content=query)
            Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT, content=full_answer)
            # NOTE: word-count is an approximation, unlike ChatView's real token count. Flagged, not fixed today.
            record_usage(request.tenant, tokens_used=len(full_answer.split()))

            meta = {
                "conversation_id": str(conversation.id),
                "citations": build_citations(top_chunks),
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
            conversation__tenant=request.tenant, role=Message.Role.ASSISTANT, cost_usd__isnull=False,
        )
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)
        rows = (
            qs.annotate(day=TruncDate("created_at"))
              .values("day")
              .annotate(total_cost_usd=Sum("cost_usd"), total_input_tokens=Sum("input_tokens"),
                        total_output_tokens=Sum("output_tokens"), message_count=Sum(1))
              .order_by("day")
        )
        return Response(list(rows))