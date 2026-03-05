from django.urls import path

from . import views

urlpatterns = [
    path("", views.RecordingListView.as_view(), name="recording-list"),
    path("add/", views.RecordingCreateView.as_view(), name="recording-create"),
    path("<int:pk>/", views.RecordingDetailView.as_view(), name="recording-detail"),
    path("search/", views.RecordingSearchView.as_view(), name="recording-search"),
]
