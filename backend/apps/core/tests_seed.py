from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from apps.recordings.models import Recording
from apps.tags.models import Tag

EXPECTED_TAG_NAMES = {
    "Prayer",
    "Taqwa",
    "Ramadan",
    "Hadith",
    "Fiqh",
    "Tafsir",
    "Seerah",
    "Aqeedah",
}


class SeedCommandSuccessTests(TestCase):
    """Tests for successful execution of the seed management command."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.out = StringIO()
        call_command("seed", stdout=cls.out)

    # 1. Running seed creates a superuser with username "admin"
    def test_creates_admin_superuser(self):
        self.assertTrue(User.objects.filter(username="admin").exists())

    # 2. The admin user has is_superuser=True and is_staff=True
    def test_admin_is_superuser_and_staff(self):
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)

    # 3. The admin user's password is "admin123"
    def test_admin_password(self):
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.check_password("admin123"))

    # 4. Running seed creates exactly 8 tags
    def test_creates_eight_tags(self):
        self.assertEqual(Tag.objects.count(), 8)

    # 5. All expected tag names exist after seeding
    def test_all_expected_tag_names_exist(self):
        actual_names = set(Tag.objects.values_list("name", flat=True))
        self.assertEqual(actual_names, EXPECTED_TAG_NAMES)

    # 6. Running seed creates exactly 3 recordings
    def test_creates_three_recordings(self):
        self.assertEqual(Recording.objects.count(), 3)

    # 7. Each recording has at least 1 tag
    def test_each_recording_has_at_least_one_tag(self):
        for recording in Recording.objects.all():
            self.assertGreaterEqual(
                recording.tags.count(),
                1,
                f"Recording '{recording.title}' has no tags.",
            )

    # 8. Each recording has an audio file set
    def test_each_recording_has_audio_file(self):
        for recording in Recording.objects.all():
            self.assertTrue(
                recording.audio_file,
                f"Recording '{recording.title}' has no audio file.",
            )

    # 9. Command outputs "Seed data created successfully."
    def test_output_success_message(self):
        self.assertIn("Seed data created successfully.", self.out.getvalue())


class SeedCommandIdempotentTests(TestCase):
    """Tests for idempotent behavior when seed is run multiple times."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.out_first = StringIO()
        cls.out_second = StringIO()
        call_command("seed", stdout=cls.out_first)
        call_command("seed", stdout=cls.out_second)

    # 10. Running seed twice does not create duplicate data
    def test_no_duplicate_data(self):
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
        self.assertEqual(Tag.objects.count(), 8)
        self.assertEqual(Recording.objects.count(), 3)

    # 11. Second run outputs "Seed data already exists. Skipping."
    def test_second_run_skip_message(self):
        self.assertIn(
            "Seed data already exists. Skipping.", self.out_second.getvalue()
        )

    # 12. After second run, still only 1 admin user, 8 tags, 3 recordings
    def test_counts_unchanged_after_second_run(self):
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
        self.assertEqual(Tag.objects.count(), 8)
        self.assertEqual(Recording.objects.count(), 3)


class SeedCommandEdgeCaseTests(TestCase):
    """Edge-case tests for the seed management command."""

    # 13. If admin user exists but tags don't, still skips
    def test_skips_when_admin_exists_but_no_tags(self):
        User.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@khanqah.local",
        )
        self.assertEqual(Tag.objects.count(), 0)

        out = StringIO()
        call_command("seed", stdout=out)

        self.assertIn("Seed data already exists. Skipping.", out.getvalue())
        self.assertEqual(Tag.objects.count(), 0)
        self.assertEqual(Recording.objects.count(), 0)
