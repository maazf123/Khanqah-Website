from django.urls import path

from . import views

urlpatterns = [
    path("", views.RecordingListView.as_view(), name="recording-list"),
    path("recordings/<int:pk>/", views.RecordingDetailView.as_view(), name="recording-detail"),
    path("search/", views.RecordingSearchView.as_view(), name="recording-search"),
]
