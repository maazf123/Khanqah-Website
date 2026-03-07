"""TDD tests for Chunk 4: Archive System (Soft-Delete).

Features tested:
1. is_archived + archived_at fields on Recording and Writing models
2. Delete endpoints now soft-delete instead of hard delete
3. Public querysets exclude archived items
4. Staff-only archived items page
5. Restore endpoint to un-archive items
6. Permanent delete endpoint to actually remove items
"""

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.recordings.models import Recording
from apps.writings.models import Writing


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


def _make_writing(**kwargs):
    defaults = {
        "title": "Test Writing",
        "body": "Some content here.",
        "published_date": timezone.now().date(),
    }
    defaults.update(kwargs)
    return Writing.objects.create(**defaults)


# ============================================================================
# Model field tests
# ============================================================================


class RecordingSoftDeleteModelTests(TestCase):
    """Recording model has is_archived and archived_at fields."""

    def test_is_archived_defaults_to_false(self):
        rec = _make_recording()
        self.assertFalse(rec.is_archived)

    def test_archived_at_defaults_to_none(self):
        rec = _make_recording()
        self.assertIsNone(rec.archived_at)

    def test_can_set_is_archived(self):
        rec = _make_recording()
        rec.is_archived = True
        rec.archived_at = timezone.now()
        rec.save()
        rec.refresh_from_db()
        self.assertTrue(rec.is_archived)
        self.assertIsNotNone(rec.archived_at)


class WritingSoftDeleteModelTests(TestCase):
    """Writing model has is_archived and archived_at fields."""

    def test_is_archived_defaults_to_false(self):
        w = _make_writing()
        self.assertFalse(w.is_archived)

    def test_archived_at_defaults_to_none(self):
        w = _make_writing()
        self.assertIsNone(w.archived_at)

    def test_can_set_is_archived(self):
        w = _make_writing()
        w.is_archived = True
        w.archived_at = timezone.now()
        w.save()
        w.refresh_from_db()
        self.assertTrue(w.is_archived)
        self.assertIsNotNone(w.archived_at)


# ============================================================================
# Soft-delete behavior (existing delete endpoints)
# ============================================================================


class RecordingSoftDeleteTests(TestCase):
    """Delete endpoint now soft-deletes recordings."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.recording = _make_recording()
        self.url = reverse("recording-delete", kwargs={"pk": self.recording.pk})

    def test_delete_sets_is_archived_true(self):
        self.client.post(self.url)
        self.recording.refresh_from_db()
        self.assertTrue(self.recording.is_archived)

    def test_delete_sets_archived_at(self):
        self.client.post(self.url)
        self.recording.refresh_from_db()
        self.assertIsNotNone(self.recording.archived_at)

    def test_delete_does_not_remove_from_db(self):
        pk = self.recording.pk
        self.client.post(self.url)
        self.assertTrue(Recording.objects.filter(pk=pk).exists())

    def test_delete_returns_ok_json(self):
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_delete_already_archived_returns_404(self):
        """Cannot soft-delete an item that's already archived."""
        self.recording.is_archived = True
        self.recording.archived_at = timezone.now()
        self.recording.save()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)


class WritingSoftDeleteTests(TestCase):
    """Delete endpoint now soft-deletes writings."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.writing = _make_writing()
        self.url = reverse("writing-delete", kwargs={"pk": self.writing.pk})

    def test_delete_sets_is_archived_true(self):
        self.client.post(self.url)
        self.writing.refresh_from_db()
        self.assertTrue(self.writing.is_archived)

    def test_delete_sets_archived_at(self):
        self.client.post(self.url)
        self.writing.refresh_from_db()
        self.assertIsNotNone(self.writing.archived_at)

    def test_delete_does_not_remove_from_db(self):
        pk = self.writing.pk
        self.client.post(self.url)
        self.assertTrue(Writing.objects.filter(pk=pk).exists())

    def test_delete_returns_ok_json(self):
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_delete_already_archived_returns_404(self):
        """Cannot soft-delete an item that's already archived."""
        self.writing.is_archived = True
        self.writing.archived_at = timezone.now()
        self.writing.save()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)


# ============================================================================
# Public queryset filtering
# ============================================================================


