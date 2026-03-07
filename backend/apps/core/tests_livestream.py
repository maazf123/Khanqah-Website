"""
TDD tests for the LiveStream feature.

Tests cover:
1. LiveStream model (fields, defaults, ordering, __str__)
2. LiveStreamListView (public list of active streams)
3. LiveStreamStartView (staff-only stream creation)
4. LiveStreamBroadcastView (staff-only broadcast page)
5. LiveStreamListenView (public listen page)
6. LiveStreamStopView (staff-only stream stopping)
7. Navigation (Go Live link visibility)
8. LiveStreamStatusAPIView (polling endpoint for stream status)
9. Listener page polling (JS polls status every 5 seconds)
"""

import uuid

from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from apps.core.models import LiveStream
from apps.core.views_home import HomeView

# ---------------------------------------------------------------------------
# Module-level URL configuration used by @override_settings(ROOT_URLCONF=...)
# ---------------------------------------------------------------------------
from django.contrib import admin

from apps.core.views_archive import ArchivedItemsView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("recordings/", include("apps.recordings.urls")),
    path("tags/", include("apps.tags.urls")),
    path("archived/", ArchivedItemsView.as_view(), name="archived-items"),
    path("", HomeView.as_view(), name="home"),
]


# ============================================================================
# 1. Model Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamModelTests(TestCase):
    """Tests for the LiveStream model fields, defaults, and behaviour."""

    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass", is_staff=True)

    def test_create_livestream(self):
        """Creating a LiveStream populates all expected fields."""
        stream = LiveStream.objects.create(title="Test Stream", created_by=self.user)
        self.assertEqual(stream.title, "Test Stream")
        self.assertTrue(stream.is_active)
        self.assertEqual(stream.created_by, self.user)
        self.assertIsNotNone(stream.stream_key)
        self.assertIsNotNone(stream.started_at)
        self.assertIsNone(stream.ended_at)

    def test_stream_key_is_uuid(self):
        """stream_key is a valid UUID instance."""
        stream = LiveStream.objects.create(title="UUID Test", created_by=self.user)
        self.assertIsInstance(stream.stream_key, uuid.UUID)

    def test_stream_key_auto_generated(self):
        """Creating a stream without an explicit key still generates one."""
        stream = LiveStream.objects.create(title="Auto Key", created_by=self.user)
        self.assertIsNotNone(stream.stream_key)
        # Verify it's a valid UUID by converting to string and back
        parsed = uuid.UUID(str(stream.stream_key))
        self.assertEqual(parsed, stream.stream_key)

    def test_stream_key_unique(self):
        """Two streams have different stream keys."""
        s1 = LiveStream.objects.create(title="Stream 1", created_by=self.user)
        s2 = LiveStream.objects.create(title="Stream 2", created_by=self.user)
        self.assertNotEqual(s1.stream_key, s2.stream_key)

    def test_str_active(self):
        """__str__ shows 'Live' when the stream is active."""
        stream = LiveStream.objects.create(title="Active Stream", created_by=self.user)
        self.assertIn("Live", str(stream))
        self.assertNotIn("Ended", str(stream))
        self.assertEqual(str(stream), "Active Stream (Live)")

    def test_str_ended(self):
        """__str__ shows 'Ended' when the stream is inactive."""
        stream = LiveStream.objects.create(
            title="Ended Stream", created_by=self.user, is_active=False
        )
        self.assertIn("Ended", str(stream))
        self.assertNotIn("Live", str(stream))
        self.assertEqual(str(stream), "Ended Stream (Ended)")

    def test_default_is_active_true(self):
        """New streams default to is_active=True."""
        stream = LiveStream.objects.create(title="Default Active", created_by=self.user)
        self.assertTrue(stream.is_active)

    def test_ended_at_null_by_default(self):
        """ended_at is None for a newly created stream."""
        stream = LiveStream.objects.create(title="No End", created_by=self.user)
        self.assertIsNone(stream.ended_at)

    def test_ordering(self):
        """Streams are ordered by -started_at (newest first)."""
        from datetime import timedelta
        s1 = LiveStream.objects.create(title="First", created_by=self.user)
        s2 = LiveStream.objects.create(title="Second", created_by=self.user)
        # Force distinct timestamps since auto_now_add can give same value in fast tests
        LiveStream.objects.filter(pk=s1.pk).update(started_at=timezone.now() - timedelta(minutes=5))
        LiveStream.objects.filter(pk=s2.pk).update(started_at=timezone.now())
        streams = list(LiveStream.objects.all())
        self.assertEqual(streams[0], s2)
        self.assertEqual(streams[1], s1)


