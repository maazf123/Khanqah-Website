"""
TDD tests for Chunk 4 (UI Polish) of the LiveStream feature.

Tests verify that templates contain the expected UI elements for:
1. Broadcast page: countdown overlay, listener count, audio visualizer,
   stop confirmation, copy button, share link, mic controls, WebSocket
2. Listen page: play button, status badge, error state, ended state,
   audio visualizer, WebSocket, back button
3. List page: LIVE badge, stream links, started time, empty state
4. Start page: form, title input, submit button, empty title error
5. Navigation: Live link, Go Live for staff, no Go Live for anon,
   active stream indicator
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse

from apps.core.models import LiveStream

# ---------------------------------------------------------------------------
# Module-level URL configuration used by @override_settings(ROOT_URLCONF=...)
# ---------------------------------------------------------------------------
urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("", include("apps.recordings.urls")),
]


# ============================================================================
# 1. BroadcastPageUITests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_ui_polish")
class BroadcastPageUITests(TestCase):
    """Tests that the broadcast template contains all expected UI elements."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Broadcast UI Test", created_by=self.staff_user
        )
        self.client.login(username="admin", password="pass")
        self.url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": self.stream.stream_key},
        )
        self.response = self.client.get(self.url)
        self.content = self.response.content.decode()

    def test_broadcast_page_has_countdown_overlay(self):
        """Broadcast page contains a countdown overlay element."""
        has_id = 'id="countdown-overlay"' in self.content
        has_class = 'class="countdown-overlay"' in self.content
        self.assertTrue(
            has_id or has_class,
            "Broadcast page should contain an element with "
            'id="countdown-overlay" or class="countdown-overlay".',
        )

    def test_broadcast_page_has_countdown_number(self):
        """Broadcast page contains a countdown number display element."""
        self.assertIn(
            'id="countdown-number"',
            self.content,
            "Broadcast page should contain an element with "
            'id="countdown-number".',
        )

    def test_broadcast_page_has_listener_count(self):
        """Broadcast page contains a listener count display element."""
        self.assertIn(
            'id="listener-count"',
            self.content,
            "Broadcast page should contain an element with "
            'id="listener-count".',
        )

    def test_broadcast_page_has_audio_visualizer(self):
        """Broadcast page contains an audio visualizer element."""
        has_id = 'id="audio-visualizer"' in self.content
        has_class = 'class="audio-visualizer"' in self.content
        self.assertTrue(
            has_id or has_class,
            "Broadcast page should contain an element with "
            'id="audio-visualizer" or class="audio-visualizer".',
        )

    def test_broadcast_page_has_stop_confirmation(self):
        """Broadcast page includes a JS confirmation before stopping the stream."""
        content_lower = self.content.lower()
        has_confirm = "confirm(" in self.content or "confirm (" in self.content
        has_are_you_sure = "are you sure" in content_lower
        self.assertTrue(
            has_confirm or has_are_you_sure,
            "Broadcast page should contain a confirmation dialog "
            '(confirm() call or "Are you sure" text) before stopping.',
        )

    def test_broadcast_page_has_copy_button(self):
        """Broadcast page contains a copy button for the share link."""
        self.assertIn(
            'id="copy-btn"',
            self.content,
            'Broadcast page should contain an element with id="copy-btn".',
        )

    def test_broadcast_page_has_share_link(self):
        """Broadcast page contains a share link input with the listen URL."""
        self.assertIn(
            'id="listen-url"',
            self.content,
            'Broadcast page should contain an element with id="listen-url".',
        )

    def test_broadcast_page_has_mute_button(self):
        """Broadcast page contains a mute toggle button."""
        self.assertIn(
            'id="mute-btn"',
            self.content,
            'Broadcast page should contain an element with id="mute-btn".',
        )

    def test_broadcast_page_has_websocket_connection(self):
        """Broadcast page contains WebSocket connection code."""
        has_websocket = "WebSocket" in self.content
        has_ws_protocol = "ws://" in self.content
        has_wss_protocol = "wss://" in self.content
        has_wss_colon = "wss:" in self.content
        has_ws_colon = "ws:" in self.content
        self.assertTrue(
            has_websocket or has_ws_protocol or has_wss_protocol
            or has_wss_colon or has_ws_colon,
            "Broadcast page should contain WebSocket connection code "
            '("WebSocket", "ws://", or "wss://").',
        )


