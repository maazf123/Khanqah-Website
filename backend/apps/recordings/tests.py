import datetime

from django.contrib.admin.sites import site as admin_site
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _make_audio_file(name="test.mp3"):
    """Return a minimal SimpleUploadedFile to satisfy the FileField."""
    return SimpleUploadedFile(name, b"fake-audio-bytes", content_type="audio/mpeg")


class RecordingCRUDTests(TestCase):
    """Tests 1-5: Basic CRUD operations."""

    def test_create_recording_with_required_fields(self):
        """1. Create a recording with all required fields."""
        recording = Recording.objects.create(
            title="Friday Bayan",
            speaker="Mufti Sahab",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        self.assertIsNotNone(recording.pk)
        self.assertEqual(recording.title, "Friday Bayan")
        self.assertEqual(recording.speaker, "Mufti Sahab")
        self.assertEqual(recording.recording_date, datetime.date(2025, 1, 1))

    def test_create_recording_with_all_fields(self):
        """2. Create a recording with all fields including optional ones."""
        tag = Tag.objects.create(name="Tarbiyyah")
        recording = Recording.objects.create(
            title="Weekly Majlis",
            description="A detailed description of the majlis.",
            speaker="Hazrat Sahab",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 6, 15),
        )
        recording.tags.add(tag)
        self.assertIsNotNone(recording.pk)
        self.assertEqual(recording.description, "A detailed description of the majlis.")
        self.assertIn(tag, recording.tags.all())

    def test_str_returns_title_dash_speaker(self):
        """3. __str__ returns 'title - speaker'."""
        recording = Recording.objects.create(
            title="Morning Dhikr",
            speaker="Sheikh Ahmad",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 3, 10),
        )
        self.assertEqual(str(recording), "Morning Dhikr - Sheikh Ahmad")

    def test_default_ordering_newest_first(self):
        """4. Default ordering is by -uploaded_at (newest first)."""
        r1 = Recording.objects.create(
            title="First",
            speaker="Speaker A",
            audio_file=_make_audio_file("a.mp3"),
            recording_date=datetime.date(2025, 1, 1),
        )
        r2 = Recording.objects.create(
            title="Second",
            speaker="Speaker B",
            audio_file=_make_audio_file("b.mp3"),
            recording_date=datetime.date(2025, 1, 2),
        )
        recordings = list(Recording.objects.all())
        self.assertEqual(recordings[0], r2)
        self.assertEqual(recordings[1], r1)

    def test_uploaded_at_auto_set_on_creation(self):
        """5. uploaded_at is auto-set on creation."""
        before = timezone.now()
        recording = Recording.objects.create(
            title="Auto Timestamp",
            speaker="Speaker X",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 4, 1),
        )
        after = timezone.now()
        self.assertIsNotNone(recording.uploaded_at)
        self.assertGreaterEqual(recording.uploaded_at, before)
        self.assertLessEqual(recording.uploaded_at, after)


