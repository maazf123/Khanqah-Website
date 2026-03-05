"""
Exhaustive tests for the recording detail view.

The view under test:
- URL: `/recordings/<int:pk>/` — name: `recording-detail`
- Django DetailView on Recording model
- Template: `recordings/recording_detail.html`
- Context object name: `recording`
"""

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _fake_audio(name="test.mp3"):
    """Return a minimal SimpleUploadedFile that stands in for an audio file."""
    return SimpleUploadedFile(name, b"\x00" * 128, content_type="audio/mpeg")


def _create_recording(title="Test", speaker="Speaker", recording_date=None,
                       description="", tags=None, **kwargs):
    """Helper to create a Recording with sensible defaults."""
    if recording_date is None:
        recording_date = date.today()
    rec = Recording.objects.create(
        title=title,
        speaker=speaker,
        description=description,
        audio_file=_fake_audio(),
        recording_date=recording_date,
        **kwargs,
    )
    if tags:
        rec.tags.set(tags)
    return rec


# ---------------------------------------------------------------------------
# Basic page tests
# ---------------------------------------------------------------------------

class RecordingDetailBasicTests(TestCase):
    """Basic page loading, template, and 404 tests."""

    def setUp(self):
        self.client = Client()

    # ---- 1. GET /recordings/<pk>/ returns 200 for a valid recording ----
    def test_get_valid_recording_returns_200(self):
        rec = _create_recording(title="Valid Recording")
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ---- 2. Uses the correct template ----
    def test_uses_correct_template(self):
        rec = _create_recording(title="Template Check")
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        self.assertTemplateUsed(response, "recordings/recording_detail.html")

    # ---- 3. Nonexistent pk returns 404 ----
    def test_nonexistent_pk_returns_404(self):
        url = reverse("recording-detail", kwargs={"pk": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Content displayed / context tests
# ---------------------------------------------------------------------------

class RecordingDetailContextTests(TestCase):
    """Tests that the context contains the correct recording and all fields."""

    def setUp(self):
        self.client = Client()
        self.tag1 = Tag.objects.create(name="Fiqh")
        self.tag2 = Tag.objects.create(name="Hadith")
        self.rec = _create_recording(
            title="Detailed Lecture",
            speaker="Shaykh Ahmad",
            description="A thorough discussion on fiqh topics.",
            recording_date=date(2025, 6, 15),
            tags=[self.tag1, self.tag2],
        )
        self.url = reverse("recording-detail", kwargs={"pk": self.rec.pk})

    # ---- 4. Context contains the correct recording object ----
    def test_context_contains_correct_recording(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["recording"], self.rec)

    # ---- 5. Recording title is accessible in context ----
    def test_recording_title_in_context(self):
        response = self.client.get(self.url)
        recording = response.context["recording"]
        self.assertEqual(recording.title, "Detailed Lecture")

    # ---- 6. Recording speaker is accessible in context ----
    def test_recording_speaker_in_context(self):
        response = self.client.get(self.url)
        recording = response.context["recording"]
        self.assertEqual(recording.speaker, "Shaykh Ahmad")

    # ---- 7. Recording description is accessible in context ----
    def test_recording_description_in_context(self):
        response = self.client.get(self.url)
        recording = response.context["recording"]
        self.assertEqual(
            recording.description,
            "A thorough discussion on fiqh topics.",
        )

    # ---- 8. Recording date is accessible in context ----
    def test_recording_date_in_context(self):
        response = self.client.get(self.url)
        recording = response.context["recording"]
        self.assertEqual(recording.recording_date, date(2025, 6, 15))

    # ---- 9. Recording tags are accessible in context ----
    def test_recording_tags_in_context(self):
        response = self.client.get(self.url)
        recording = response.context["recording"]
        tags = set(recording.tags.all())
        self.assertEqual(tags, {self.tag1, self.tag2})

    # ---- 10. Recording audio_file URL is accessible in context ----
    def test_recording_audio_file_url_in_context(self):
        response = self.client.get(self.url)
        recording = response.context["recording"]
        # The audio_file field should have a .url attribute
        self.assertTrue(recording.audio_file.url)
        self.assertIn("recordings/", recording.audio_file.url)


# ---------------------------------------------------------------------------
# Audio player tests
# ---------------------------------------------------------------------------

class RecordingDetailAudioPlayerTests(TestCase):
    """Tests for the HTML5 <audio> element in the rendered response."""

    def setUp(self):
        self.client = Client()
        self.rec = _create_recording(title="Audio Lecture")
        self.url = reverse("recording-detail", kwargs={"pk": self.rec.pk})

    # ---- 11. Response content contains an HTML5 <audio> element ----
    def test_response_contains_audio_element(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("<audio", content)

    # ---- 12. The <audio> element's source references the recording's audio file URL ----
    def test_audio_element_references_audio_file_url(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        audio_url = self.rec.audio_file.url
        self.assertIn(audio_url, content)


# ---------------------------------------------------------------------------
# Tags displayed tests
# ---------------------------------------------------------------------------

class RecordingDetailTagDisplayTests(TestCase):
    """Tests for tags in the detail view."""

    def setUp(self):
        self.client = Client()

    # ---- 13. Recording with tags -- tags appear in context ----
    def test_recording_with_tags_has_tags_in_context(self):
        tag_fiqh = Tag.objects.create(name="Fiqh")
        tag_tafsir = Tag.objects.create(name="Tafsir")
        rec = _create_recording(title="Tagged Lecture", tags=[tag_fiqh, tag_tafsir])
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        recording = response.context["recording"]
        tags = set(recording.tags.all())
        self.assertEqual(tags, {tag_fiqh, tag_tafsir})

    # ---- 14. Recording with no tags -- still works fine (no error) ----
    def test_recording_with_no_tags_returns_200(self):
        rec = _create_recording(title="No Tags Lecture")
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        recording = response.context["recording"]
        self.assertEqual(recording.tags.count(), 0)

    # ---- 15. Tags link back to the browse page with tag filter ----
    def test_tags_link_to_browse_page_with_tag_filter(self):
        tag = Tag.objects.create(name="Seerah")
        rec = _create_recording(title="Seerah Lecture", tags=[tag])
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        content = response.content.decode()
        # The template should contain a link with ?tag=<slug>
        expected_link = f"?tag={tag.slug}"
        self.assertIn(expected_link, content)


# ---------------------------------------------------------------------------
# Description tests
# ---------------------------------------------------------------------------

class RecordingDetailDescriptionTests(TestCase):
    """Tests for the description field in the detail view."""

    def setUp(self):
        self.client = Client()

    # ---- 16. Recording with description shows it ----
    def test_recording_with_description_shows_it(self):
        rec = _create_recording(
            title="Described Lecture",
            description="This is a detailed description of the lecture.",
        )
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        content = response.content.decode()
        self.assertIn("This is a detailed description of the lecture.", content)

    # ---- 17. Recording with empty description -- page still works ----
    def test_recording_with_empty_description_returns_200(self):
        rec = _create_recording(title="No Description", description="")
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Navigation tests
# ---------------------------------------------------------------------------

class RecordingDetailNavigationTests(TestCase):
    """Tests for navigation links on the detail page."""

    def setUp(self):
        self.client = Client()

    # ---- 18. Page contains a link back to the recording list ----
    def test_page_contains_link_to_recording_list(self):
        rec = _create_recording(title="Nav Test Lecture")
        url = reverse("recording-detail", kwargs={"pk": rec.pk})
        response = self.client.get(url)
        content = response.content.decode()
        list_url = reverse("recording-list")
        self.assertIn(list_url, content)
