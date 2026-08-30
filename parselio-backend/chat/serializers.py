from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField(min_length=1, max_length=2000)


class CitationSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    chunk_id = serializers.UUIDField()
    document_id = serializers.UUIDField()
    text = serializers.CharField()


class ChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    citations = CitationSerializer(many=True)