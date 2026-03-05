from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from .models import LiveStream


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class LiveStreamListView(ListView):
    model = LiveStream
    template_name = "livestream/livestream_list.html"
    context_object_name = "livestreams"

    def get_queryset(self):
        return LiveStream.objects.filter(is_active=True)


class LiveStreamStartView(StaffRequiredMixin, TemplateView):
    template_name = "livestream/livestream_start.html"

    def post(self, request, *args, **kwargs):
        title = request.POST.get("title", "").strip()
        if not title:
            now = timezone.now()
            title = f"{now.strftime('%B')} {now.day}, {now.year} Live Stream"
        stream = LiveStream.objects.create(title=title, created_by=request.user)
        return redirect("livestream-broadcast", stream_key=stream.stream_key)


class LiveStreamBroadcastView(StaffRequiredMixin, DetailView):
    model = LiveStream
    template_name = "livestream/livestream_broadcast.html"
    context_object_name = "livestream"
    slug_field = "stream_key"
    slug_url_kwarg = "stream_key"

    def get_queryset(self):
        qs = LiveStream.objects.filter(is_active=True)
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        return qs


class LiveStreamListenView(DetailView):
    model = LiveStream
    template_name = "livestream/livestream_listen.html"
    context_object_name = "livestream"
    slug_field = "stream_key"
    slug_url_kwarg = "stream_key"


class LiveStreamStatusAPIView(View):
    """JSON endpoint that returns whether a stream is still active.
    Listeners poll this every 5 seconds to detect when the stream ends."""

    def get(self, request, stream_key):
        stream = get_object_or_404(LiveStream, stream_key=stream_key)
        return JsonResponse({
            "is_active": stream.is_active,
            "title": stream.title,
        })

    def post(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["GET"])


class LiveStreamStopView(StaffRequiredMixin, View):
    def post(self, request, stream_key):
        qs = LiveStream.objects.filter(is_active=True)
        if not request.user.is_superuser:
            qs = qs.filter(created_by=request.user)
        stream = get_object_or_404(qs, stream_key=stream_key)
        stream.is_active = False
        stream.ended_at = timezone.now()
        stream.save()
        return redirect("livestream-list")

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
