"""
TDD tests for Chunk 2: Broadcast Page UX Overhaul.

These tests verify the broadcast page after the UX overhaul:
1. No start-mic-btn -- mic auto-starts after countdown, no manual start button
2. No stop-mic-btn -- replaced by mute toggle
3. Has a mute/unmute toggle button with id="mute-btn"
4. Mute button contains "Mute" text (initially, since mic starts unmuted)
5. JS auto-starts mic after WebSocket role confirmation (getUserMedia called
   automatically, no button click required)
6. Share/copy link section wrapped in id="share-section"
7. Copy button still exists with id="copy-btn"
8. Listen URL input still exists with id="listen-url"
9. Stop form still exists with id="stop-form"
10. Countdown overlay still exists with id="countdown-overlay" and
    id="countdown-number"
11. Page does NOT contain "Start Microphone" text
12. Page DOES contain "Mute" text
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


@override_settings(ROOT_URLCONF="apps.core.tests_broadcast_ux")
class BroadcastUXTests(TestCase):
    """Tests for the broadcast page UX overhaul (Chunk 2).

    The overhaul removes the manual start/stop mic buttons in favor of
    auto-starting the mic after the countdown and providing a mute toggle.
    It also wraps the share link section in a dedicated container.
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.stream = LiveStream.objects.create(
            title="Broadcast UX Test", created_by=self.staff_user
        )
        self.client.login(username="admin", password="pass")
        self.url = reverse(
            "livestream-broadcast",
            kwargs={"stream_key": self.stream.stream_key},
        )
        self.response = self.client.get(self.url)
        self.content = self.response.content.decode()

    # ------------------------------------------------------------------
    # Removed elements: start-mic-btn and stop-mic-btn should be gone
    # ------------------------------------------------------------------

    def test_no_start_mic_btn(self):
        """The broadcast page must NOT contain an element with id='start-mic-btn'.

        The manual start microphone button has been removed because the mic
        now auto-starts after the countdown completes.
        """
        self.assertNotIn(
            'id="start-mic-btn"',
            self.content,
            "Broadcast page should NOT contain id=\"start-mic-btn\" -- "
            "mic auto-starts after countdown, no manual start button needed.",
        )

    def test_no_stop_mic_btn(self):
        """The broadcast page must NOT contain an element with id='stop-mic-btn'.

        The old stop-mic button has been replaced by a mute/unmute toggle.
        """
        self.assertNotIn(
            'id="stop-mic-btn"',
            self.content,
            "Broadcast page should NOT contain id=\"stop-mic-btn\" -- "
            "replaced by the mute toggle button.",
        )

    def test_no_start_microphone_text(self):
        """The page should NOT contain the text 'Start Microphone'.

        Since the mic auto-starts, there is no reason for this label to exist.
        """
        self.assertNotIn(
            "Start Microphone",
            self.content,
            "Broadcast page should NOT contain 'Start Microphone' text -- "
            "mic auto-starts after countdown.",
        )

    # ------------------------------------------------------------------
    # New element: mute-btn
    # ------------------------------------------------------------------

    def test_has_mute_btn(self):
        """The broadcast page must contain a mute/unmute toggle with id='mute-btn'."""
        self.assertIn(
            'id="mute-btn"',
            self.content,
            "Broadcast page should contain an element with id=\"mute-btn\" "
            "for the mute/unmute toggle.",
        )

    def test_mute_btn_contains_mute_text(self):
        """The mute button should initially display 'Mute' text.

        Since the mic auto-starts in an unmuted state, the button label
        should say 'Mute' (the action available is to mute).
        """
        self.assertIn(
            "Mute",
            self.content,
            "Broadcast page should contain 'Mute' text for the mute button "
            "(mic starts unmuted, so the available action is 'Mute').",
        )

    # ------------------------------------------------------------------
    # Share section wrapper
    # ------------------------------------------------------------------

    def test_has_share_section_wrapper(self):
        """The share/copy link section must be wrapped in id='share-section'."""
        self.assertIn(
            'id="share-section"',
            self.content,
            "Broadcast page should wrap the share link area in an element "
            "with id=\"share-section\".",
        )

    # ------------------------------------------------------------------
    # Retained elements: these must still exist after the overhaul
    # ------------------------------------------------------------------

    def test_still_has_copy_btn(self):
        """The copy button with id='copy-btn' must still exist."""
        self.assertIn(
            'id="copy-btn"',
            self.content,
            "Broadcast page should still contain id=\"copy-btn\".",
        )

    def test_still_has_listen_url(self):
        """The listen URL input with id='listen-url' must still exist."""
        self.assertIn(
            'id="listen-url"',
            self.content,
            "Broadcast page should still contain id=\"listen-url\".",
        )

    def test_still_has_stop_form(self):
        """The stop stream form with id='stop-form' must still exist."""
        self.assertIn(
            'id="stop-form"',
            self.content,
            "Broadcast page should still contain id=\"stop-form\".",
        )

    def test_still_has_countdown_overlay(self):
        """The countdown overlay with id='countdown-overlay' must still exist."""
        self.assertIn(
            'id="countdown-overlay"',
            self.content,
            "Broadcast page should still contain id=\"countdown-overlay\".",
        )

    def test_still_has_countdown_number(self):
        """The countdown number display with id='countdown-number' must still exist."""
        self.assertIn(
            'id="countdown-number"',
            self.content,
            "Broadcast page should still contain id=\"countdown-number\".",
        )

    # ------------------------------------------------------------------
    # JS behavior: auto-start mic logic
    # ------------------------------------------------------------------

    def test_js_contains_get_user_media(self):
        """The JS must call getUserMedia to access the microphone.

        This confirms the mic acquisition code is present in the template.
        """
        self.assertIn(
            "getUserMedia",
            self.content,
            "Broadcast page JS should contain a getUserMedia call "
            "to access the microphone.",
        )

    def test_js_no_start_mic_btn_event_listener(self):
        """The JS must NOT attach a click listener to 'start-mic-btn'.

        Since the mic auto-starts, there should be no event listener that
        waits for a manual click on a start button.
        """
        self.assertNotIn(
            'getElementById("start-mic-btn").addEventListener',
            self.content,
            "JS should NOT have an addEventListener on start-mic-btn -- "
            "mic auto-starts without user clicking a start button.",
        )
        # Also check the single-quote variant
        self.assertNotIn(
            "getElementById('start-mic-btn').addEventListener",
            self.content,
            "JS should NOT have an addEventListener on start-mic-btn -- "
            "mic auto-starts without user clicking a start button.",
        )

    def test_js_auto_starts_mic_on_role_confirmed(self):
        """After WebSocket confirms the broadcaster role, the mic should
        auto-start (call startMic or getUserMedia) without waiting for a
        button click.

        The role_confirmed handler should trigger the mic start flow
        (countdown then getUserMedia) automatically.
        """
        # Find the role_confirmed block and verify it triggers mic start
        # The JS should call startMic() (or equivalent) inside the
        # role_confirmed handler rather than merely enabling a button.
        has_auto_start = False

        # Check if role_confirmed triggers startMic directly
        if "role_confirmed" in self.content:
            # Find the section around role_confirmed and check it calls
            # startMic or getUserMedia rather than enabling a button
            rc_index = self.content.index("role_confirmed")
            # Look at a generous window after role_confirmed
            context_after = self.content[rc_index:rc_index + 500]
            # Should call startMic or the mic acquisition flow
            if "startMic" in context_after or "getUserMedia" in context_after:
                has_auto_start = True
            # Should NOT just enable a button
            if 'disabled = false' in context_after or '.disabled = false' in context_after:
                # If it only enables a button (old behavior), that's wrong
                # But if it ALSO calls startMic, that's fine
                if "startMic" not in context_after and "getUserMedia" not in context_after:
                    has_auto_start = False

        self.assertTrue(
            has_auto_start,
            "After role_confirmed, the JS should automatically call startMic() "
            "or getUserMedia() instead of merely enabling a start button. "
            "The mic must auto-start without user interaction.",
        )

    def test_js_no_enable_start_btn_on_role_confirmed(self):
        """The role_confirmed handler must NOT simply enable a start button.

        Old behavior: role_confirmed enables start-mic-btn.disabled = false.
        New behavior: role_confirmed triggers auto-start of mic.
        The JS should not reference start-mic-btn at all.
        """
        self.assertNotIn(
            "start-mic-btn",
            self.content,
            "JS should not reference 'start-mic-btn' at all -- "
            "the start button has been removed entirely.",
        )

    def test_js_no_stop_mic_btn_reference(self):
        """The JS must NOT reference 'stop-mic-btn' at all.

        The old stop-mic-btn has been replaced by the mute toggle.
        """
        self.assertNotIn(
            "stop-mic-btn",
            self.content,
            "JS should not reference 'stop-mic-btn' at all -- "
            "replaced by the mute-btn toggle.",
        )
