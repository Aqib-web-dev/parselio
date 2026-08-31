from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from billing.services import record_usage
from documents.services import retrieve, rerank, generate_answer
from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .throttles import TenantRateThrottle


class ChatView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TenantRateThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]

        candidates = retrieve(request.tenant, request.user, query)
        top_chunks = rerank(query, candidates)
        answer_text = generate_answer(query, top_chunks)
        
        record_usage(request.tenant, tokens_used=len(answer_text.split()))  # NEW

        response_data = {
            "answer": answer_text,
            "citations": [
                {
                    "number": i + 1,
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "text": c.text,
                }
                for i, c in enumerate(top_chunks)
            ],
        }
        return Response(ChatResponseSerializer(response_data).data, status=200)
