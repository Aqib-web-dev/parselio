import django_filters
from documents.models import Document


class DocumentFilter(django_filters.FilterSet):
    created_at = django_filters.DateFromToRangeFilter()

    class Meta:
        model = Document
        fields = ["status", "created_at"]