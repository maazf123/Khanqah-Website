import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from apps.tags.models import Tag

from .models import Writing


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self):
        return self.request.user.is_staff


class WritingListView(ListView):
    model = Writing
    template_name = "writings/writing_list.html"
    context_object_name = "writings"

    def get_queryset(self):
        qs = Writing.objects.filter(is_archived=False)
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context["featured_writing"] = qs.first()
        context["recent_writings"] = qs[1:6]
        context["tags"] = Tag.objects.all()
        context["current_tag"] = self.request.GET.get("tag")
        return context


class WritingArchiveView(ListView):
    model = Writing
    template_name = "writings/writing_archive.html"
    context_object_name = "writings"
    paginate_by = 12

    def get_queryset(self):
        qs = Writing.objects.filter(is_archived=False)
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tags"] = Tag.objects.all()
        context["current_tag"] = self.request.GET.get("tag")
        return context


class WritingSearchView(ListView):
    model = Writing
    template_name = "writings/writing_archive.html"
    context_object_name = "writings"
    paginate_by = 12

    def get_queryset(self):
        q = self.request.GET.get("q", "").strip()
        if not q:
            return Writing.objects.none()
        qs = Writing.objects.filter(
            Q(title__icontains=q) | Q(body__icontains=q),
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


class WritingDetailView(DetailView):
    model = Writing
    template_name = "writings/writing_detail.html"
    context_object_name = "writing"

    def get_queryset(self):
        return Writing.objects.filter(is_archived=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tags"] = Tag.objects.all()
        return context


class WritingDetailAPIView(View):
    def get(self, request, pk):
        try:
            writing = Writing.objects.get(pk=pk, is_archived=False)
        except Writing.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)
        return JsonResponse({
            "id": writing.pk,
            "title": writing.title,
            "body": writing.body,
            "published_date": writing.published_date.strftime("%B %d, %Y"),
            "tags": list(writing.tags.values_list("name", flat=True)),
        })


class WritingCreateView(StaffRequiredMixin, CreateView):
    model = Writing
    template_name = "writings/writing_form.html"
    fields = ["title", "body", "tags"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["tags"].required = False
        return form

    def form_valid(self, form):
        from django.utils import timezone
        form.instance.published_date = timezone.now().date()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("writing-list")


class WritingUpdateView(StaffRequiredMixin, View):
    def post(self, request, pk):
        writing = get_object_or_404(Writing, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"ok": False, "error": "Invalid JSON."})

        if "title" in data:
            if not data["title"].strip():
                return JsonResponse({"ok": False, "error": "Title is required."})
            writing.title = data["title"].strip()
        if "body" in data:
            if not data["body"].strip():
                return JsonResponse({"ok": False, "error": "Body is required."})
            writing.body = data["body"]
        writing.save()

        if "tags" in data:
            writing.tags.set(data["tags"])

        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class WritingDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        writing = get_object_or_404(Writing, pk=pk, is_archived=False)
        writing.is_archived = True
        writing.archived_at = timezone.now()
        writing.save()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class WritingRestoreView(StaffRequiredMixin, View):
    def post(self, request, pk):
        writing = get_object_or_404(Writing, pk=pk, is_archived=True)
        writing.is_archived = False
        writing.archived_at = None
        writing.save()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class WritingPermanentDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        writing = get_object_or_404(Writing, pk=pk, is_archived=True)
        writing.delete()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
