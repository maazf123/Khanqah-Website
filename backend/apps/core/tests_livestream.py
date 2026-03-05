"""
TDD tests for the LiveStream feature (Chunk 2).

Tests cover:
1. LiveStream model (fields, defaults, ordering, __str__)
2. LiveStreamListView (public list of active streams)
3. LiveStreamStartView (staff-only stream creation)
4. LiveStreamBroadcastView (staff-only broadcast page)
5. LiveStreamListenView (public listen page)
6. LiveStreamStopView (staff-only stream stopping)
7. Navigation (Go Live link visibility)
"""

import uuid

from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from apps.core.models import LiveStream

# ---------------------------------------------------------------------------
# Module-level URL configuration used by @override_settings(ROOT_URLCONF=...)
# ---------------------------------------------------------------------------
from django.contrib import admin

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("", include("apps.recordings.urls")),
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
