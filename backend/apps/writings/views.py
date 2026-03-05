from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse
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
    paginate_by = 12

    def get_queryset(self):
        qs = Writing.objects.all()
        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tags"] = Tag.objects.all()
        context["current_tag"] = self.request.GET.get("tag")
        return context


class WritingDetailView(DetailView):
    model = Writing
    template_name = "writings/writing_detail.html"
    context_object_name = "writing"


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
