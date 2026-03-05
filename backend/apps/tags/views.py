from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from .models import Tag


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self):
        return self.request.user.is_staff


class TagListView(StaffRequiredMixin, View):
    """Returns all tags as JSON for the modal."""

    def get(self, request):
        tags = Tag.objects.all()
        return JsonResponse({
            "tags": [
                {"id": t.pk, "name": t.name}
                for t in tags
            ]
        })


class TagCreateView(StaffRequiredMixin, View):
    def post(self, request):
        name = request.POST.get("name", "").strip()
        if not name:
            return JsonResponse({"ok": False, "error": "Name is required."})
        if Tag.objects.filter(name=name).exists():
            return JsonResponse({"ok": False, "error": "Tag already exists."})
        tag = Tag.objects.create(name=name)
        return JsonResponse({
            "ok": True,
            "tag": {"id": tag.pk, "name": tag.name},
        })

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class TagDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        tag = get_object_or_404(Tag, pk=pk)
        tag.delete()
        return JsonResponse({"ok": True})

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
