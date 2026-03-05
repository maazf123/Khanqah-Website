import uuid

from django.conf import settings
from django.db import models


class LiveStream(models.Model):
    title = models.CharField(max_length=255)
    stream_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.title} ({'Live' if self.is_active else 'Ended'})"
