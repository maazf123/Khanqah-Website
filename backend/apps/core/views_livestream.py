import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.recordings.models import Recording

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
        # Check ownership: the stream must belong to this user (or user is superuser)
        qs = LiveStream.objects.all()
        if not request.user.is_superuser:
            qs = qs.filter(created_by=request.user)
        stream = get_object_or_404(qs, stream_key=stream_key)

        # Only update if still active (gracefully handle double-stop / race)
        if stream.is_active:
            stream.is_active = False
            stream.ended_at = timezone.now()
            stream.save()

        # Return JSON for AJAX requests, redirect for regular form submits
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        return redirect("livestream-list")

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class LiveStreamArchiveView(StaffRequiredMixin, View):
    """Create a Recording from a finished LiveStream's metadata."""

    def post(self, request, stream_key):
        stream = get_object_or_404(LiveStream, stream_key=stream_key)
        if stream.is_active:
            return JsonResponse({"ok": False, "error": "Stream is still active."})

        # Determine mode: "post" (public) or "archive" (hidden). Default to "archive".
        mode = "archive"
        if request.content_type and "json" in request.content_type:
            try:
                body = json.loads(request.body)
                mode = body.get("mode", "archive")
            except (json.JSONDecodeError, ValueError):
                pass

        speaker = request.user.get_full_name() or request.user.username
        recording = Recording.objects.create(
            title=stream.title,
            speaker=speaker,
            recording_date=timezone.now().date(),
            description=f"Archived from live stream on {stream.started_at.strftime('%B %d, %Y')}",
        )

        if mode == "archive":
            recording.is_archived = True
            recording.archived_at = timezone.now()
            recording.save()

        return JsonResponse({"ok": True, "recording_id": recording.pk})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
