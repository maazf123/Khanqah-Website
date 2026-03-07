import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from apps.recordings.models import Recording
from apps.tags.models import Tag


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self):
        return self.request.user.is_staff


class RecordingListView(ListView):
    model = Recording
    template_name = "recordings/recording_list.html"
    context_object_name = "recordings"

    def get_queryset(self):
        return Recording.objects.filter(is_archived=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context["featured_recording"] = qs.first()
        context["recent_recordings"] = qs[1:4]
        context["tags"] = Tag.objects.all()
        return context


class RecordingArchiveView(ListView):
    model = Recording
    template_name = "recordings/recording_archive.html"
    context_object_name = "recordings"
    paginate_by = 10

    def get_queryset(self):
        qs = Recording.objects.filter(is_archived=False)
        tag_slug = self.request.GET.get("tag")
        speaker = self.request.GET.get("speaker")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        if speaker:
            qs = qs.filter(speaker=speaker)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tags"] = Tag.objects.all()
        context["current_tag"] = self.request.GET.get("tag")
        context["current_speaker"] = self.request.GET.get("speaker")
        return context


class RecordingDetailView(DetailView):
    model = Recording
    template_name = "recordings/recording_detail.html"
    context_object_name = "recording"

    def get_queryset(self):
        return Recording.objects.filter(is_archived=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tags"] = Tag.objects.all()
        return context


class RecordingSearchView(ListView):
    model = Recording
    template_name = "recordings/recording_search.html"
    context_object_name = "recordings"
    paginate_by = 10

    def get_queryset(self):
        q = self.request.GET.get("q", "").strip()
        if not q:
            return Recording.objects.none()
        qs = Recording.objects.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(speaker__icontains=q),
            is_archived=False,
        ).distinct()
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["tags"] = Tag.objects.all()
        context["current_tag"] = self.request.GET.get("tag") or None
        return context


class RecordingCreateView(StaffRequiredMixin, CreateView):
    model = Recording
    template_name = "recordings/recording_form.html"
    fields = ["title", "description", "audio_file", "tags"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["description"].required = False
        form.fields["tags"].required = False
        form.fields["audio_file"].required = True
        return form

    def form_valid(self, form):
        from django.utils import timezone
        form.instance.recording_date = timezone.now().date()
        form.instance.speaker = self.request.user.get_full_name() or self.request.user.username
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("recording-list")


class RecordingUpdateView(StaffRequiredMixin, View):
    def post(self, request, pk):
        recording = get_object_or_404(Recording, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"ok": False, "error": "Invalid JSON."})

        if "title" in data:
            if not data["title"].strip():
                return JsonResponse({"ok": False, "error": "Title is required."})
            recording.title = data["title"].strip()
        if "description" in data:
            recording.description = data["description"]
        recording.save()

        if "tags" in data:
            recording.tags.set(data["tags"])

        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class RecordingDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        recording = get_object_or_404(Recording, pk=pk, is_archived=False)
        recording.is_archived = True
        recording.archived_at = timezone.now()
        recording.save()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class RecordingRestoreView(StaffRequiredMixin, View):
    def post(self, request, pk):
        recording = get_object_or_404(Recording, pk=pk, is_archived=True)
        recording.is_archived = False
        recording.archived_at = None
        recording.save()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class RecordingPermanentDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        recording = get_object_or_404(Recording, pk=pk, is_archived=True)
        recording.delete()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
