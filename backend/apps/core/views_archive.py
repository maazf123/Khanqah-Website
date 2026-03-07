from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from apps.recordings.models import Recording
from apps.writings.models import Writing


class ArchivedItemsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "core/archived_items.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["archived_recordings"] = Recording.objects.filter(is_archived=True).order_by("-archived_at")
        context["archived_writings"] = Writing.objects.filter(is_archived=True).order_by("-archived_at")
        return context
