from django.urls import path

from . import views

urlpatterns = [
    path("", views.WritingListView.as_view(), name="writing-list"),
    path("create/", views.WritingCreateView.as_view(), name="writing-create"),
    path("all/", views.WritingArchiveView.as_view(), name="writing-archive"),
    path("<int:pk>/", views.WritingDetailView.as_view(), name="writing-detail"),
    path("<int:pk>/api/", views.WritingDetailAPIView.as_view(), name="writing-detail-api"),
]