# ============================================================================
# 2. LiveStreamListView Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamListViewTests(TestCase):
    """Tests for the public list of active live streams."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("admin", password="pass", is_staff=True)
        self.url = reverse("livestream-list")

    def test_list_view_status_200(self):
        """Anonymous GET to the list page returns HTTP 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_list_view_uses_correct_template(self):
        """The list view uses 'livestream/livestream_list.html'."""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "livestream/livestream_list.html")

    def test_list_shows_only_active_streams(self):
        """Only active streams appear in the list; inactive ones are excluded."""
        active = LiveStream.objects.create(
            title="Active", created_by=self.user, is_active=True
        )
        inactive = LiveStream.objects.create(
            title="Inactive", created_by=self.user, is_active=False
        )
        response = self.client.get(self.url)
        streams = list(response.context["livestreams"])
        stream_ids = {s.pk for s in streams}
        self.assertIn(active.pk, stream_ids)
        self.assertNotIn(inactive.pk, stream_ids)

    def test_list_empty_when_no_active_streams(self):
        """When no active streams exist, the list is empty."""
        LiveStream.objects.create(
            title="Ended", created_by=self.user, is_active=False
        )
        response = self.client.get(self.url)
        streams = response.context["livestreams"]
        self.assertEqual(len(streams), 0)

    def test_list_context_contains_streams(self):
        """The context contains a 'livestream_list' key with stream objects."""
        LiveStream.objects.create(title="Stream A", created_by=self.user)
        response = self.client.get(self.url)
        self.assertIn("livestreams", response.context)
        self.assertEqual(len(response.context["livestreams"]), 1)


# ============================================================================
# 3. LiveStreamStartView Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamStartViewTests(TestCase):
    """Tests for the staff-only stream creation view."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user("user", password="pass")
        self.url = reverse("livestream-start")

    def test_start_requires_login(self):
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_start_requires_staff(self):
        """Logged-in non-staff users receive 403 Forbidden."""
        self.client.login(username="user", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_start_get_renders_form(self):
        """Staff GET request returns 200 with a form."""
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("<form", content)

    def test_start_post_creates_stream(self):
        """Staff POST with a valid title creates a new LiveStream."""
        self.client.login(username="admin", password="pass")
        self.assertEqual(LiveStream.objects.count(), 0)
        self.client.post(self.url, {"title": "New Live Session"})
        self.assertEqual(LiveStream.objects.count(), 1)
        stream = LiveStream.objects.first()
        self.assertEqual(stream.title, "New Live Session")

    def test_start_post_redirects_to_broadcast(self):
        """After creating a stream, the user is redirected to the broadcast page."""
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url, {"title": "New Live Session"})
        stream = LiveStream.objects.first()
        expected_url = reverse(
            "livestream-broadcast", kwargs={"stream_key": stream.stream_key}
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_start_post_sets_created_by(self):
        """The newly created stream's created_by is the current staff user."""
        self.client.login(username="admin", password="pass")
        self.client.post(self.url, {"title": "My Stream"})
        stream = LiveStream.objects.first()
        self.assertEqual(stream.created_by, self.staff_user)

    def test_start_post_empty_title_creates_stream_with_auto_title(self):
        """POST with an empty title auto-generates a date-based title."""
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url, {"title": ""})
        self.assertEqual(LiveStream.objects.count(), 1)
        self.assertEqual(response.status_code, 302)
        stream = LiveStream.objects.first()
        self.assertIn("Live Stream", stream.title)


