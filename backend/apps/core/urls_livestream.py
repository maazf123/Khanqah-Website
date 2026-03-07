from django.urls import path

from . import views_livestream as views

urlpatterns = [
    path("", views.LiveStreamListView.as_view(), name="livestream-list"),
    path("start/", views.LiveStreamStartView.as_view(), name="livestream-start"),
    path("<uuid:stream_key>/broadcast/", views.LiveStreamBroadcastView.as_view(), name="livestream-broadcast"),
    path("<uuid:stream_key>/listen/", views.LiveStreamListenView.as_view(), name="livestream-listen"),
    path("<uuid:stream_key>/stop/", views.LiveStreamStopView.as_view(), name="livestream-stop"),
    path("<uuid:stream_key>/status/", views.LiveStreamStatusAPIView.as_view(), name="livestream-status"),
    path("<uuid:stream_key>/archive/", views.LiveStreamArchiveView.as_view(), name="livestream-archive"),
]
