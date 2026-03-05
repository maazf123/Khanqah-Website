from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from apps.tags.models import Tag
from apps.recordings.models import Recording
import datetime

class Command(BaseCommand):
    help = "Seed the database with sample data"

    def handle(self, *args, **options):
        # Check if already seeded (admin user exists)
        if User.objects.filter(username="admin").exists():
            self.stdout.write("Seed data already exists. Skipping.")
            return

        # Create superuser
        User.objects.create_superuser(
            username="admin",
            email="admin@khanqah.local",
            password="admin123",
        )

        # Create tags
        tag_names = [
            "Prayer", "Taqwa", "Ramadan", "Hadith",
            "Fiqh", "Tafsir", "Seerah", "Aqeedah",
        ]
        tags = {}
        for name in tag_names:
            tags[name] = Tag.objects.create(name=name)

        # Create sample recordings
        recordings_data = [
            {
                "title": "The Importance of Salah",
                "description": "A comprehensive talk on the significance of the five daily prayers.",
                "speaker": "Mufti Ahmad",
                "recording_date": datetime.date(2025, 1, 15),
                "tags": ["Prayer", "Taqwa"],
            },
            {
                "title": "Preparing for Ramadan",
                "description": "How to spiritually and physically prepare for the blessed month.",
                "speaker": "Shaykh Bilal",
                "recording_date": datetime.date(2025, 2, 20),
                "tags": ["Ramadan", "Taqwa", "Fiqh"],
            },
            {
                "title": "Stories from the Seerah",
                "description": "Lessons from the life of the Prophet (peace be upon him).",
                "speaker": "Mufti Ahmad",
                "recording_date": datetime.date(2025, 3, 10),
                "tags": ["Seerah", "Hadith"],
            },
        ]

        for data in recordings_data:
            tag_list = data.pop("tags")
            # Create a small dummy audio file
            audio_content = ContentFile(b"\x00" * 256)
            audio_content.name = f"{data['title'].lower().replace(' ', '_')}.mp3"
            recording = Recording.objects.create(
                audio_file=audio_content,
                **data,
            )
            for tag_name in tag_list:
                recording.tags.add(tags[tag_name])

        self.stdout.write("Seed data created successfully.")