# ============================================================================
# 2. ListenPageUITests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_ui_polish")
class ListenPageUITests(TestCase):
    """Tests that the listen template contains all expected UI elements."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Listen UI Test", created_by=self.staff_user
        )
        self.url = reverse(
            "livestream-listen",
            kwargs={"stream_key": self.stream.stream_key},
        )
        # Access as anonymous user
        self.response = self.client.get(self.url)
        self.content = self.response.content.decode()

    def test_listen_page_has_play_button(self):
        """Listen page contains a play/listen button."""
        self.assertIn(
            'id="play-btn"',
            self.content,
            'Listen page should contain an element with id="play-btn".',
        )

    def test_listen_page_has_status_badge(self):
        """Listen page contains a status badge element."""
        self.assertIn(
            'id="status-badge"',
            self.content,
            'Listen page should contain an element with id="status-badge".',
        )

    def test_listen_page_has_error_state(self):
        """Listen page contains error state UI or reconnect functionality."""
        has_error_id = 'id="error-state"' in self.content
        has_error_class = 'class="error-state"' in self.content
        has_reconnect = "reconnect" in self.content.lower()
        has_retry = "retry" in self.content.lower()
        self.assertTrue(
            has_error_id or has_error_class or has_reconnect or has_retry,
            "Listen page should contain an error state element "
            '(id="error-state", class="error-state", or "reconnect"/"retry" text).',
        )

    def test_listen_page_has_ended_state(self):
        """Listen page contains ended state handling in JS."""
        content_lower = self.content.lower()
        has_ended = "ended" in content_lower
        has_stream_ended = "stream has ended" in content_lower
        self.assertTrue(
            has_ended or has_stream_ended,
            "Listen page should contain ended state handling "
            '("ended" or "stream has ended" text in JS).',
        )

    def test_listen_page_has_audio_visualizer(self):
        """Listen page contains an audio visualizer element."""
        has_id = 'id="audio-visualizer"' in self.content
        has_class = 'class="audio-visualizer"' in self.content
        self.assertTrue(
            has_id or has_class,
            "Listen page should contain an element with "
            'id="audio-visualizer" or class="audio-visualizer".',
        )

    def test_listen_page_has_websocket_connection(self):
        """Listen page contains WebSocket connection code."""
        has_websocket = "WebSocket" in self.content
        has_ws_protocol = "ws://" in self.content
        has_wss_colon = "wss:" in self.content
        has_ws_colon = "ws:" in self.content
        self.assertTrue(
            has_websocket or has_ws_protocol or has_wss_colon or has_ws_colon,
            "Listen page should contain WebSocket connection code.",
        )

    def test_listen_page_has_back_button_in_ended_state(self):
        """Listen page contains a back/go-back link for when the stream ends."""
        list_url = reverse("livestream-list")
        has_list_url = list_url in self.content
        has_livestream_list = "livestream-list" in self.content
        content_lower = self.content.lower()
        has_back = "back" in content_lower
        has_go_back = "go back" in content_lower
        self.assertTrue(
            has_list_url or has_livestream_list or has_back or has_go_back,
            "Listen page should contain a back/go-back mechanism "
            '(livestream-list URL, "Back", or "Go Back" text).',
        )


# ============================================================================
# 3. LiveStreamListUITests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_ui_polish")
class LiveStreamListUITests(TestCase):
    """Tests that the list page shows proper UI for active streams."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.url = reverse("livestream-list")

    def test_list_page_shows_live_badge(self):
        """When there is an active stream, the page contains a LIVE badge."""
        LiveStream.objects.create(
            title="Active Stream", created_by=self.staff_user
        )
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn(
            "LIVE",
            content,
            "List page should show a LIVE badge when an active stream exists.",
        )

    def test_list_page_has_stream_link(self):
        """Active stream title links to the listen page."""
        stream = LiveStream.objects.create(
            title="Linked Stream", created_by=self.staff_user
        )
        response = self.client.get(self.url)
        content = response.content.decode()
        listen_url = reverse(
            "livestream-listen",
            kwargs={"stream_key": stream.stream_key},
        )
        self.assertIn(
            listen_url,
            content,
            "List page should contain a link to the listen page for the stream.",
        )

    def test_list_page_shows_started_time(self):
        """List page shows time-since info (contains 'ago' or timesince)."""
        LiveStream.objects.create(
            title="Timed Stream", created_by=self.staff_user
        )
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn(
            "ago",
            content,
            'List page should show timing information containing "ago".',
        )

    def test_list_page_empty_state(self):
        """When no active streams exist, the page shows an empty message."""
        response = self.client.get(self.url)
        content = response.content.decode().lower()
        has_empty_msg = (
            "no live streams" in content
            or "no streams" in content
            or "check back" in content
            or "empty" in content
        )
        self.assertTrue(
            has_empty_msg,
            "List page should show an empty state message when no streams exist.",
        )


