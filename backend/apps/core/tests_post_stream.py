"""TDD tests for post-stream flow: Post vs Archive vs Discard.

After stopping a livestream, the broadcaster sees a modal with three options:
- Post: Creates a public recording (visible to everyone)
- Archive: Creates a hidden recording (is_archived=True, only visible in /archived/)
- Discard: No recording created, redirects to livestream list

Also tests:
- Recordings list page has staff-only "View Archived" link
- Full user flow simulation (start stream → stop → post/archive/discard → verify pages)
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import LiveStream
from apps.recordings.models import Recording


# ============================================================================
# 1. Archive endpoint mode parameter
# ============================================================================


class ArchiveEndpointPostModeTests(TestCase):
    """When mode='post', the archive endpoint creates a PUBLIC recording."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            "admin", password="pass", is_staff=True,
            first_name="Sheikh", last_name="Ahmad",
        )
        self.client.login(username="admin", password="pass")
        self.stream = LiveStream.objects.create(
            title="Friday Bayan", created_by=self.staff, is_active=False,
        )
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.url = reverse("livestream-archive", kwargs={"stream_key": self.stream.stream_key})

    def test_post_mode_creates_public_recording(self):
        response = self.client.post(
            self.url, {"mode": "post"},
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        rec = Recording.objects.get(pk=data["recording_id"])
        self.assertFalse(rec.is_archived)

    def test_post_mode_recording_has_correct_title(self):
        self.client.post(self.url, {"mode": "post"}, content_type="application/json")
        rec = Recording.objects.first()
        self.assertEqual(rec.title, "Friday Bayan")

    def test_post_mode_recording_has_speaker(self):
        self.client.post(self.url, {"mode": "post"}, content_type="application/json")
        rec = Recording.objects.first()
        self.assertEqual(rec.speaker, "Sheikh Ahmad")

    def test_post_mode_recording_visible_in_list(self):
        """A posted recording appears on the public recordings page."""
        self.client.post(self.url, {"mode": "post"}, content_type="application/json")
        response = self.client.get(reverse("recording-list"))
        self.assertContains(response, "Friday Bayan")

    def test_post_mode_recording_detail_accessible(self):
        """A posted recording's detail page loads without error."""
        resp = self.client.post(self.url, {"mode": "post"}, content_type="application/json")
        rec_id = resp.json()["recording_id"]
        response = self.client.get(reverse("recording-detail", kwargs={"pk": rec_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Friday Bayan")


class ArchiveEndpointArchiveModeTests(TestCase):
    """When mode='archive', the endpoint creates a HIDDEN recording (is_archived=True)."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            "admin", password="pass", is_staff=True,
            first_name="Sheikh", last_name="Ahmad",
        )
        self.client.login(username="admin", password="pass")
        self.stream = LiveStream.objects.create(
            title="Private Dhikr", created_by=self.staff, is_active=False,
        )
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.url = reverse("livestream-archive", kwargs={"stream_key": self.stream.stream_key})

    def test_archive_mode_creates_archived_recording(self):
        response = self.client.post(
            self.url, {"mode": "archive"},
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        rec = Recording.objects.get(pk=data["recording_id"])
        self.assertTrue(rec.is_archived)

    def test_archive_mode_sets_archived_at(self):
        self.client.post(self.url, {"mode": "archive"}, content_type="application/json")
        rec = Recording.objects.first()
        self.assertIsNotNone(rec.archived_at)

    def test_archive_mode_recording_not_visible_in_list(self):
        """An archived recording does NOT appear on the public recordings page."""
        self.client.post(self.url, {"mode": "archive"}, content_type="application/json")
        response = self.client.get(reverse("recording-list"))
        self.assertNotContains(response, "Private Dhikr")

    def test_archive_mode_recording_detail_returns_404(self):
        """An archived recording's detail page returns 404 for public access."""
        resp = self.client.post(self.url, {"mode": "archive"}, content_type="application/json")
        rec_id = resp.json()["recording_id"]
        self.client.logout()
        response = self.client.get(reverse("recording-detail", kwargs={"pk": rec_id}))
        self.assertEqual(response.status_code, 404)

    def test_archive_mode_recording_visible_in_archived_page(self):
        """An archived recording appears on the staff-only /archived/ page."""
        self.client.post(self.url, {"mode": "archive"}, content_type="application/json")
        response = self.client.get(reverse("archived-items"))
        self.assertContains(response, "Private Dhikr")


class ArchiveEndpointDefaultModeTests(TestCase):
    """When no mode is provided (backwards compat), default to 'archive' behavior."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.stream = LiveStream.objects.create(
            title="Default Mode", created_by=self.staff, is_active=False,
        )
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.url = reverse("livestream-archive", kwargs={"stream_key": self.stream.stream_key})

    def test_no_mode_defaults_to_archive(self):
        """Without a mode param, recording is created as archived."""
        response = self.client.post(self.url)
        data = response.json()
        self.assertTrue(data["ok"])
        rec = Recording.objects.get(pk=data["recording_id"])
        self.assertTrue(rec.is_archived)


# ============================================================================
# 2. Post-stream modal HTML (3 buttons)
# ============================================================================


class PostStreamModalThreeButtonTests(TestCase):
    """The post-stream modal must have Post, Archive, and Discard buttons."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.stream = LiveStream.objects.create(
            title="Modal Test", created_by=self.staff,
        )
        self.url = reverse("livestream-broadcast", kwargs={"stream_key": self.stream.stream_key})
        response = self.client.get(self.url)
        self.html = response.content.decode()

    def test_has_post_button(self):
        self.assertIn('id="post-btn"', self.html)

    def test_has_archive_button(self):
        self.assertIn('id="archive-btn"', self.html)

    def test_has_discard_button(self):
        self.assertIn('id="discard-btn"', self.html)

    def test_post_button_text(self):
        """Post button should contain 'Post' text."""
        self.assertIn("Post", self.html)

    def test_archive_button_text(self):
        """Archive button should contain 'Archive' text."""
        self.assertIn("Archive", self.html)

    def test_discard_button_text(self):
        """Discard button should contain 'Discard' text."""
        self.assertIn("Discard", self.html)

    def test_js_has_post_stream_function(self):
        """JS must have a postStream function for the Post button."""
        self.assertIn("postStream", self.html)

    def test_js_has_archive_stream_function(self):
        """JS must have an archiveStream function for the Archive button."""
        self.assertIn("archiveStream", self.html)


# ============================================================================
# 3. Recordings list page — staff-only "View Archived" link
# ============================================================================


class RecordingsListArchivedLinkTests(TestCase):
    """The recordings list page should have a 'View Archived' link for staff."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")

    def test_staff_sees_view_archived_link(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("recording-list"))
        self.assertContains(response, reverse("archived-items"))

    def test_anonymous_does_not_see_view_archived_link(self):
        response = self.client.get(reverse("recording-list"))
        content = response.content.decode()
        self.assertNotIn("archived", content.lower().split("archive recording")[0] if "archive recording" in content.lower() else content.lower())

    def test_staff_sees_archived_text(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("recording-list"))
        self.assertContains(response, "View Archived")


# ============================================================================
# 4. Full user flow simulation tests
# ============================================================================


class UserFlowPostStreamTests(TestCase):
    """Simulate the full user journey: start stream → stop → Post → verify."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            "admin", password="pass", is_staff=True,
            first_name="Sheikh", last_name="Ahmad",
        )
        self.client.login(username="admin", password="pass")

    def test_full_post_flow(self):
        """User starts stream, stops it, posts recording, verifies it's public."""
        # 1. Start a livestream
        response = self.client.post(
            reverse("livestream-start"),
            {"title": "Jummah Khutbah"},
        )
        self.assertEqual(response.status_code, 302)
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        self.assertTrue(stream.is_active)

        # 2. Broadcast page loads
        broadcast_url = reverse("livestream-broadcast", kwargs={"stream_key": stream.stream_key})
        response = self.client.get(broadcast_url)
        self.assertEqual(response.status_code, 200)

        # 3. Stop the stream (AJAX)
        stop_url = reverse("livestream-stop", kwargs={"stream_key": stream.stream_key})
        response = self.client.post(
            stop_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        # 4. Post the recording (mode=post)
        archive_url = reverse("livestream-archive", kwargs={"stream_key": stream.stream_key})
        response = self.client.post(
            archive_url, {"mode": "post"},
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        rec_id = data["recording_id"]

        # 5. Verify recording detail page loads
        detail_url = reverse("recording-detail", kwargs={"pk": rec_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jummah Khutbah")

        # 6. Verify recording appears in public list
        response = self.client.get(reverse("recording-list"))
        self.assertContains(response, "Jummah Khutbah")

        # 7. Verify anonymous user can also see it
        self.client.logout()
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

    def test_full_archive_flow(self):
        """User starts stream, stops it, archives it, verifies it's hidden."""
        # 1. Start stream
        self.client.post(reverse("livestream-start"), {"title": "Test Dhikr"})
        stream = LiveStream.objects.first()

        # 2. Stop stream
        stop_url = reverse("livestream-stop", kwargs={"stream_key": stream.stream_key})
        self.client.post(stop_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        # 3. Archive the recording (mode=archive)
        archive_url = reverse("livestream-archive", kwargs={"stream_key": stream.stream_key})
        response = self.client.post(
            archive_url, {"mode": "archive"},
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        rec_id = data["recording_id"]

        # 4. Recording detail returns 404 (it's archived)
        detail_url = reverse("recording-detail", kwargs={"pk": rec_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

        # 5. Recording does NOT appear in public list
        response = self.client.get(reverse("recording-list"))
        self.assertNotContains(response, "Test Dhikr")

        # 6. Recording DOES appear in /archived/ page
        response = self.client.get(reverse("archived-items"))
        self.assertContains(response, "Test Dhikr")

        # 7. Recording can be restored
        rec = Recording.objects.get(pk=rec_id)
        restore_url = reverse("recording-restore", kwargs={"pk": rec.pk})
        response = self.client.post(restore_url)
        self.assertTrue(response.json()["ok"])

        # 8. After restore, detail page works
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

    def test_full_discard_flow(self):
        """User starts stream, stops it, discards — no recording created."""
        # 1. Start stream
        self.client.post(reverse("livestream-start"), {"title": "Discarded Stream"})
        stream = LiveStream.objects.first()

        # 2. Stop stream
        stop_url = reverse("livestream-stop", kwargs={"stream_key": stream.stream_key})
        self.client.post(stop_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        # 3. Discard — user just navigates away (no archive call)
        # Verify no recording was created
        self.assertEqual(Recording.objects.count(), 0)

        # 4. Recordings page has no trace of the stream
        response = self.client.get(reverse("recording-list"))
        self.assertNotContains(response, "Discarded Stream")

        # 5. Archived page also has no trace
        response = self.client.get(reverse("archived-items"))
        self.assertNotContains(response, "Discarded Stream")

    def test_post_then_verify_no_audio_message(self):
        """Posted recording without audio shows 'No audio file' message, not a crash."""
        self.client.post(reverse("livestream-start"), {"title": "No Audio Test"})
        stream = LiveStream.objects.first()
        stop_url = reverse("livestream-stop", kwargs={"stream_key": stream.stream_key})
        self.client.post(stop_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        archive_url = reverse("livestream-archive", kwargs={"stream_key": stream.stream_key})
        resp = self.client.post(archive_url, {"mode": "post"}, content_type="application/json")
        rec_id = resp.json()["recording_id"]

        # Detail page should NOT crash — it should show a message instead
        response = self.client.get(reverse("recording-detail", kwargs={"pk": rec_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No audio file")

    def test_stop_already_stopped_then_archive(self):
        """Double-stopping and then archiving still works."""
        self.client.post(reverse("livestream-start"), {"title": "Double Stop"})
        stream = LiveStream.objects.first()
        stop_url = reverse("livestream-stop", kwargs={"stream_key": stream.stream_key})

        # Stop twice
        self.client.post(stop_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.client.post(stop_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        # Archive still works
        archive_url = reverse("livestream-archive", kwargs={"stream_key": stream.stream_key})
        response = self.client.post(archive_url, {"mode": "post"}, content_type="application/json")
        self.assertTrue(response.json()["ok"])