# ============================================================================
# 4. LiveStreamBroadcastView Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamBroadcastViewTests(TestCase):
    """Tests for the staff-only broadcast page."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.other_staff = User.objects.create_user(
            "other_staff", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user("user", password="pass")
        self.superuser = User.objects.create_superuser("super", password="pass")
        self.stream = LiveStream.objects.create(
            title="Broadcast Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-broadcast", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_broadcast_requires_login(self):
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_broadcast_requires_staff(self):
        """Non-staff users receive 403 Forbidden."""
        self.client.login(username="user", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_broadcast_shows_for_creator(self):
        """The staff user who created the stream can access the broadcast page."""
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_broadcast_shows_stream_key_for_sharing(self):
        """The broadcast page contains the stream key or listen URL for sharing."""
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        content = response.content.decode()
        # Should contain either the stream_key itself or the listen URL
        listen_url = reverse(
            "livestream-listen", kwargs={"stream_key": self.stream.stream_key}
        )
        has_key = str(self.stream.stream_key) in content
        has_listen_url = listen_url in content
        self.assertTrue(
            has_key or has_listen_url,
            "Broadcast page should contain the stream key or listen URL for sharing.",
        )

    def test_broadcast_404_if_inactive(self):
        """If the stream has ended (is_active=False), return 404."""
        self.stream.is_active = False
        self.stream.save()
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_broadcast_404_for_other_staff(self):
        """A different staff user (non-superuser) cannot access the broadcast page.
        Returns 404 because the queryset is filtered to only show the creator's streams."""
        self.client.login(username="other_staff", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_broadcast_allowed_for_superuser(self):
        """A superuser can access any broadcast page regardless of creator."""
        self.client.login(username="super", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


# ============================================================================
# 5. LiveStreamListenView Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamListenViewTests(TestCase):
    """Tests for the public listen page."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("admin", password="pass", is_staff=True)
        self.stream = LiveStream.objects.create(
            title="Listen Test", created_by=self.user
        )
        self.url = reverse(
            "livestream-listen", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_listen_accessible_anonymous(self):
        """Anonymous users can access the listen page (no login required)."""
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(response.status_code, 200)

    def test_listen_returns_200_for_active(self):
        """An active stream returns HTTP 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_listen_shows_ended_for_inactive(self):
        """An inactive stream returns HTTP 200 with ended state."""
        self.stream.is_active = False
        self.stream.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertIn("ended", content)

    def test_listen_404_for_nonexistent_key(self):
        """A random UUID that does not correspond to any stream returns 404."""
        fake_key = uuid.uuid4()
        url = reverse("livestream-listen", kwargs={"stream_key": fake_key})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_listen_uses_correct_template(self):
        """The listen page uses 'livestream/livestream_listen.html'."""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "livestream/livestream_listen.html")

    def test_listen_context_has_stream(self):
        """The template context contains the 'livestream' object."""
        response = self.client.get(self.url)
        self.assertIn("livestream", response.context)
        self.assertEqual(response.context["livestream"], self.stream)


# ============================================================================
# 6. LiveStreamStopView Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamStopViewTests(TestCase):
    """Tests for the staff-only stream-stopping view."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.other_staff = User.objects.create_user(
            "other_staff", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user("user", password="pass")
        self.superuser = User.objects.create_superuser("super", password="pass")
        self.stream = LiveStream.objects.create(
            title="Stop Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-stop", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_stop_requires_login(self):
        """Anonymous users are redirected to the login page."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_stop_requires_staff(self):
        """Non-staff users receive 403 Forbidden."""
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_stop_post_deactivates_stream(self):
        """POST sets the stream's is_active to False."""
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.stream.refresh_from_db()
        self.assertFalse(self.stream.is_active)

    def test_stop_post_sets_ended_at(self):
        """POST sets ended_at to approximately the current time."""
        self.client.login(username="admin", password="pass")
        before = timezone.now()
        self.client.post(self.url)
        after = timezone.now()
        self.stream.refresh_from_db()
        self.assertIsNotNone(self.stream.ended_at)
        self.assertGreaterEqual(self.stream.ended_at, before)
        self.assertLessEqual(self.stream.ended_at, after)

    def test_stop_get_not_allowed(self):
        """GET requests return HTTP 405 Method Not Allowed."""
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_stop_redirects_to_list(self):
        """After stopping, the user is redirected to the livestream list."""
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        expected_url = reverse("livestream-list")
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_stop_only_by_creator_or_superuser(self):
        """A different staff user (non-superuser) cannot stop another's stream.
        Returns 404 because the queryset is filtered to only the creator's streams."""
        self.client.login(username="other_staff", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        # Stream should remain active
        self.stream.refresh_from_db()
        self.assertTrue(self.stream.is_active)

    def test_stop_allowed_for_superuser(self):
        """A superuser can stop any stream."""
        self.client.login(username="super", password="pass")
        response = self.client.post(self.url)
        self.stream.refresh_from_db()
        self.assertFalse(self.stream.is_active)
        expected_url = reverse("livestream-list")
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)


# ============================================================================
# 7. Navigation Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamNavigationTests(TestCase):
    """Tests for the 'Go Live' link visibility in the site navigation."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )

    def test_nav_has_live_link_for_staff(self):
        """Staff users see a 'Go Live' link in the navigation bar."""
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("recording-list"))
        content = response.content.decode()
        self.assertIn("Go Live", content)

    def test_nav_no_go_live_for_anonymous(self):
        """Anonymous users do not see a 'Go Live' link in the navigation."""
        response = self.client.get(reverse("recording-list"))
        content = response.content.decode()
        self.assertNotIn("Go Live", content)


# ============================================================================
# 8. LiveStreamStatusAPIView Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamStatusAPIViewTests(TestCase):
    """Tests for the JSON status endpoint that listeners poll."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("admin", password="pass", is_staff=True)
        self.stream = LiveStream.objects.create(
            title="Status Test", created_by=self.user
        )
        self.url = reverse(
            "livestream-status", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_status_returns_200(self):
        """GET to the status endpoint returns HTTP 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_status_returns_json(self):
        """The response Content-Type is application/json."""
        response = self.client.get(self.url)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_status_active_stream(self):
        """An active stream returns is_active=true in JSON."""
        response = self.client.get(self.url)
        data = response.json()
        self.assertTrue(data["is_active"])

    def test_status_ended_stream(self):
        """An ended stream returns is_active=false in JSON."""
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()
        response = self.client.get(self.url)
        data = response.json()
        self.assertFalse(data["is_active"])

    def test_status_contains_title(self):
        """The response JSON includes the stream title."""
        response = self.client.get(self.url)
        data = response.json()
        self.assertEqual(data["title"], "Status Test")

    def test_status_nonexistent_stream_returns_404(self):
        """A random UUID returns 404."""
        fake_key = uuid.uuid4()
        url = reverse("livestream-status", kwargs={"stream_key": fake_key})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_status_accessible_anonymous(self):
        """Anonymous users can access the status endpoint (no login required)."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_status_post_not_allowed(self):
        """POST to the status endpoint returns 405 Method Not Allowed."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)

    def test_status_reflects_realtime_change(self):
        """If the stream is stopped between two polls, the status changes."""
        # First poll: active
        response1 = self.client.get(self.url)
        self.assertTrue(response1.json()["is_active"])

        # Stop the stream
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()

        # Second poll: ended
        response2 = self.client.get(self.url)
        self.assertFalse(response2.json()["is_active"])


# ============================================================================
# 9. Listener Page Polling Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamListenerPollingTests(TestCase):
    """Tests that the listen page includes polling JS for stream status."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("admin", password="pass", is_staff=True)
        self.stream = LiveStream.objects.create(
            title="Polling Test", created_by=self.user
        )
        self.url = reverse(
            "livestream-listen", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_listen_page_contains_status_url(self):
        """The listen page JS includes the status API URL for polling."""
        response = self.client.get(self.url)
        html = response.content.decode()
        status_url = reverse(
            "livestream-status", kwargs={"stream_key": self.stream.stream_key}
        )
        self.assertIn(status_url, html)

    def test_listen_page_has_polling_interval(self):
        """The listen page JS sets up a polling interval (setInterval)."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("setInterval", html)

    def test_listen_page_has_5_second_interval(self):
        """The polling interval is 5000ms (5 seconds)."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("5000", html)

    def test_listen_page_polls_with_fetch(self):
        """The listen page uses fetch() to call the status endpoint."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("fetch(", html)

    def test_listen_page_checks_is_active(self):
        """The polling JS checks the is_active field from the response."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("is_active", html)

    def test_ended_stream_page_does_not_poll(self):
        """When the stream is already ended on page load, no polling JS runs."""
        self.stream.is_active = False
        self.stream.save()
        response = self.client.get(self.url)
        html = response.content.decode()
        # The ended template block should NOT contain polling logic
        self.assertNotIn("pollStreamStatus", html)

    def test_listen_page_clears_interval_on_end(self):
        """The JS clears the polling interval when the stream ends."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("clearInterval", html)


# ============================================================================
# 10. LiveStreamStopView — Graceful Handling of Already-Stopped Streams
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamStopAlreadyStoppedTests(TestCase):
    """Tests that stopping an already-stopped stream does not 404.

    Bug: LiveStreamStopView queries only is_active=True streams, so if the
    stream was already stopped (double-click, page reload, race condition),
    get_object_or_404 raises a 404. The view should handle this gracefully.
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.superuser = User.objects.create_superuser("super", password="pass")
        self.stream = LiveStream.objects.create(
            title="Already Stopped", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-stop", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_stop_already_inactive_stream_does_not_404(self):
        """Stopping a stream that is already inactive should NOT return 404."""
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 404)

    def test_stop_already_inactive_stream_redirects(self):
        """Stopping an already-inactive stream should redirect to the list."""
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        expected_url = reverse("livestream-list")
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_stop_already_inactive_stream_stays_inactive(self):
        """Stopping an already-inactive stream does not re-activate it or
        change its ended_at timestamp."""
        original_ended_at = timezone.now()
        self.stream.is_active = False
        self.stream.ended_at = original_ended_at
        self.stream.save()
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.stream.refresh_from_db()
        self.assertFalse(self.stream.is_active)
        self.assertEqual(self.stream.ended_at, original_ended_at)

    def test_double_stop_does_not_error(self):
        """Stopping a stream twice in quick succession does not crash."""
        self.client.login(username="admin", password="pass")
        response1 = self.client.post(self.url)
        response2 = self.client.post(self.url)
        # First stop should work normally
        self.assertNotEqual(response1.status_code, 404)
        # Second stop should also not 404
        self.assertNotEqual(response2.status_code, 404)

    def test_double_stop_stream_stays_inactive(self):
        """After two stops, the stream is still inactive with ended_at set."""
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.client.post(self.url)
        self.stream.refresh_from_db()
        self.assertFalse(self.stream.is_active)
        self.assertIsNotNone(self.stream.ended_at)

    def test_stop_nonexistent_stream_still_404(self):
        """A completely nonexistent stream_key should still 404."""
        fake_key = uuid.uuid4()
        url = reverse("livestream-stop", kwargs={"stream_key": fake_key})
        self.client.login(username="admin", password="pass")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_stop_already_inactive_other_staff_still_blocked(self):
        """Another staff user cannot stop someone else's stream even if it's
        already inactive — they should not get a 404 crash but they also
        shouldn't be able to affect the stream."""
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()
        other = User.objects.create_user("other", password="pass", is_staff=True)
        self.client.login(username="other", password="pass")
        response = self.client.post(self.url)
        # Should be 404 because they don't own it (not a crash — just no match)
        self.assertEqual(response.status_code, 404)

    def test_superuser_can_stop_already_inactive_stream(self):
        """Superuser stopping an already-inactive stream gets a graceful redirect."""
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.client.login(username="super", password="pass")
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 404)
        expected_url = reverse("livestream-list")
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)


# ============================================================================
# 11. Stop-Confirmation Modal Tests (replaces browser confirm() dialog)
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamStopConfirmationModalTests(TestCase):
    """Tests that the broadcast page has a styled stop-confirmation modal
    instead of a native browser confirm() dialog.

    The modal should:
    - Exist in the HTML with a recognisable id
    - Contain a warning message about ending the stream
    - Have an "End Stream" confirmation button that submits the stop form
    - Have a "Cancel" button that closes the modal
    - NOT use the native window.confirm() for the stop action
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Modal Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": self.stream.stream_key},
        )
        self.client.login(username="admin", password="pass")

    def test_broadcast_page_contains_stop_modal(self):
        """The broadcast page must contain a stop-confirmation modal overlay."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="stop-confirm-modal"', html)

    def test_stop_modal_has_overlay(self):
        """The modal must use the modal-overlay class for backdrop."""
        response = self.client.get(self.url)
        html = response.content.decode()
        # The modal element should have class modal-overlay
        self.assertIn('class="modal-overlay"', html)

    def test_stop_modal_has_warning_message(self):
        """The modal must contain a warning about ending the stream."""
        response = self.client.get(self.url)
        html = response.content.decode().lower()
        self.assertIn("end", html)
        self.assertIn("stream", html)
        # Should mention listeners being disconnected
        self.assertIn("listener", html)

    def test_stop_modal_has_confirm_button(self):
        """The modal must have a confirm button to actually end the stream."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="stop-confirm-btn"', html)

    def test_stop_modal_has_cancel_button(self):
        """The modal must have a cancel button to dismiss without stopping."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="stop-cancel-btn"', html)

    def test_stop_modal_confirm_button_is_danger_styled(self):
        """The confirm button should use danger styling (btn-danger class)."""
        response = self.client.get(self.url)
        html = response.content.decode()
        # Find the confirm button and check it has btn-danger
        import re
        btn_match = re.search(r'id="stop-confirm-btn"[^>]*class="([^"]*)"', html)
        if not btn_match:
            btn_match = re.search(r'class="([^"]*)"[^>]*id="stop-confirm-btn"', html)
        self.assertIsNotNone(btn_match, "stop-confirm-btn must exist with a class")
        self.assertIn("btn-danger", btn_match.group(1))

    def test_no_window_confirm_for_stop(self):
        """The broadcast page must NOT use window.confirm() for the stop action.
        The old code had: confirm("Are you sure you want to stop this stream...")
        This should be replaced by the modal."""
        response = self.client.get(self.url)
        html = response.content.decode()
        # The old pattern was an event listener on stop-form using confirm()
        self.assertNotIn('confirm("Are you sure', html)
        self.assertNotIn("confirm('Are you sure", html)

    def test_stop_button_opens_modal_not_submits_form(self):
        """The 'Stop Stream' button should open the modal, not directly submit."""
        response = self.client.get(self.url)
        html = response.content.decode()
        # The stop button should trigger showing the modal
        self.assertIn("stop-confirm-modal", html)


# ============================================================================
# 12. Stop via AJAX returns JSON (for post-stream modal flow)
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamStopAJAXTests(TestCase):
    """When the stop endpoint is called via AJAX (X-Requested-With header),
    it should return JSON instead of a redirect, so the broadcast page JS
    can show the post-stream modal without leaving the page."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="AJAX Stop Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-stop", kwargs={"stream_key": self.stream.stream_key}
        )
        self.client.login(username="admin", password="pass")

    def test_ajax_stop_returns_json(self):
        """AJAX POST returns JSON with ok=true."""
        response = self.client.post(
            self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    def test_ajax_stop_deactivates_stream(self):
        """AJAX stop still deactivates the stream."""
        self.client.post(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.stream.refresh_from_db()
        self.assertFalse(self.stream.is_active)
        self.assertIsNotNone(self.stream.ended_at)

    def test_ajax_stop_already_inactive_returns_json(self):
        """AJAX stop on already-inactive stream returns JSON gracefully."""
        self.stream.is_active = False
        self.stream.ended_at = timezone.now()
        self.stream.save()
        response = self.client.post(
            self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    def test_regular_post_still_redirects(self):
        """Regular (non-AJAX) POST still redirects as before."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)


# ============================================================================
# 13. Post-Stream Modal HTML Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class PostStreamModalTests(TestCase):
    """The broadcast page must contain a post-stream modal that appears
    after the stream is stopped, giving the broadcaster the option to
    archive the stream as a recording or discard it."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Post-Stream Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": self.stream.stream_key},
        )
        self.client.login(username="admin", password="pass")

    def test_broadcast_page_contains_post_stream_modal(self):
        """The broadcast page must contain a post-stream modal."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="post-stream-modal"', html)

    def test_post_stream_modal_has_archive_button(self):
        """The post-stream modal must have an archive button."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="archive-btn"', html)

    def test_post_stream_modal_has_discard_button(self):
        """The post-stream modal must have a discard button."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="discard-btn"', html)

    def test_post_stream_modal_shows_stream_title(self):
        """The post-stream modal must reference the stream title."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("Post-Stream Test", html)

    def test_post_stream_modal_mentions_archive(self):
        """The modal should mention archiving/saving the recording."""
        response = self.client.get(self.url)
        html = response.content.decode().lower()
        self.assertIn("archive", html)

    def test_post_stream_modal_has_overlay(self):
        """The modal uses the modal-overlay pattern."""
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="post-stream-modal"', html)
        self.assertIn('class="modal-overlay"', html)


# ============================================================================
# 14. LiveStream Archive Endpoint Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_livestream")
class LiveStreamArchiveEndpointTests(TestCase):
    """Tests for the POST /livestream/<uuid>/archive/ endpoint that creates
    a Recording from a finished LiveStream's metadata."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True,
            first_name="Test", last_name="Speaker",
        )
        self.regular_user = User.objects.create_user("user", password="pass")
        self.stream = LiveStream.objects.create(
            title="Archive Me", created_by=self.staff_user,
            is_active=False,
        )
        self.stream.ended_at = timezone.now()
        self.stream.save()
        self.url = reverse(
            "livestream-archive", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_archive_requires_login(self):
        """Anonymous users are redirected to login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_archive_requires_staff(self):
        """Non-staff users get 403."""
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_archive_creates_recording(self):
        """POST creates a new Recording."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        self.assertEqual(Recording.objects.count(), 0)
        self.client.post(self.url)
        self.assertEqual(Recording.objects.count(), 1)

    def test_archive_returns_json_with_ok(self):
        """POST returns JSON with ok=true."""
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    def test_archive_returns_recording_id(self):
        """The JSON response includes the new recording's ID."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        data = response.json()
        self.assertIn("recording_id", data)
        self.assertTrue(Recording.objects.filter(pk=data["recording_id"]).exists())

    def test_archived_recording_has_stream_title(self):
        """The Recording title matches the LiveStream title."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        rec = Recording.objects.first()
        self.assertEqual(rec.title, "Archive Me")

    def test_archived_recording_has_speaker_from_creator(self):
        """The Recording speaker is the stream creator's name."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        rec = Recording.objects.first()
        self.assertEqual(rec.speaker, "Test Speaker")

    def test_archived_recording_has_today_as_date(self):
        """The Recording's recording_date is today."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        rec = Recording.objects.first()
        self.assertEqual(rec.recording_date, timezone.now().date())

    def test_archived_recording_has_no_audio_file(self):
        """The Recording has an empty audio_file (metadata-only archive)."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        rec = Recording.objects.first()
        self.assertFalse(rec.audio_file)

    def test_cannot_archive_active_stream(self):
        """Archiving an active stream returns an error."""
        self.stream.is_active = True
        self.stream.save()
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        data = response.json()
        self.assertFalse(data["ok"])

    def test_archive_nonexistent_stream_404(self):
        """Archiving a nonexistent stream returns 404."""
        fake_key = uuid.uuid4()
        url = reverse("livestream-archive", kwargs={"stream_key": fake_key})
        self.client.login(username="admin", password="pass")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_archive_get_not_allowed(self):
        """GET to the archive endpoint returns 405."""
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_double_archive_creates_two_recordings(self):
        """Archiving twice creates two separate recordings (idempotency not required)."""
        from apps.recordings.models import Recording
        self.client.login(username="admin", password="pass")
        self.client.post(self.url)
        self.client.post(self.url)
        self.assertEqual(Recording.objects.count(), 2)
