from django.db.models import Q
from django.views.generic import DetailView, ListView

from apps.recordings.models import Recording
from apps.tags.models import Tag


class RecordingListView(ListView):
    model = Recording
    template_name = "recordings/recording_list.html"
    context_object_name = "recordings"
    paginate_by = 10

    def get_queryset(self):
        qs = Recording.objects.all()
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
            | Q(speaker__icontains=q)
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
