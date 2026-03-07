from django.urls import path

from . import views

urlpatterns = [
    path("", views.RecordingListView.as_view(), name="recording-list"),
    path("add/", views.RecordingCreateView.as_view(), name="recording-create"),
    path("all/", views.RecordingArchiveView.as_view(), name="recording-archive"),
    path("<int:pk>/", views.RecordingDetailView.as_view(), name="recording-detail"),
    path("<int:pk>/edit/", views.RecordingUpdateView.as_view(), name="recording-update"),
    path("<int:pk>/delete/", views.RecordingDeleteView.as_view(), name="recording-delete"),
    path("<int:pk>/restore/", views.RecordingRestoreView.as_view(), name="recording-restore"),
    path("<int:pk>/permanent-delete/", views.RecordingPermanentDeleteView.as_view(), name="recording-permanent-delete"),
    path("search/", views.RecordingSearchView.as_view(), name="recording-search"),
]
