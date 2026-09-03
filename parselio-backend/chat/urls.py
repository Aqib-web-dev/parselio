from django.urls import path
from .views import ChatStreamView, ChatView, UsageSummaryView

urlpatterns = [
    path("", ChatView.as_view(), name="chat"),
    path("stream/", ChatStreamView.as_view(), name="chat-stream"), 
    path("admin/usage-summary/", UsageSummaryView.as_view(), name="usage-summary"),
]