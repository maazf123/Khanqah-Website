from django.urls import path

from . import views

urlpatterns = [
    path("", views.WritingListView.as_view(), name="writing-list"),
    path("create/", views.WritingCreateView.as_view(), name="writing-create"),
    path("all/", views.WritingArchiveView.as_view(), name="writing-archive"),
    path("<int:pk>/", views.WritingDetailView.as_view(), name="writing-detail"),
    path("<int:pk>/edit/", views.WritingUpdateView.as_view(), name="writing-update"),
    path("<int:pk>/delete/", views.WritingDeleteView.as_view(), name="writing-delete"),
    path("<int:pk>/restore/", views.WritingRestoreView.as_view(), name="writing-restore"),
    path("<int:pk>/permanent-delete/", views.WritingPermanentDeleteView.as_view(), name="writing-permanent-delete"),
    path("<int:pk>/api/", views.WritingDetailAPIView.as_view(), name="writing-detail-api"),
]
