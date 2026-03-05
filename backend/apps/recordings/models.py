from django.core.exceptions import ValidationError
from django.db import models


class Recording(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    speaker = models.CharField(max_length=255)
    audio_file = models.FileField(upload_to="recordings/")
    recording_date = models.DateField()
    tags = models.ManyToManyField("tags.Tag", blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.title} - {self.speaker}"

    def clean(self):
        super().clean()
        if self.pk and self.tags.count() > 10:
            raise ValidationError("A recording can have at most 10 tags.")
