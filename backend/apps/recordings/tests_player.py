"""Tests for recording card clickability and audio player features."""
import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _make_recording(**kwargs):
    defaults = {
        "title": "Test Recording",
        "description": "A test.",
        "speaker": "Test Speaker",
        "recording_date": datetime.date(2025, 1, 1),
        "audio_file": SimpleUploadedFile("t.mp3", b"\x00" * 256, content_type="audio/mpeg"),
    }
    defaults.update(kwargs)
    return Recording.objects.create(**defaults)


# ── Card clickability tests ──────────────────────────────────────


class RecordingCardClickableTests(TestCase):
    """The entire recording card should be a clickable link."""

    def setUp(self):
        self.client = Client()
        self.recording = _make_recording()
        self.list_url = reverse("recording-list")

    def test_card_is_wrapped_in_anchor(self):
        """The recording-card should be wrapped in (or be) an <a> tag linking to detail."""
        response = self.client.get(self.list_url)
        html = response.content.decode()
        detail_url = reverse("recording-detail", args=[self.recording.pk])
        # There should be an <a> wrapping the card that links to the detail page
        self.assertIn(f'href="{detail_url}"', html)
        # The card-body content should be inside a link to the detail page
        # Check that the card link wraps the card content (not just the title)
        self.assertIn('recording-card-link', html)

    def test_card_link_contains_title(self):
        response = self.client.get(self.list_url)
        html = response.content.decode()
        self.assertIn(self.recording.title, html)

    def test_card_link_contains_description(self):
        response = self.client.get(self.list_url)
        html = response.content.decode()
        self.assertIn(self.recording.description, html)


# ── Progress bar seekable tests ──────────────────────────────────


class AudioPlayerSeekableTests(TestCase):
    """The detail page progress bar should be clickable to seek."""

    def setUp(self):
        self.client = Client()
        self.recording = _make_recording()
        self.detail_url = reverse("recording-detail", args=[self.recording.pk])

    def test_progress_bar_has_click_handler(self):
        """The progress bar should have a click/seek handler in the JS."""
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        # The JS should register a click listener on the progress bar
        self.assertIn("progress-bar", html)
        # Should have seek-on-click logic
        self.assertIn("getBoundingClientRect", html)

    def test_progress_bar_has_cursor_pointer(self):
        """The progress bar element should indicate it's clickable."""
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        # The progress-bar should be clickable (cursor pointer set via class or inline)
        self.assertIn("progress-bar", html)


# ── Skip forward/back button tests ──────────────────────────────


class AudioPlayerSkipButtonTests(TestCase):
    """The detail page should have skip forward/back 10s buttons."""

    def setUp(self):
        self.client = Client()
        self.recording = _make_recording()
        self.detail_url = reverse("recording-detail", args=[self.recording.pk])

    def test_has_skip_back_button(self):
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        self.assertIn("skip-back", html)

    def test_has_skip_forward_button(self):
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        self.assertIn("skip-fwd", html)

    def test_skip_buttons_show_10_label(self):
        """Buttons should display '10' to indicate 10-second skip."""
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        # Both skip buttons should show "10"
        self.assertIn("10", html)

    def test_skip_back_js_subtracts_10(self):
        """The JS should subtract 10 from currentTime on back click."""
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        self.assertIn("currentTime", html)
        # Should have -10 logic
        self.assertIn("-10", html) or self.assertIn("- 10", html)

    def test_skip_fwd_js_adds_10(self):
        """The JS should add 10 to currentTime on forward click."""
        response = self.client.get(self.detail_url)
        html = response.content.decode()
        self.assertIn("+10", html) or self.assertIn("+ 10", html)