class RecordingQuerysetFilterTests(TestCase):
    """Archived recordings should not appear in public views."""

    def setUp(self):
        self.client = Client()
        self.active = _make_recording(title="Active Recording")
        self.archived = _make_recording(title="Archived Recording")
        self.archived.is_archived = True
        self.archived.archived_at = timezone.now()
        self.archived.save()

    def test_list_excludes_archived(self):
        response = self.client.get(reverse("recording-list"))
        content = response.content.decode()
        self.assertIn("Active Recording", content)
        self.assertNotIn("Archived Recording", content)

    def test_all_recordings_page_excludes_archived(self):
        """The 'all recordings' paginated page also excludes archived items."""
        response = self.client.get(reverse("recording-archive"))
        content = response.content.decode()
        self.assertIn("Active Recording", content)
        self.assertNotIn("Archived Recording", content)

    def test_search_excludes_archived(self):
        response = self.client.get(reverse("recording-search") + "?q=Recording")
        content = response.content.decode()
        self.assertIn("Active Recording", content)
        self.assertNotIn("Archived Recording", content)

    def test_detail_of_archived_returns_404(self):
        response = self.client.get(
            reverse("recording-detail", kwargs={"pk": self.archived.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_of_active_returns_200(self):
        response = self.client.get(
            reverse("recording-detail", kwargs={"pk": self.active.pk})
        )
        self.assertEqual(response.status_code, 200)


class WritingQuerysetFilterTests(TestCase):
    """Archived writings should not appear in public views."""

    def setUp(self):
        self.client = Client()
        self.active = _make_writing(title="Active Writing")
        self.archived = _make_writing(title="Archived Writing")
        self.archived.is_archived = True
        self.archived.archived_at = timezone.now()
        self.archived.save()

    def test_list_excludes_archived(self):
        response = self.client.get(reverse("writing-list"))
        content = response.content.decode()
        self.assertIn("Active Writing", content)
        self.assertNotIn("Archived Writing", content)

    def test_all_writings_page_excludes_archived(self):
        response = self.client.get(reverse("writing-archive"))
        content = response.content.decode()
        self.assertIn("Active Writing", content)
        self.assertNotIn("Archived Writing", content)

    def test_detail_of_archived_returns_404(self):
        response = self.client.get(
            reverse("writing-detail", kwargs={"pk": self.archived.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_of_active_returns_200(self):
        response = self.client.get(
            reverse("writing-detail", kwargs={"pk": self.active.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_api_detail_of_archived_returns_404(self):
        response = self.client.get(
            reverse("writing-detail-api", kwargs={"pk": self.archived.pk})
        )
        self.assertEqual(response.status_code, 404)


# ============================================================================
# Archived items page (staff-only)
# ============================================================================


class ArchivedItemsPageTests(TestCase):
    """Staff-only page listing all archived recordings and writings."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.url = reverse("archived-items")

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_shows_archived_recordings(self):
        rec = _make_recording(title="Archived Rec")
        rec.is_archived = True
        rec.archived_at = timezone.now()
        rec.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Archived Rec")

    def test_shows_archived_writings(self):
        w = _make_writing(title="Archived Writing")
        w.is_archived = True
        w.archived_at = timezone.now()
        w.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Archived Writing")

    def test_does_not_show_active_recordings(self):
        _make_recording(title="Active Rec")
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Active Rec")

    def test_does_not_show_active_writings(self):
        _make_writing(title="Active Writing")
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Active Writing")

    def test_empty_archive_shows_message(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "No archived items")

    def test_has_restore_button_for_recording(self):
        rec = _make_recording(title="Restore Me Rec")
        rec.is_archived = True
        rec.archived_at = timezone.now()
        rec.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "recording-restore-btn")

    def test_has_permanent_delete_button_for_recording(self):
        rec = _make_recording(title="Delete Me Rec")
        rec.is_archived = True
        rec.archived_at = timezone.now()
        rec.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "recording-permanent-delete-btn")

    def test_has_restore_button_for_writing(self):
        w = _make_writing(title="Restore Me Writing")
        w.is_archived = True
        w.archived_at = timezone.now()
        w.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "writing-restore-btn")

    def test_has_permanent_delete_button_for_writing(self):
        w = _make_writing(title="Delete Me Writing")
        w.is_archived = True
        w.archived_at = timezone.now()
        w.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "writing-permanent-delete-btn")


# ============================================================================
# Restore endpoints
# ============================================================================


class RecordingRestoreTests(TestCase):
    """Restore endpoint un-archives a recording."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.recording = _make_recording()
        self.recording.is_archived = True
        self.recording.archived_at = timezone.now()
        self.recording.save()
        self.url = reverse("recording-restore", kwargs={"pk": self.recording.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_restore_sets_is_archived_false(self):
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.recording.refresh_from_db()
        self.assertFalse(self.recording.is_archived)

    def test_restore_clears_archived_at(self):
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.recording.refresh_from_db()
        self.assertIsNone(self.recording.archived_at)

    def test_restore_returns_ok_json(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_returns_404(self):
        self.client.login(username="admin", password="pass")
        url = reverse("recording-restore", kwargs={"pk": 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_restore_non_archived_returns_404(self):
        """Cannot restore a recording that is not archived."""
        active = _make_recording(title="Active")
        url = reverse("recording-restore", kwargs={"pk": active.pk})
        self.client.login(username="admin", password="pass")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class WritingRestoreTests(TestCase):
    """Restore endpoint un-archives a writing."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.writing = _make_writing()
        self.writing.is_archived = True
        self.writing.archived_at = timezone.now()
        self.writing.save()
        self.url = reverse("writing-restore", kwargs={"pk": self.writing.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_restore_sets_is_archived_false(self):
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.writing.refresh_from_db()
        self.assertFalse(self.writing.is_archived)

    def test_restore_clears_archived_at(self):
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.writing.refresh_from_db()
        self.assertIsNone(self.writing.archived_at)

    def test_restore_returns_ok_json(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_returns_404(self):
        self.client.login(username="admin", password="pass")
        url = reverse("writing-restore", kwargs={"pk": 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_restore_non_archived_returns_404(self):
        """Cannot restore a writing that is not archived."""
        active = _make_writing(title="Active")
        url = reverse("writing-restore", kwargs={"pk": active.pk})
        self.client.login(username="admin", password="pass")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


# ============================================================================
# Permanent delete endpoints
# ============================================================================


class RecordingPermanentDeleteTests(TestCase):
    """Permanent delete endpoint actually removes the recording from DB."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.recording = _make_recording()
        self.recording.is_archived = True
        self.recording.archived_at = timezone.now()
        self.recording.save()
        self.url = reverse("recording-permanent-delete", kwargs={"pk": self.recording.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_permanently_deletes_recording(self):
        pk = self.recording.pk
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.assertFalse(Recording.objects.filter(pk=pk).exists())

    def test_returns_ok_json(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_only_works_on_archived_items(self):
        """Cannot permanently delete an active (non-archived) recording."""
        active = _make_recording(title="Active One")
        url = reverse("recording-permanent-delete", kwargs={"pk": active.pk})
        self.client.login(username="admin", password="pass")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Recording.objects.filter(pk=active.pk).exists())

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_returns_404(self):
        self.client.login(username="admin", password="pass")
        url = reverse("recording-permanent-delete", kwargs={"pk": 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class WritingPermanentDeleteTests(TestCase):
    """Permanent delete endpoint actually removes the writing from DB."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.writing = _make_writing()
        self.writing.is_archived = True
        self.writing.archived_at = timezone.now()
        self.writing.save()
        self.url = reverse("writing-permanent-delete", kwargs={"pk": self.writing.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_permanently_deletes_writing(self):
        pk = self.writing.pk
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.assertFalse(Writing.objects.filter(pk=pk).exists())

    def test_returns_ok_json(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_only_works_on_archived_items(self):
        """Cannot permanently delete an active (non-archived) writing."""
        active = _make_writing(title="Active Writing")
        url = reverse("writing-permanent-delete", kwargs={"pk": active.pk})
        self.client.login(username="admin", password="pass")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Writing.objects.filter(pk=active.pk).exists())

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_returns_404(self):
        self.client.login(username="admin", password="pass")
        url = reverse("writing-permanent-delete", kwargs={"pk": 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
