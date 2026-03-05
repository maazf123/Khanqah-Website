from django.urls import path

from . import views

urlpatterns = [
    path("", views.TagListView.as_view(), name="tag-list"),
    path("create/", views.TagCreateView.as_view(), name="tag-create"),
    path("<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag-delete"),
]