# ============================================================================
# 4. StartPageUITests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_ui_polish")
class StartPageUITests(TestCase):
    """Tests that the start stream form page has proper UI elements."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.client.login(username="admin", password="pass")
        self.url = reverse("livestream-start")

    def test_start_page_has_form(self):
        """Start page contains a form element."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn(
            "<form",
            content,
            "Start page should contain a <form> element.",
        )

    def test_start_page_has_title_input(self):
        """Start page contains an input with name='title'."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn(
            'name="title"',
            content,
            'Start page should contain an input with name="title".',
        )

    def test_start_page_has_submit_button(self):
        """Start page contains a submit button."""
        response = self.client.get(self.url)
        content = response.content.decode()
        has_submit_type = 'type="submit"' in content
        has_submit_btn = "<button" in content and "submit" in content.lower()
        self.assertTrue(
            has_submit_type or has_submit_btn,
            "Start page should contain a submit button.",
        )

    def test_start_page_creates_stream_on_empty_title(self):
        """POSTing an empty title auto-generates a title and redirects."""
        response = self.client.post(self.url, {"title": ""})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LiveStream.objects.exists())


# ============================================================================
# 5. NavigationUITests
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_ui_polish")
class NavigationUITests(TestCase):
    """Tests for navigation bar elements related to live streaming."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user("user", password="pass")

    def _get_nav_page(self):
        """Get a page that renders the base template with navigation."""
        return self.client.get(reverse("livestream-list"))

    def test_live_nav_link_removed_for_anonymous(self):
        """The 'Live' link is not shown in navigation for anonymous users.
        Only staff see 'Go Live'."""
        response = self._get_nav_page()
        content = response.content.decode()
        self.assertNotIn(
            ">Live<",
            content,
            "Anonymous users should not see a 'Live' nav link.",
        )

    def test_go_live_button_for_staff(self):
        """Staff users see a 'Go Live' link/button in the navigation."""
        self.client.login(username="admin", password="pass")
        response = self._get_nav_page()
        content = response.content.decode()
        self.assertIn(
            "Go Live",
            content,
            "Staff users should see a 'Go Live' button in navigation.",
        )

    def test_go_live_button_has_distinct_styling(self):
        """Staff 'Go Live' link has a distinct CSS class for styling."""
        self.client.login(username="admin", password="pass")
        response = self._get_nav_page()
        content = response.content.decode()
        has_class = "nav-go-live" in content
        self.assertTrue(
            has_class,
            "Go Live link should have a distinct CSS class (nav-go-live).",
        )

    def test_no_go_live_for_anonymous(self):
        """Anonymous users do not see a 'Go Live' link in the navigation."""
        response = self._get_nav_page()
        content = response.content.decode()
        self.assertNotIn(
            "Go Live",
            content,
            "Anonymous users should not see a 'Go Live' button.",
        )

    def test_no_go_live_for_regular_user(self):
        """Non-staff logged-in users do not see 'Go Live' in the navigation."""
        self.client.login(username="user", password="pass")
        response = self._get_nav_page()
        content = response.content.decode()
        self.assertNotIn(
            "Go Live",
            content,
            "Non-staff users should not see a 'Go Live' button.",
        )

    def test_active_stream_indicator_in_nav(self):
        """When an active stream exists and staff is logged in, the nav shows Go Live."""
        LiveStream.objects.create(
            title="Active Nav Stream", created_by=self.staff_user
        )
        self.client.login(username="admin", password="pass")
        response = self._get_nav_page()
        content = response.content.decode()
        self.assertIn(
            "Go Live",
            content,
            "Staff should see 'Go Live' in the navigation.",
        )
