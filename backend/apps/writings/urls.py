from django.urls import path

from . import views

urlpatterns = [
    path("", views.WritingListView.as_view(), name="writing-list"),
    path("create/", views.WritingCreateView.as_view(), name="writing-create"),
    path("<int:pk>/", views.WritingDetailView.as_view(), name="writing-detail"),
]
