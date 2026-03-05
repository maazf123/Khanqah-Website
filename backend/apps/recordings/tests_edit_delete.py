"""Tests for recording edit and delete functionality (staff-only, modal-based)."""

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _make_recording(**kwargs):
    defaults = {
        "title": "Test Recording",
        "description": "A test.",
        "speaker": "Sheikh Test",
        "audio_file": SimpleUploadedFile("t.mp3", b"audio", content_type="audio/mpeg"),
        "recording_date": timezone.now().date(),
    }
    defaults.update(kwargs)
    return Recording.objects.create(**defaults)


# ============================================================================
# Recording Update API
# ============================================================================


class RecordingUpdateAccessTests(TestCase):
    """Only staff can access the recording update endpoint."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.recording = _make_recording()
        self.url = reverse("recording-update", kwargs={"pk": self.recording.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url, {"title": "New"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url, {"title": "New"})
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(
            self.url, {"title": "Updated", "description": "d"},
            content_type="application/json",
        )
        self.assertIn(response.status_code, [200, 302])

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class RecordingUpdateAPITests(TestCase):
    """Tests for the JSON recording update endpoint."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.tag1 = Tag.objects.create(name="Fiqh")
        self.tag2 = Tag.objects.create(name="Hadith")
        self.recording = _make_recording()
        self.recording.tags.add(self.tag1)
        self.url = reverse("recording-update", kwargs={"pk": self.recording.pk})

    def test_returns_json(self):
        response = self.client.post(
            self.url, {"title": "New Title", "description": "new desc"},
            content_type="application/json",
        )
        self.assertEqual(response["Content-Type"], "application/json")

    def test_updates_title(self):
        self.client.post(
            self.url, {"title": "Updated Title"},
            content_type="application/json",
        )
        self.recording.refresh_from_db()
        self.assertEqual(self.recording.title, "Updated Title")

    def test_updates_description(self):
        self.client.post(
            self.url, {"description": "New description"},
            content_type="application/json",
        )
        self.recording.refresh_from_db()
        self.assertEqual(self.recording.description, "New description")

    def test_updates_tags(self):
        self.client.post(
            self.url, {"tags": [self.tag2.pk]},
            content_type="application/json",
        )
        self.recording.refresh_from_db()
        self.assertEqual(list(self.recording.tags.values_list("pk", flat=True)), [self.tag2.pk])

    def test_returns_ok_true(self):
        response = self.client.post(
            self.url, {"title": "X"},
            content_type="application/json",
        )
        self.assertTrue(response.json()["ok"])

    def test_blank_title_returns_error(self):
        response = self.client.post(
            self.url, {"title": ""},
            content_type="application/json",
        )
        data = response.json()
        self.assertFalse(data["ok"])

    def test_nonexistent_recording_returns_404(self):
        url = reverse("recording-update", kwargs={"pk": 99999})
        response = self.client.post(
            url, {"title": "X"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_partial_update_preserves_other_fields(self):
        original_title = self.recording.title
        self.client.post(
            self.url, {"description": "Only desc changed"},
            content_type="application/json",
        )
        self.recording.refresh_from_db()
        self.assertEqual(self.recording.title, original_title)
        self.assertEqual(self.recording.description, "Only desc changed")

    def test_clear_tags(self):
        self.client.post(
            self.url, {"tags": []},
            content_type="application/json",
        )
        self.recording.refresh_from_db()
        self.assertEqual(self.recording.tags.count(), 0)


# ============================================================================
# Recording Delete API
# ============================================================================


class RecordingDeleteAccessTests(TestCase):
    """Only staff can delete recordings."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.recording = _make_recording()
        self.url = reverse("recording-delete", kwargs={"pk": self.recording.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_delete(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertIn(response.status_code, [200])

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class RecordingDeleteAPITests(TestCase):
    """Tests for the JSON recording delete endpoint."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.recording = _make_recording()
        self.url = reverse("recording-delete", kwargs={"pk": self.recording.pk})

    def test_returns_json(self):
        response = self.client.post(self.url)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_returns_ok(self):
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_deletes_recording(self):
        pk = self.recording.pk
        self.client.post(self.url)
        self.assertFalse(Recording.objects.filter(pk=pk).exists())

    def test_nonexistent_returns_404(self):
        url = reverse("recording-delete", kwargs={"pk": 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


# ============================================================================
# Edit/Delete buttons visible on detail page for staff only
# ============================================================================


class RecordingDetailAdminButtonsTests(TestCase):
    """Edit/delete icons appear on the detail page only for staff."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.recording = _make_recording()
        self.url = reverse("recording-detail", kwargs={"pk": self.recording.pk})

    def test_staff_sees_edit_button(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "edit-recording-modal")

    def test_staff_sees_delete_button(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "delete-recording-btn")

    def test_anonymous_does_not_see_edit_button(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "edit-recording-modal")

    def test_anonymous_does_not_see_delete_button(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "delete-recording-btn")
