import datetime
import os
import shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.recordings.models import Recording
from apps.tags.models import Tag


SEED_RECORDINGS = [
    {
        "title": "Al Hamīd Foundation's live audio",
        "description": "A live session covering spiritual topics and reminders for the community.",
        "speaker": "Al Hamīd Foundation",
        "recording_date": datetime.date(2025, 12, 1),
        "source_file": "recording_2966513.mp3",
        "tags": ["Tassawuf"],
    },
    {
        "title": "The Bliss of the Desert",
        "description": "Reflections on the spiritual lessons drawn from solitude and the desert experience of the pious predecessors.",
        "speaker": "Al Hamīd Foundation",
        "recording_date": datetime.date(2025, 10, 20),
        "source_file": "recording_2930164.mp3",
        "tags": ["Tassawuf", "Tazkiyah"],
    },
    {
        "title": "Remembering the Garden",
        "description": "A discourse on keeping the hereafter in focus and striving for Jannah through daily actions.",
        "speaker": "Al Hamīd Foundation",
        "recording_date": datetime.date(2025, 10, 20),
        "source_file": "recording_2930163.mp3",
        "tags": ["Tazkiyah"],
    },
    {
        "title": "Sālik & Non Sālik",
        "description": "Understanding the difference between one who treads the spiritual path and one who does not.",
        "speaker": "Al Hamīd Foundation",
        "recording_date": datetime.date(2025, 10, 9),
        "source_file": "recording_2919375.mp3",
        "tags": ["Tassawuf", "Tazkiyah"],
    },
    {
        "title": "Being Two Faced",
        "description": "A powerful reminder on the dangers of hypocrisy and the importance of sincerity in faith.",
        "speaker": "Al Hamīd Foundation",
        "recording_date": datetime.date(2025, 9, 22),
        "source_file": "recording_2904279.mp3",
        "tags": ["Tazkiyah"],
    },
    {
        "title": "Is Islām a Part of My Life?",
        "description": "A thought-provoking session challenging listeners to evaluate how central the deen is in their daily lives.",
        "speaker": "Al Hamīd Foundation",
        "recording_date": datetime.date(2025, 8, 19),
        "source_file": "recording_2873505.mp3",
        "tags": ["Tassawuf"],
    },
]


class Command(BaseCommand):
    help = "Seed the database with sample data"

    def handle(self, *args, **options):
        # Create superuser if needed
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                email="admin@khanqah.local",
                password="admin123",
            )
            self.stdout.write("Created admin user.")

        # Create tags
        tag_names = [
            "Tassawuf", "Tazkiyah", "Fiqh", "Seerah",
            "Hadith", "Ramadan", "Dhikr", "Friday Bayaan",
        ]
        tags = {}
        for name in tag_names:
            tags[name], _ = Tag.objects.get_or_create(name=name)

        # Clear old recordings
        Recording.objects.all().delete()

        # Seed recordings
        media_recordings_dir = os.path.join(settings.MEDIA_ROOT, "recordings")
        os.makedirs(media_recordings_dir, exist_ok=True)

        for data in SEED_RECORDINGS:
            source = os.path.join(settings.MEDIA_ROOT, "recordings", data["source_file"])
            if not os.path.exists(source):
                self.stderr.write(f"  Audio file not found: {source}")
                continue

            # The file is already in media/recordings/, just point the model to it
            relative_path = f"recordings/{data['source_file']}"

            recording = Recording.objects.create(
                title=data["title"],
                description=data["description"],
                speaker=data["speaker"],
                recording_date=data["recording_date"],
                audio_file=relative_path,
            )
            for tag_name in data["tags"]:
                if tag_name in tags:
                    recording.tags.add(tags[tag_name])

            self.stdout.write(f"  Created: {recording.title}")

        self.stdout.write(self.style.SUCCESS(f"Seed complete: {Recording.objects.count()} recordings."))
