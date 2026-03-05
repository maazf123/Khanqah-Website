"""
TDD tests for Chunk 1: Smart Title Default.

When a staff user starts a livestream without providing a title (empty or
whitespace-only), the system should auto-generate a title in the format
"Month Day, Year Live Stream" (e.g., "March 5, 2026 Live Stream") instead
of rejecting the POST with an error.

All tests are expected to FAIL until the feature is implemented.
"""

from datetime import datetime
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

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


@override_settings(ROOT_URLCONF="apps.core.tests_smart_title")
class SmartTitleTests(TestCase):
    """Tests for the Smart Title Default feature on LiveStreamStartView."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            "admin", password="pass", is_staff=True
        )
        self.url = reverse("livestream-start")
        self.client.login(username="admin", password="pass")

    # ------------------------------------------------------------------
    # Requirement 1 & 6: Title field should be optional in the HTML form
    # ------------------------------------------------------------------
    def test_title_input_does_not_have_required_attribute(self):
        """The title <input> in the start form should NOT have the 'required' attribute."""
        response = self.client.get(self.url)
        content = response.content.decode()
        # Find the input element for title and verify 'required' is absent.
        # The input tag should contain name="title" but NOT the word "required".
        self.assertIn('name="title"', content)
        # Extract the <input ...> tag for the title field
        import re

        match = re.search(r"<input[^>]*name=[\"']title[\"'][^>]*>", content)
        self.assertIsNotNone(match, "Could not find an <input> with name='title'")
        input_tag = match.group(0)
        self.assertNotIn("required", input_tag)

    def test_placeholder_contains_optional(self):
        """The placeholder text on the title input should contain 'optional'
        to hint to the user that the field is not required."""
        response = self.client.get(self.url)
        content = response.content.decode()
        import re

        match = re.search(r"<input[^>]*name=[\"']title[\"'][^>]*>", content)
        self.assertIsNotNone(match, "Could not find an <input> with name='title'")
        input_tag = match.group(0).lower()
        # The placeholder attribute should exist and contain 'optional'
        placeholder_match = re.search(r'placeholder=["\']([^"\']*)["\']', input_tag)
        self.assertIsNotNone(
            placeholder_match, "Title input should have a placeholder attribute"
        )
        placeholder_text = placeholder_match.group(1)
        self.assertIn("optional", placeholder_text)

    # ------------------------------------------------------------------
    # Requirement 2: POSTing empty title should succeed (302 redirect)
    # ------------------------------------------------------------------
    def test_empty_title_post_redirects(self):
        """POST with an empty title ('') should succeed and redirect (302),
        NOT re-render the form with an error."""
        response = self.client.post(self.url, {"title": ""})
        self.assertEqual(
            response.status_code,
            302,
            "Empty title POST should redirect (302), not show a form error",
        )

    def test_empty_title_post_creates_stream(self):
        """POST with an empty title should still create a LiveStream object."""
        self.assertEqual(LiveStream.objects.count(), 0)
        self.client.post(self.url, {"title": ""})
        self.assertEqual(LiveStream.objects.count(), 1)

    # ------------------------------------------------------------------
    # Requirement 3: POSTing whitespace-only title should succeed
    # ------------------------------------------------------------------
    def test_whitespace_title_post_redirects(self):
        """POST with a whitespace-only title ('   ') should succeed and
        redirect (302), NOT re-render the form with an error."""
        response = self.client.post(self.url, {"title": "   "})
        self.assertEqual(
            response.status_code,
            302,
            "Whitespace-only title POST should redirect (302), not show a form error",
        )

    def test_whitespace_title_post_creates_stream(self):
        """POST with a whitespace-only title should still create a LiveStream."""
        self.assertEqual(LiveStream.objects.count(), 0)
        self.client.post(self.url, {"title": "   "})
        self.assertEqual(LiveStream.objects.count(), 1)

    # ------------------------------------------------------------------
    # Requirement 4: Auto-generated title format
    # ------------------------------------------------------------------
    def test_empty_title_generates_date_based_title(self):
        """When title is empty, the created LiveStream should get an
        auto-generated title in format 'Month Day, Year Live Stream'."""
        # Mock timezone.now to return a known date
        fake_now = timezone.make_aware(datetime(2026, 3, 5, 14, 30, 0))
        with patch("apps.core.views_livestream.timezone.now", return_value=fake_now):
            self.client.post(self.url, {"title": ""})
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        self.assertEqual(stream.title, "March 5, 2026 Live Stream")

    def test_whitespace_title_generates_date_based_title(self):
        """When title is whitespace-only, the created LiveStream should get an
        auto-generated title in format 'Month Day, Year Live Stream'."""
        fake_now = timezone.make_aware(datetime(2026, 3, 5, 14, 30, 0))
        with patch("apps.core.views_livestream.timezone.now", return_value=fake_now):
            self.client.post(self.url, {"title": "   "})
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        self.assertEqual(stream.title, "March 5, 2026 Live Stream")

    def test_auto_title_format_different_date(self):
        """Verify the auto-generated title uses the correct format for a
        different date (no zero-padded day)."""
        fake_now = timezone.make_aware(datetime(2025, 12, 25, 10, 0, 0))
        with patch("apps.core.views_livestream.timezone.now", return_value=fake_now):
            self.client.post(self.url, {"title": ""})
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        # Day should NOT be zero-padded: "December 25, 2025" not "December 25, 2025"
        self.assertEqual(stream.title, "December 25, 2025 Live Stream")

    def test_auto_title_single_digit_day_not_zero_padded(self):
        """The day in the auto-generated title should not be zero-padded.
        E.g., 'March 5, 2026' not 'March 05, 2026'."""
        fake_now = timezone.make_aware(datetime(2026, 1, 7, 9, 0, 0))
        with patch("apps.core.views_livestream.timezone.now", return_value=fake_now):
            self.client.post(self.url, {"title": ""})
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        self.assertEqual(stream.title, "January 7, 2026 Live Stream")
        self.assertNotIn("07", stream.title)

    # ------------------------------------------------------------------
    # Requirement 5: When title is provided, use it as-is
    # ------------------------------------------------------------------
    def test_provided_title_used_as_is(self):
        """When a non-whitespace title is provided, it should be stored exactly."""
        self.client.post(self.url, {"title": "Friday Bayaan"})
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        self.assertEqual(stream.title, "Friday Bayaan")

    def test_provided_title_with_surrounding_whitespace_is_stripped(self):
        """A title with leading/trailing whitespace but real content in the
        middle should be stripped and used (not auto-generated)."""
        self.client.post(self.url, {"title": "  My Custom Title  "})
        stream = LiveStream.objects.first()
        self.assertIsNotNone(stream)
        # The view already strips; the title should be the stripped version
        self.assertEqual(stream.title, "My Custom Title")

    def test_provided_title_post_still_redirects(self):
        """POST with a normal title should still redirect as before."""
        response = self.client.post(self.url, {"title": "Regular Stream"})
        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------
    # Requirement 7: No error message for empty title
    # ------------------------------------------------------------------
    def test_empty_title_no_error_message(self):
        """POST with an empty title should NOT display any error message.
        The response should be a redirect, not a form re-render with errors."""
        response = self.client.post(self.url, {"title": ""})
        # A redirect means no error page was rendered
        self.assertEqual(response.status_code, 302)
        # But also verify: if we follow the redirect, the error text should
        # not be present anywhere in the flow
        self.assertNotEqual(response.status_code, 200)

    def test_whitespace_title_no_error_message(self):
        """POST with whitespace-only title should NOT display 'Title is required.'"""
        response = self.client.post(self.url, {"title": "   "})
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.status_code, 200)

    def test_empty_title_no_title_required_error_in_response(self):
        """Even if the response is 200 (current broken behavior), it should
        NOT contain the text 'Title is required.' once the feature is built.
        This test verifies the error message is absent."""
        response = self.client.post(self.url, {"title": ""})
        if response.status_code == 200:
            content = response.content.decode()
            self.assertNotIn("Title is required", content)
        # If it's a redirect (302), that's the correct behavior - no error shown
        else:
            self.assertEqual(response.status_code, 302)
