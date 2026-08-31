from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField(min_length=1, max_length=2000)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)


class CitationSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    chunk_id = serializers.UUIDField()
    document_id = serializers.UUIDField()
    text = serializers.CharField()


class ChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    conversation_id = serializers.UUIDField()
    citations = CitationSerializer(many=True)