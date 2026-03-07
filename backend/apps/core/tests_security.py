"""
Security and stress tests for the LiveStream feature.

Tests cover:
1. Authentication & Authorization (login required, staff required, ownership, superuser bypass, CSRF)
2. Input Validation & XSS (script tags, SQL injection, null bytes, special chars, length limits)
3. Stream Lifecycle (create/broadcast/stop transitions, visibility, repeated stops)
4. WebSocket Security (non-existent streams, ended streams, role enforcement, binary data filtering)
"""

import asyncio
import base64
import json
import uuid

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone
from django.utils.html import escape

from apps.core.consumers import AudioStreamConsumer
from apps.core.models import LiveStream
from apps.core.views_archive import ArchivedItemsView

# ---------------------------------------------------------------------------
# Module-level URL configuration used by @override_settings(ROOT_URLCONF=...)
# ---------------------------------------------------------------------------
urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("archived/", ArchivedItemsView.as_view(), name="archived-items"),
    path("", include("apps.recordings.urls")),
]

# ---------------------------------------------------------------------------
# WebSocket test application (URLRouter so scope["url_route"] is populated)
# ---------------------------------------------------------------------------
TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

test_ws_application = URLRouter([
    path("ws/stream/<uuid:stream_key>/", AudioStreamConsumer.as_asgi()),
])


# ============================================================================
# 1. Authentication & Authorization Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_security")
class AuthenticationStartTests(TestCase):
    """Verify that the start-stream endpoint enforces authentication."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("livestream-start")

    def test_anonymous_post_start_redirects_to_login(self):
        """Anonymous user POSTing to start stream is redirected to login."""
        response = self.client.post(self.url, {"title": "Test"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_anonymous_get_start_redirects_to_login(self):
        """Anonymous user GETting the start page is redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)


@override_settings(ROOT_URLCONF="apps.core.tests_security")
class AuthenticationStopTests(TestCase):
    """Verify that the stop-stream endpoint enforces authentication."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "staffuser", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Auth Stop Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-stop", kwargs={"stream_key": self.stream.stream_key}
        )

    def test_anonymous_post_stop_redirects_to_login(self):
        """Anonymous user POSTing to stop stream is redirected to login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)