class RecordingFieldValidationTests(TestCase):
    """Tests 6-14: Field-level validation."""

    def test_title_required_blank_fails(self):
        """6. Title is required (blank fails validation)."""
        recording = Recording(
            title="",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            recording.full_clean()
        self.assertIn("title", ctx.exception.message_dict)

    def test_title_max_length_is_255(self):
        """7. Title max length is 255 (256 chars fails)."""
        recording = Recording(
            title="A" * 256,
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            recording.full_clean()
        self.assertIn("title", ctx.exception.message_dict)

    def test_title_exactly_255_characters_works(self):
        """8. Title at exactly 255 characters works."""
        recording = Recording(
            title="A" * 255,
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        # Should not raise
        recording.full_clean()

    def test_speaker_required_blank_fails(self):
        """9. Speaker is required (blank fails validation)."""
        recording = Recording(
            title="Some Title",
            speaker="",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            recording.full_clean()
        self.assertIn("speaker", ctx.exception.message_dict)

    def test_speaker_max_length_is_255(self):
        """10. Speaker max length is 255 (256 chars fails)."""
        recording = Recording(
            title="Title",
            speaker="S" * 256,
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            recording.full_clean()
        self.assertIn("speaker", ctx.exception.message_dict)

    def test_description_optional_blank_allowed(self):
        """11. Description is optional (blank allowed)."""
        recording = Recording(
            title="Title",
            speaker="Speaker",
            description="",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        # Should not raise
        recording.full_clean()

    def test_description_defaults_to_empty_string(self):
        """12. Description defaults to empty string."""
        recording = Recording.objects.create(
            title="Title",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        self.assertEqual(recording.description, "")

    def test_audio_file_upload_to_recordings(self):
        """13. Audio file upload_to is 'recordings/'."""
        field = Recording._meta.get_field("audio_file")
        self.assertEqual(field.upload_to, "recordings/")

    def test_recording_date_required(self):
        """14. recording_date is required."""
        recording = Recording(
            title="Title",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            recording.full_clean()
        self.assertIn("recording_date", ctx.exception.message_dict)


class RecordingTagRelationshipTests(TestCase):
    """Tests 15-21: Tag M2M relationship."""

    def test_recording_can_have_zero_tags(self):
        """15. A recording can have zero tags."""
        recording = Recording.objects.create(
            title="No Tags",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        self.assertEqual(recording.tags.count(), 0)
        # clean() should not raise
        recording.clean()

    def test_recording_can_have_one_tag(self):
        """16. A recording can have 1 tag."""
        tag = Tag.objects.create(name="Fiqh")
        recording = Recording.objects.create(
            title="One Tag",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        recording.tags.add(tag)
        self.assertEqual(recording.tags.count(), 1)
        recording.clean()

    def test_recording_can_have_up_to_10_tags(self):
        """17. A recording can have up to 10 tags."""
        tags = [Tag.objects.create(name=f"Tag{i}") for i in range(10)]
        recording = Recording.objects.create(
            title="Ten Tags",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        recording.tags.add(*tags)
        self.assertEqual(recording.tags.count(), 10)
        # clean() should not raise
        recording.clean()

    def test_11th_tag_raises_validation_error(self):
        """18. Adding an 11th tag and calling clean() raises ValidationError."""
        tags = [Tag.objects.create(name=f"Tag{i}") for i in range(11)]
        recording = Recording.objects.create(
            title="Too Many Tags",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        recording.tags.add(*tags)
        self.assertEqual(recording.tags.count(), 11)
        with self.assertRaises(ValidationError):
            recording.clean()

    def test_tag_can_be_on_multiple_recordings(self):
        """19. Tags are many-to-many (a tag can be on multiple recordings)."""
        tag = Tag.objects.create(name="Shared Tag")
        r1 = Recording.objects.create(
            title="Recording 1",
            speaker="Speaker A",
            audio_file=_make_audio_file("a.mp3"),
            recording_date=datetime.date(2025, 1, 1),
        )
        r2 = Recording.objects.create(
            title="Recording 2",
            speaker="Speaker B",
            audio_file=_make_audio_file("b.mp3"),
            recording_date=datetime.date(2025, 1, 2),
        )
        r1.tags.add(tag)
        r2.tags.add(tag)
        self.assertIn(tag, r1.tags.all())
        self.assertIn(tag, r2.tags.all())
        self.assertEqual(tag.recording_set.count(), 2)

    def test_removing_tag_from_recording(self):
        """20. Removing a tag from a recording works."""
        tag = Tag.objects.create(name="Removable")
        recording = Recording.objects.create(
            title="Remove Tag Test",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        recording.tags.add(tag)
        self.assertEqual(recording.tags.count(), 1)
        recording.tags.remove(tag)
        self.assertEqual(recording.tags.count(), 0)

    def test_deleting_tag_removes_it_from_recording(self):
        """21. Deleting a tag removes it from the recording's tags (M2M cascade)."""
        tag = Tag.objects.create(name="Ephemeral")
        recording = Recording.objects.create(
            title="Cascade Test",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        recording.tags.add(tag)
        self.assertEqual(recording.tags.count(), 1)
        tag.delete()
        self.assertEqual(recording.tags.count(), 0)


class RecordingEdgeCaseTests(TestCase):
    """Tests 22-25: Edge cases."""

    def test_multiple_recordings_ordered_newest_first(self):
        """22. Multiple recordings ordered by newest first."""
        r1 = Recording.objects.create(
            title="Oldest",
            speaker="Speaker A",
            audio_file=_make_audio_file("1.mp3"),
            recording_date=datetime.date(2025, 1, 1),
        )
        r2 = Recording.objects.create(
            title="Middle",
            speaker="Speaker B",
            audio_file=_make_audio_file("2.mp3"),
            recording_date=datetime.date(2025, 2, 1),
        )
        r3 = Recording.objects.create(
            title="Newest",
            speaker="Speaker C",
            audio_file=_make_audio_file("3.mp3"),
            recording_date=datetime.date(2025, 3, 1),
        )
        recordings = list(Recording.objects.all())
        self.assertEqual(recordings[0], r3)
        self.assertEqual(recordings[1], r2)
        self.assertEqual(recordings[2], r1)

    def test_recording_can_be_deleted(self):
        """23. Recording can be deleted."""
        recording = Recording.objects.create(
            title="To Delete",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        pk = recording.pk
        recording.delete()
        self.assertFalse(Recording.objects.filter(pk=pk).exists())

    def test_deleting_recording_does_not_delete_tags(self):
        """24. Deleting a recording does NOT delete its tags."""
        tag = Tag.objects.create(name="Persistent")
        recording = Recording.objects.create(
            title="Deletable Recording",
            speaker="Speaker",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 1, 1),
        )
        recording.tags.add(tag)
        recording.delete()
        self.assertTrue(Tag.objects.filter(pk=tag.pk).exists())

    def test_two_recordings_can_have_same_title(self):
        """25. Two recordings can have the same title (not unique)."""
        r1 = Recording.objects.create(
            title="Duplicate Title",
            speaker="Speaker A",
            audio_file=_make_audio_file("a.mp3"),
            recording_date=datetime.date(2025, 1, 1),
        )
        r2 = Recording.objects.create(
            title="Duplicate Title",
            speaker="Speaker B",
            audio_file=_make_audio_file("b.mp3"),
            recording_date=datetime.date(2025, 1, 2),
        )
        self.assertEqual(r1.title, r2.title)
        self.assertNotEqual(r1.pk, r2.pk)
        self.assertEqual(Recording.objects.filter(title="Duplicate Title").count(), 2)


class RecordingAdminTests(TestCase):
    """Test 26: Admin registration."""

    def test_recording_registered_in_admin(self):
        """26. Recording model is registered in admin."""
        self.assertIn(Recording, admin_site._registry)