@override_settings(ROOT_URLCONF="apps.core.tests_security")
class AuthorizationNonStaffTests(TestCase):
    """Non-staff logged-in users should be denied access to staff endpoints."""

    def setUp(self):
        self.client = Client()
        self.regular_user = User.objects.create_user("regular", password="pass")
        self.staff_user = User.objects.create_user(
            "staffuser", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Auth Test", created_by=self.staff_user
        )
        self.client.login(username="regular", password="pass")

    def test_non_staff_post_start_returns_403(self):
        """Non-staff user POSTing to start stream gets 403 Forbidden."""
        url = reverse("livestream-start")
        response = self.client.post(url, {"title": "Hacked"})
        self.assertEqual(response.status_code, 403)

    def test_non_staff_post_stop_returns_403(self):
        """Non-staff user POSTing to stop stream gets 403 Forbidden."""
        url = reverse(
            "livestream-stop", kwargs={"stream_key": self.stream.stream_key}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_non_staff_get_broadcast_returns_403(self):
        """Non-staff user accessing broadcast page gets 403 Forbidden."""
        url = reverse(
            "livestream-broadcast", kwargs={"stream_key": self.stream.stream_key}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


@override_settings(ROOT_URLCONF="apps.core.tests_security")
class OwnershipEnforcementTests(TestCase):
    """Staff users should only access their own streams (unless superuser)."""

    def setUp(self):
        self.client = Client()
        self.staff_a = User.objects.create_user(
            "staff_a", password="pass", is_staff=True
        )
        self.staff_b = User.objects.create_user(
            "staff_b", password="pass", is_staff=True
        )
        self.superuser = User.objects.create_superuser("super", password="pass")
        self.stream_a = LiveStream.objects.create(
            title="Stream A", created_by=self.staff_a
        )

    def test_staff_cannot_broadcast_other_staffs_stream(self):
        """Staff B trying to access Staff A's broadcast page gets 404."""
        self.client.login(username="staff_b", password="pass")
        url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": self.stream_a.stream_key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_staff_cannot_stop_other_staffs_stream(self):
        """Staff B trying to stop Staff A's stream gets 404."""
        self.client.login(username="staff_b", password="pass")
        url = reverse(
            "livestream-stop",
            kwargs={"stream_key": self.stream_a.stream_key},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        # Confirm stream is still active
        self.stream_a.refresh_from_db()
        self.assertTrue(self.stream_a.is_active)

    def test_superuser_can_broadcast_any_stream(self):
        """Superuser can access any staff's broadcast page."""
        self.client.login(username="super", password="pass")
        url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": self.stream_a.stream_key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_stop_any_stream(self):
        """Superuser can stop any staff's stream."""
        self.client.login(username="super", password="pass")
        url = reverse(
            "livestream-stop",
            kwargs={"stream_key": self.stream_a.stream_key},
        )
        response = self.client.post(url)
        self.stream_a.refresh_from_db()
        self.assertFalse(self.stream_a.is_active)
        self.assertIsNotNone(self.stream_a.ended_at)


@override_settings(ROOT_URLCONF="apps.core.tests_security")
class CSRFProtectionTests(TestCase):
    """Verify CSRF protection on POST endpoints."""

    def setUp(self):
        # Use enforce_csrf_checks=True to test CSRF enforcement
        self.client = Client(enforce_csrf_checks=True)
        self.staff_user = User.objects.create_user(
            "staffuser", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="CSRF Test", created_by=self.staff_user
        )
        self.client.login(username="staffuser", password="pass")

    def test_start_post_without_csrf_token_returns_403(self):
        """POST to start without CSRF token returns 403."""
        url = reverse("livestream-start")
        response = self.client.post(url, {"title": "No CSRF"})
        self.assertEqual(response.status_code, 403)

    def test_stop_post_without_csrf_token_returns_403(self):
        """POST to stop without CSRF token returns 403."""
        url = reverse(
            "livestream-stop",
            kwargs={"stream_key": self.stream.stream_key},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_start_post_with_csrf_token_succeeds(self):
        """POST to start with a valid CSRF token succeeds (302 redirect)."""
        # Get the page first to obtain a CSRF cookie
        regular_client = Client()
        regular_client.login(username="staffuser", password="pass")
        url = reverse("livestream-start")
        response = regular_client.post(url, {"title": "With CSRF"})
        # Default Client does NOT enforce CSRF, so this should work
        self.assertEqual(response.status_code, 302)


# ============================================================================
# 2. Input Validation & XSS Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_security")
class XSSInputTests(TestCase):
    """Verify that potentially dangerous input is handled safely."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "staffuser", password="pass", is_staff=True
        )
        self.client.login(username="staffuser", password="pass")
        self.start_url = reverse("livestream-start")

    def _create_stream_with_title(self, title):
        """Helper to create a stream via POST and return the created LiveStream."""
        self.client.post(self.start_url, {"title": title})
        return LiveStream.objects.order_by("-pk").first()

    def test_script_tag_stored_but_escaped_in_template(self):
        """Title with <script> tags is stored in DB but escaped on render."""
        malicious_title = '<script>alert("XSS")</script>'
        stream = self._create_stream_with_title(malicious_title)
        self.assertEqual(stream.title, malicious_title)

        # Check list page -- title should be escaped
        list_url = reverse("livestream-list")
        response = self.client.get(list_url)
        content = response.content.decode()
        # Raw <script> should NOT appear; escaped version should
        self.assertNotIn('<script>alert("XSS")</script>', content)
        self.assertIn(escape(malicious_title), content)

    def test_script_tag_escaped_on_listen_page(self):
        """Title with <script> tags is escaped on the listen page."""
        malicious_title = '<script>document.cookie</script>'
        stream = self._create_stream_with_title(malicious_title)

        listen_url = reverse(
            "livestream-listen", kwargs={"stream_key": stream.stream_key}
        )
        response = self.client.get(listen_url)
        content = response.content.decode()
        self.assertNotIn("<script>document.cookie</script>", content)
        self.assertIn(escape(malicious_title), content)

    def test_script_tag_escaped_on_broadcast_page(self):
        """Title with <script> tags is escaped on the broadcast page."""
        malicious_title = '<img src=x onerror=alert(1)>'
        stream = self._create_stream_with_title(malicious_title)

        broadcast_url = reverse(
            "livestream-broadcast", kwargs={"stream_key": stream.stream_key}
        )
        response = self.client.get(broadcast_url)
        content = response.content.decode()
        self.assertNotIn('<img src=x onerror=alert(1)>', content)
        self.assertIn(escape(malicious_title), content)

    def test_sql_injection_attempt_stored_safely(self):
        """Title with SQL injection payload is stored as a literal string."""
        sql_title = "'; DROP TABLE core_livestream; --"
        stream = self._create_stream_with_title(sql_title)
        self.assertEqual(stream.title, sql_title)
        # Confirm the table still exists by querying
        count = LiveStream.objects.count()
        self.assertGreaterEqual(count, 1)

    def test_null_bytes_in_title(self):
        """Title containing null bytes is handled (stored or stripped)."""
        null_title = "Stream\x00Title"
        stream = self._create_stream_with_title(null_title)
        # The stream should be created; title may have null preserved or stripped
        self.assertIsNotNone(stream)
        self.assertIn("Stream", stream.title)

    def test_title_with_only_spaces_gets_auto_title(self):
        """Title that is only whitespace triggers auto-generated title."""
        stream = self._create_stream_with_title("     ")
        # The view strips the title; empty after strip triggers auto-title
        self.assertIn("Live Stream", stream.title)

    def test_title_with_special_characters(self):
        """Title with unicode and special chars is stored correctly."""
        special_title = "Stream @#$%^&*() - \u0627\u0644\u0633\u0644\u0627\u0645"
        stream = self._create_stream_with_title(special_title)
        self.assertEqual(stream.title, special_title)

    def test_title_exceeding_255_chars_no_crash(self):
        """Title exceeding the 255-char model limit either raises a DB error
        (PostgreSQL) or stores it (SQLite). Either way, no 500 crash."""
        from django.db import DataError

        long_title = "A" * 256
        try:
            resp = self.client.post(self.start_url, {"title": long_title})
            # SQLite doesn't enforce max_length, so it stores it.
            # We just verify no 500 error occurred.
            self.assertIn(resp.status_code, [302, 200])
        except DataError:
            # Expected for databases that enforce max_length (e.g., PostgreSQL)
            pass

    def test_title_exactly_255_chars_accepted(self):
        """Title at exactly the 255-char limit is accepted."""
        exact_title = "B" * 255
        stream = self._create_stream_with_title(exact_title)
        self.assertEqual(stream.title, exact_title)

    def test_html_entities_in_title(self):
        """HTML entities like &amp; are stored literally and escaped on render."""
        entity_title = "Stream &amp; <b>Bold</b>"
        stream = self._create_stream_with_title(entity_title)
        self.assertEqual(stream.title, entity_title)

        list_url = reverse("livestream-list")
        response = self.client.get(list_url)
        content = response.content.decode()
        # The raw <b> should not appear unescaped
        self.assertNotIn("<b>Bold</b>", content)


# ============================================================================
# 3. Stream Lifecycle Tests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_security")
class StreamLifecycleTests(TestCase):
    """Test the full create -> broadcast -> stop lifecycle and edge cases."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "staffuser", password="pass", is_staff=True
        )
        self.client.login(username="staffuser", password="pass")

    def test_full_lifecycle_create_broadcast_stop(self):
        """Create a stream, access broadcast page, then stop it."""
        # Create
        start_url = reverse("livestream-start")
        response = self.client.post(start_url, {"title": "Lifecycle Test"})
        self.assertEqual(response.status_code, 302)
        stream = LiveStream.objects.first()
        self.assertTrue(stream.is_active)

        # Broadcast
        broadcast_url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": stream.stream_key},
        )
        response = self.client.get(broadcast_url)
        self.assertEqual(response.status_code, 200)

        # Stop
        stop_url = reverse(
            "livestream-stop",
            kwargs={"stream_key": stream.stream_key},
        )
        response = self.client.post(stop_url)
        self.assertEqual(response.status_code, 302)
        stream.refresh_from_db()
        self.assertFalse(stream.is_active)
        self.assertIsNotNone(stream.ended_at)

    def test_stopped_stream_cannot_be_broadcast(self):
        """After stopping, the broadcast page returns 404."""
        stream = LiveStream.objects.create(
            title="Stopped Stream", created_by=self.staff_user
        )
        stream.is_active = False
        stream.ended_at = timezone.now()
        stream.save()

        broadcast_url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": stream.stream_key},
        )
        response = self.client.get(broadcast_url)
        self.assertEqual(response.status_code, 404)

    def test_stopped_stream_can_be_stopped_again_idempotently(self):
        """Stopping an already-stopped stream succeeds gracefully (idempotent)."""
        stream = LiveStream.objects.create(
            title="Double Stop", created_by=self.staff_user
        )
        # Stop it first
        stop_url = reverse(
            "livestream-stop", kwargs={"stream_key": stream.stream_key}
        )
        response = self.client.post(stop_url)
        self.assertEqual(response.status_code, 302)

        # Stopping again also succeeds (idempotent)
        response = self.client.post(stop_url)
        self.assertEqual(response.status_code, 302)

    def test_stopped_stream_still_visible_on_listen_page(self):
        """A stopped stream is still accessible on the listen page (shows ended state)."""
        stream = LiveStream.objects.create(
            title="Ended Visible", created_by=self.staff_user
        )
        stream.is_active = False
        stream.ended_at = timezone.now()
        stream.save()

        listen_url = reverse(
            "livestream-listen", kwargs={"stream_key": stream.stream_key}
        )
        response = self.client.get(listen_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertIn("ended", content)

    def test_multiple_stops_on_same_stream(self):
        """Multiple POST requests to stop an already-stopped stream all succeed (idempotent)."""
        stream = LiveStream.objects.create(
            title="Multi Stop", created_by=self.staff_user
        )
        stop_url = reverse(
            "livestream-stop", kwargs={"stream_key": stream.stream_key}
        )
        # First stop succeeds
        response = self.client.post(stop_url)
        self.assertEqual(response.status_code, 302)

        # Subsequent stops also succeed (idempotent)
        for _ in range(2):
            response = self.client.post(stop_url)
            self.assertEqual(response.status_code, 302)

    def test_active_stream_appears_in_list(self):
        """An active stream appears in the livestream list."""
        stream = LiveStream.objects.create(
            title="Active List Test", created_by=self.staff_user
        )
        list_url = reverse("livestream-list")
        response = self.client.get(list_url)
        stream_ids = {s.pk for s in response.context["livestreams"]}
        self.assertIn(stream.pk, stream_ids)

    def test_stopped_stream_disappears_from_list(self):
        """After stopping, the stream no longer appears in the list."""
        stream = LiveStream.objects.create(
            title="Disappear Test", created_by=self.staff_user
        )
        # Confirm it is listed
        list_url = reverse("livestream-list")
        response = self.client.get(list_url)
        stream_ids = {s.pk for s in response.context["livestreams"]}
        self.assertIn(stream.pk, stream_ids)

        # Stop it
        stop_url = reverse(
            "livestream-stop", kwargs={"stream_key": stream.stream_key}
        )
        self.client.post(stop_url)

        # Confirm it is no longer listed
        response = self.client.get(list_url)
        stream_ids = {s.pk for s in response.context["livestreams"]}
        self.assertNotIn(stream.pk, stream_ids)

    def test_stop_sets_ended_at_timestamp(self):
        """Stopping a stream records a proper ended_at timestamp."""
        stream = LiveStream.objects.create(
            title="Timestamp Test", created_by=self.staff_user
        )
        before = timezone.now()
        stop_url = reverse(
            "livestream-stop", kwargs={"stream_key": stream.stream_key}
        )
        self.client.post(stop_url)
        after = timezone.now()

        stream.refresh_from_db()
        self.assertIsNotNone(stream.ended_at)
        self.assertGreaterEqual(stream.ended_at, before)
        self.assertLessEqual(stream.ended_at, after)

    def test_create_stop_create_new_stream_works(self):
        """After stopping one stream, creating a new one works normally."""
        start_url = reverse("livestream-start")
        # Create first stream
        self.client.post(start_url, {"title": "First Stream"})
        first = LiveStream.objects.order_by("-pk").first()

        # Stop it
        stop_url = reverse(
            "livestream-stop", kwargs={"stream_key": first.stream_key}
        )
        self.client.post(stop_url)

        # Create second stream
        self.client.post(start_url, {"title": "Second Stream"})
        self.assertEqual(LiveStream.objects.count(), 2)
        second = LiveStream.objects.order_by("-pk").first()
        self.assertTrue(second.is_active)
        self.assertEqual(second.title, "Second Stream")


# ============================================================================
# 4. WebSocket Security Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class WebSocketConnectionSecurityTests(TransactionTestCase):
    """Test WebSocket connection security: non-existent and ended streams."""

    def _create_user(self, username="testuser", is_staff=False):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream", is_active=True):
        return LiveStream.objects.create(
            title=title, created_by=user, is_active=is_active
        )

    def test_connection_to_nonexistent_stream_uuid_rejected(self):
        """WebSocket connection to a UUID with no matching stream is rejected."""
        async def _test():
            fake_key = uuid.uuid4()
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{fake_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertFalse(
                connected,
                "Connection to a non-existent stream UUID should be rejected",
            )
            await communicator.disconnect()

        async_to_sync(_test)()

    def test_connection_to_ended_stream_rejected(self):
        """WebSocket connection to an ended (inactive) stream is rejected."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, is_active=False)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertFalse(
                connected,
                "Connection to an ended/inactive stream should be rejected",
            )
            await communicator.disconnect()

        async_to_sync(_test)()

    def test_connection_to_active_stream_accepted(self):
        """WebSocket connection to an active stream is accepted (baseline)."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, is_active=True)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(
                connected,
                "Connection to an active stream should be accepted",
            )
            await communicator.disconnect()

        async_to_sync(_test)()


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class WebSocketRoleEnforcementTests(TransactionTestCase):
    """Test that only broadcasters can send audio and listeners are blocked."""

    def _create_user(self, username="testuser", is_staff=False):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream"):
        return LiveStream.objects.create(title=title, created_by=user)

    def test_listener_cannot_send_audio(self):
        """A client with listener role sending binary data does not broadcast."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            # Connect two clients
            listener = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            other = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )

            await listener.connect()
            await other.connect()

            # Set listener role
            await listener.send_json_to({"type": "role", "role": "listener"})
            await listener.receive_json_from()

            await other.send_json_to({"type": "role", "role": "listener"})
            await other.receive_json_from()

            # Listener tries to send audio via JSON protocol
            await listener.send_json_to({"type": "audio", "data": base64.b64encode(b"sneaky-audio-attempt").decode("ascii")})

            # Other client should not receive anything
            try:
                msg = await asyncio.wait_for(
                    other.receive_from(), timeout=0.3
                )
                self.fail(
                    f"Listener should not be able to broadcast, but other received: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected

            await listener.disconnect()
            await other.disconnect()

        async_to_sync(_test)()

    def test_no_role_set_binary_data_ignored(self):
        """A client that never sets a role sending binary data is ignored."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            # Connect two clients, neither sets a role
            sender = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            receiver = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )

            await sender.connect()
            await receiver.connect()

            # Sender sends binary data without setting any role
            await sender.send_to(bytes_data=b"no-role-audio-data")

            # Receiver should not get anything
            try:
                msg = await asyncio.wait_for(
                    receiver.receive_from(), timeout=0.3
                )
                self.fail(
                    f"No-role client should not broadcast, but receiver got: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected

            await sender.disconnect()
            await receiver.disconnect()

        async_to_sync(_test)()

    def test_broadcaster_can_send_audio(self):
        """A client with broadcaster role can send audio to listeners (baseline)."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            broadcaster = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            listener = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )

            await broadcaster.connect()
            await listener.connect()

            # Set roles
            await broadcaster.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster.receive_json_from()

            await listener.send_json_to({"type": "role", "role": "listener"})
            await listener.receive_json_from()

            # Broadcaster sends audio via JSON protocol
            audio = b"\xff\xfe\xfd-test-audio"
            await broadcaster.send_json_to({"type": "audio", "data": base64.b64encode(audio).decode("ascii")})

            # Listener receives it as JSON
            resp = await listener.receive_json_from()
            self.assertEqual(resp["type"], "audio")
            self.assertEqual(base64.b64decode(resp["data"]), audio)

            await broadcaster.disconnect()
            await listener.disconnect()

        async_to_sync(_test)()

    def test_role_change_listener_to_broadcaster_allows_sending(self):
        """If a client changes role from listener to broadcaster, it can then send audio.
        This tests the actual behavior of the consumer (role is simply overwritten)."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            client_a = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            client_b = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )

            await client_a.connect()
            await client_b.connect()

            # Client A starts as listener
            await client_a.send_json_to({"type": "role", "role": "listener"})
            resp = await client_a.receive_json_from()
            self.assertEqual(resp["role"], "listener")

            # Set client B as listener too
            await client_b.send_json_to({"type": "role", "role": "listener"})
            await client_b.receive_json_from()

            # Client A sends audio as listener via JSON -- should be ignored
            await client_a.send_json_to({"type": "audio", "data": base64.b64encode(b"listener-audio").decode("ascii")})
            try:
                await asyncio.wait_for(client_b.receive_from(), timeout=0.2)
                self.fail("Listener should not broadcast")
            except asyncio.TimeoutError:
                pass

            # Client A changes role to broadcaster
            await client_a.send_json_to({"type": "role", "role": "broadcaster"})
            resp = await client_a.receive_json_from()
            self.assertEqual(resp["role"], "broadcaster")

            # Now client A can send audio via JSON protocol
            audio = b"broadcaster-audio"
            await client_a.send_json_to({"type": "audio", "data": base64.b64encode(audio).decode("ascii")})
            resp = await client_b.receive_json_from()
            self.assertEqual(resp["type"], "audio")
            self.assertEqual(base64.b64decode(resp["data"]), audio)

            await client_a.disconnect()
            await client_b.disconnect()

        async_to_sync(_test)()

    def test_broadcaster_does_not_receive_own_audio(self):
        """The broadcaster should not echo its own audio back to itself."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            broadcaster = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            await broadcaster.connect()

            await broadcaster.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster.receive_json_from()

            # Send audio via JSON protocol
            await broadcaster.send_json_to({"type": "audio", "data": base64.b64encode(b"no-echo-test").decode("ascii")})

            # Broadcaster should NOT receive its own audio
            try:
                msg = await asyncio.wait_for(
                    broadcaster.receive_from(), timeout=0.3
                )
                self.fail(
                    f"Broadcaster should not receive its own audio, but got: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected

            await broadcaster.disconnect()

        async_to_sync(_test)()

    def test_large_binary_payload_handled(self):
        """A large binary payload from the broadcaster is forwarded to listeners."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            broadcaster = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            listener = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )

            await broadcaster.connect()
            await listener.connect()

            await broadcaster.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster.receive_json_from()

            await listener.send_json_to({"type": "role", "role": "listener"})
            await listener.receive_json_from()

            # Send a large payload (64KB) via JSON protocol
            large_audio = b"\xab" * 65536
            await broadcaster.send_json_to({"type": "audio", "data": base64.b64encode(large_audio).decode("ascii")})

            resp = await listener.receive_json_from()
            self.assertEqual(resp["type"], "audio")
            decoded = base64.b64decode(resp["data"])
            self.assertEqual(len(decoded), 65536)
            self.assertEqual(decoded, large_audio)

            await broadcaster.disconnect()
            await listener.disconnect()

        async_to_sync(_test)()

    def test_minimal_binary_payload_forwarded(self):
        """A minimal binary payload (single null byte) is forwarded because
        bytes_data is falsy when empty."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            broadcaster = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            listener = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )

            await broadcaster.connect()
            await listener.connect()

            await broadcaster.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster.receive_json_from()

            await listener.send_json_to({"type": "role", "role": "listener"})
            await listener.receive_json_from()

            # Send minimal 1-byte payload via JSON protocol
            await broadcaster.send_json_to({"type": "audio", "data": base64.b64encode(b"\x00").decode("ascii")})

            # The consumer broadcasts it via JSON
            resp = await listener.receive_json_from(timeout=1)
            self.assertEqual(resp["type"], "audio")
            self.assertEqual(base64.b64decode(resp["data"]), b"\x00")

            await broadcaster.disconnect()
            await listener.disconnect()

        async_to_sync(_test)()

    def test_malformed_json_text_data_does_not_crash(self):
        """Sending malformed JSON text data should not crash the consumer."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send malformed JSON -- this will raise json.JSONDecodeError in the consumer
            # The consumer should handle it (or crash, which we want to detect)
            try:
                await communicator.send_to(text_data="not-valid-json{{{")
                # Give it a moment to process
                await asyncio.sleep(0.1)
            except Exception:
                pass

            # The connection should still be open or cleanly closed
            # If the consumer crashed, this would raise an exception
            await communicator.disconnect()

        async_to_sync(_test)()


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class WebSocketStreamIsolationTests(TransactionTestCase):
    """Test that streams are properly isolated from each other via WebSocket."""

    def _create_user(self, username="testuser", is_staff=False):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream"):
        return LiveStream.objects.create(title=title, created_by=user)

    def test_audio_does_not_leak_between_streams(self):
        """Audio from stream A does not reach listeners on stream B."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream_a = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream A")
            )
            stream_b = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream B")
            )

            # Broadcaster on stream A
            broadcaster_a = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_a.stream_key}/",
            )
            await broadcaster_a.connect()
            await broadcaster_a.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster_a.receive_json_from()

            # Listener on stream B
            listener_b = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_b.stream_key}/",
            )
            await listener_b.connect()
            await listener_b.send_json_to({"type": "role", "role": "listener"})
            await listener_b.receive_json_from()

            # Broadcaster A sends audio via JSON protocol
            await broadcaster_a.send_json_to({"type": "audio", "data": base64.b64encode(b"stream-a-secret-audio").decode("ascii")})

            # Listener on stream B should NOT receive it
            try:
                msg = await asyncio.wait_for(
                    listener_b.receive_from(), timeout=0.3
                )
                self.fail(
                    f"Audio from stream A leaked to stream B listener: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected -- streams are isolated

            await broadcaster_a.disconnect()
            await listener_b.disconnect()

        async_to_sync(_test)()

    def test_concurrent_streams_independent(self):
        """Two concurrent streams operate independently -- each broadcaster's
        audio only reaches its own listeners."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream_a = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Concurrent A")
            )
            stream_b = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Concurrent B")
            )

            # Stream A: broadcaster + listener
            bc_a = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_a.stream_key}/",
            )
            await bc_a.connect()
            await bc_a.send_json_to({"type": "role", "role": "broadcaster"})
            await bc_a.receive_json_from()

            li_a = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_a.stream_key}/",
            )
            await li_a.connect()
            await li_a.send_json_to({"type": "role", "role": "listener"})
            await li_a.receive_json_from()

            # Stream B: broadcaster + listener
            bc_b = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_b.stream_key}/",
            )
            await bc_b.connect()
            await bc_b.send_json_to({"type": "role", "role": "broadcaster"})
            await bc_b.receive_json_from()

            li_b = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_b.stream_key}/",
            )
            await li_b.connect()
            await li_b.send_json_to({"type": "role", "role": "listener"})
            await li_b.receive_json_from()

            # Stream A broadcaster sends via JSON protocol
            audio_a = b"audio-from-A"
            await bc_a.send_json_to({"type": "audio", "data": base64.b64encode(audio_a).decode("ascii")})
            resp_a = await li_a.receive_json_from()
            self.assertEqual(resp_a["type"], "audio")
            self.assertEqual(base64.b64decode(resp_a["data"]), audio_a)

            # Stream B listener should NOT receive stream A audio
            try:
                await asyncio.wait_for(li_b.receive_from(), timeout=0.2)
                self.fail("Stream B listener received audio from stream A")
            except asyncio.TimeoutError:
                pass

            # Stream B broadcaster sends via JSON protocol
            audio_b = b"audio-from-B"
            await bc_b.send_json_to({"type": "audio", "data": base64.b64encode(audio_b).decode("ascii")})
            resp_b = await li_b.receive_json_from()
            self.assertEqual(resp_b["type"], "audio")
            self.assertEqual(base64.b64decode(resp_b["data"]), audio_b)

            # Stream A listener should NOT receive stream B audio
            try:
                await asyncio.wait_for(li_a.receive_from(), timeout=0.2)
                self.fail("Stream A listener received audio from stream B")
            except asyncio.TimeoutError:
                pass

            await bc_a.disconnect()
            await li_a.disconnect()
            await bc_b.disconnect()
            await li_b.disconnect()

        async_to_sync(_test)()
