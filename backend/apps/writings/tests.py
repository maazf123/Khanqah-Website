import json
from datetime import date, timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import include, path, resolve, reverse

from apps.core.views_home import HomeView
from apps.tags.models import Tag

from .models import Writing


# ---------------------------------------------------------------------------
# Test URL configuration
# The main urls.py may not include writings URLs yet, so we define a
# self-contained URL conf here and override ROOT_URLCONF for every test class
# that touches views/URLs.
# Templates (e.g. base.html) reference urls like 'login', 'logout', 'home',
# and 'recording-list', so we must include those patterns here as well.
# ---------------------------------------------------------------------------
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("recordings/", include("apps.recordings.urls")),
    path("", HomeView.as_view(), name="home"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_tag(name, slug=None):
    """Create and return a Tag instance."""
    if slug is None:
        slug = name.lower().replace(" ", "-")
    return Tag.objects.create(name=name, slug=slug)


def _make_writing(title="Test Writing", body="This is the body text.",
                  published_date=None, tags=None, **kwargs):
    """Create a Writing, optionally attaching tags (an iterable of Tag objects)."""
    if published_date is None:
        published_date = date.today()
    writing = Writing.objects.create(
        title=title,
        body=body,
        published_date=published_date,
        **kwargs,
    )
    if tags:
        writing.tags.set(tags)
    return writing


# ===================================================================
# Model Tests
# ===================================================================
class WritingModelTests(TestCase):
    """Tests for the Writing model itself."""

    def test_create_writing_with_all_fields(self):
        tag = _make_tag("Reflection", "reflection")
        w = _make_writing(
            title="Full Fields",
            body="Body content here.",
            published_date=date(2026, 1, 15),
            tags=[tag],
        )
        self.assertEqual(w.title, "Full Fields")
        self.assertEqual(w.body, "Body content here.")
        self.assertEqual(w.published_date, date(2026, 1, 15))
        self.assertIsNotNone(w.created_at)
        self.assertIsNotNone(w.pk)
        self.assertIn(tag, w.tags.all())

    def test_str_returns_title(self):
        w = _make_writing(title="My Title")
        self.assertEqual(str(w), "My Title")

    def test_ordering_by_published_date_descending(self):
        w1 = _make_writing(title="Oldest", published_date=date(2025, 1, 1))
        w2 = _make_writing(title="Middle", published_date=date(2025, 6, 1))
        w3 = _make_writing(title="Newest", published_date=date(2026, 1, 1))
        writings = list(Writing.objects.all())
        self.assertEqual(writings, [w3, w2, w1])

    def test_can_add_tags_to_writing(self):
        t1 = _make_tag("Advice", "advice")
        t2 = _make_tag("Motivation", "motivation")
        w = _make_writing(title="Tagged Writing")
        w.tags.add(t1, t2)
        self.assertEqual(w.tags.count(), 2)
        self.assertIn(t1, w.tags.all())
        self.assertIn(t2, w.tags.all())

    def test_tags_are_optional(self):
        w = _make_writing(title="No Tags Writing")
        self.assertEqual(w.tags.count(), 0)


# ===================================================================
# URL Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingURLTests(TestCase):
    """Tests for URL resolution."""

    def test_writing_list_url(self):
        url = reverse("writing-list")
        self.assertEqual(url, "/writings/")

    def test_writing_detail_url(self):
        url = reverse("writing-detail", kwargs={"pk": 42})
        self.assertEqual(url, "/writings/42/")

    def test_writing_create_url(self):
        url = reverse("writing-create")
        self.assertEqual(url, "/writings/create/")

    def test_writing_list_resolves_correct_view(self):
        match = resolve("/writings/")
        self.assertEqual(match.url_name, "writing-list")

    def test_writing_detail_resolves_correct_view(self):
        match = resolve("/writings/1/")
        self.assertEqual(match.url_name, "writing-detail")

    def test_writing_create_resolves_correct_view(self):
        match = resolve("/writings/create/")
        self.assertEqual(match.url_name, "writing-create")

    def test_writing_archive_url(self):
        url = reverse("writing-archive")
        self.assertEqual(url, "/writings/all/")

    def test_writing_archive_resolves_correct_view(self):
        match = resolve("/writings/all/")
        self.assertEqual(match.url_name, "writing-archive")


# ===================================================================
# List View Tests (Redesigned: featured writing + sidebar)
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingListViewTests(TestCase):
    """Tests for the redesigned WritingListView with featured writing and sidebar."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_reflection = _make_tag("Reflection", "reflection")
        cls.tag_advice = _make_tag("Advice", "advice")
        # Create 8 writings so we can test featured + 5 sidebar items
        cls.writings = []
        for i in range(8):
            w = _make_writing(
                title=f"Writing {i}",
                body=f"Full body text for writing {i}. This should not be truncated.",
                published_date=date(2026, 1, 1) + timedelta(days=i),
                tags=[cls.tag_reflection] if i % 2 == 0 else [cls.tag_advice],
            )
            cls.writings.append(w)
        # The most recent is writings[7], next most recent is writings[6], etc.

    def setUp(self):
        self.url = reverse("writing-list")

    def test_list_view_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_list_view_uses_correct_template(self):
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, "writings/writing_list.html")

    def test_context_contains_featured_writing(self):
        resp = self.client.get(self.url)
        self.assertIn("featured_writing", resp.context)
        # The featured writing should be the most recent one
        self.assertEqual(resp.context["featured_writing"], self.writings[7])

    def test_context_contains_recent_writings(self):
        resp = self.client.get(self.url)
        self.assertIn("recent_writings", resp.context)
        recent = list(resp.context["recent_writings"])
        # Should be the next 5 most recent (excluding the featured one)
        self.assertEqual(len(recent), 5)
        expected = list(reversed(self.writings[2:7]))
        self.assertEqual(recent, expected)

    def test_featured_writing_title_displayed(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Writing 7")

    def test_featured_writing_full_body_displayed(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Full body text for writing 7. This should not be truncated.")

    def test_featured_writing_shows_published_date(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # Writing 7 has date 2026-01-08
        self.assertIn("2026", content)

    def test_featured_writing_shows_tags(self):
        resp = self.client.get(self.url)
        # Writing 7 (index 7, odd) has tag_advice
        self.assertContains(resp, "Advice")

    def test_sidebar_shows_recent_titles(self):
        resp = self.client.get(self.url)
        # Sidebar should show writings 6, 5, 4, 3, 2
        for i in range(2, 7):
            self.assertContains(resp, f"Writing {i}")

    def test_sidebar_shows_recent_dates(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # All sidebar writings have dates in January 2026
        self.assertIn("2026", content)

    def test_sidebar_items_link_to_detail_page(self):
        resp = self.client.get(self.url)
        # Each sidebar item should link to the detail page
        for i in range(2, 7):
            detail_url = reverse("writing-detail", kwargs={"pk": self.writings[i].pk})
            self.assertContains(resp, detail_url)

    def test_browse_all_link_present(self):
        resp = self.client.get(self.url)
        archive_url = reverse("writing-archive")
        self.assertContains(resp, archive_url)

    def test_context_has_tags(self):
        resp = self.client.get(self.url)
        self.assertIn("tags", resp.context)


# ===================================================================
# List View Few Writings Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingListViewFewWritingsTests(TestCase):
    """Tests for the list view with varying numbers of writings."""

    def setUp(self):
        self.url = reverse("writing-list")

    def test_one_writing_featured_shows_sidebar_empty(self):
        """With only 1 writing, featured shows that writing and sidebar is empty."""
        w = _make_writing(
            title="Only Writing",
            body="The only writing body.",
            published_date=date(2026, 3, 1),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["featured_writing"], w)
        self.assertEqual(len(resp.context["recent_writings"]), 0)

    def test_two_writings_featured_most_recent_sidebar_has_one(self):
        """With 2 writings, featured is the most recent, sidebar has 1 item."""
        w1 = _make_writing(
            title="Older Writing",
            body="Older body.",
            published_date=date(2026, 1, 1),
        )
        w2 = _make_writing(
            title="Newer Writing",
            body="Newer body.",
            published_date=date(2026, 2, 1),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["featured_writing"], w2)
        recent = list(resp.context["recent_writings"])
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0], w1)

    def test_seven_writings_sidebar_has_five_not_six(self):
        """With 7 writings, featured is the most recent, sidebar has exactly 5."""
        writings = []
        for i in range(7):
            w = _make_writing(
                title=f"Writing {i}",
                body=f"Body {i}.",
                published_date=date(2026, 1, 1) + timedelta(days=i),
            )
            writings.append(w)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["featured_writing"], writings[6])
        recent = list(resp.context["recent_writings"])
        self.assertEqual(len(recent), 5)


# ===================================================================
# List View Filter Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingListViewFilterTests(TestCase):
    """Tag filtering tests."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_advice = _make_tag("Advice", "advice")
        cls.tag_motivation = _make_tag("Motivation", "motivation")
        cls.advice_w = _make_writing(
            title="Advice Post",
            published_date=date(2026, 2, 1),
            tags=[cls.tag_advice],
        )
        cls.motivation_w = _make_writing(
            title="Motivation Post",
            published_date=date(2026, 2, 2),
            tags=[cls.tag_motivation],
        )

    def setUp(self):
        self.url = reverse("writing-list")

    def test_filter_by_tag_slug(self):
        resp = self.client.get(self.url, {"tag": "advice"})
        self.assertEqual(resp.status_code, 200)
        writings = resp.context["writings"]
        self.assertEqual(len(writings), 1)
        self.assertEqual(writings[0].title, "Advice Post")

    def test_filter_invalid_tag_returns_empty(self):
        resp = self.client.get(self.url, {"tag": "nonexistent"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["writings"]), 0)

    def test_context_current_tag_is_set_when_filtering(self):
        resp = self.client.get(self.url, {"tag": "advice"})
        self.assertEqual(resp.context["current_tag"], "advice")


# ===================================================================
# List View Empty Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingListViewEmptyTests(TestCase):
    """Tests for the list view when no writings exist."""

    def setUp(self):
        self.url = reverse("writing-list")

    def test_empty_state_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_empty_state_shows_no_writings_message(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "No writings yet")

    def test_empty_state_has_no_featured_writing(self):
        resp = self.client.get(self.url)
        self.assertIsNone(resp.context["featured_writing"])


# ===================================================================
# Detail View Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingDetailViewTests(TestCase):
    """Tests for WritingDetailView."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_dua = _make_tag("Du'a & Dhikr", "dua-dhikr")
        cls.tag_reflection = _make_tag("Reflection", "reflection")
        cls.writing = _make_writing(
            title="Detail Test Writing",
            body="This is the full body text that should be displayed in its entirety on the detail page.",
            published_date=date(2026, 5, 20),
            tags=[cls.tag_dua, cls.tag_reflection],
        )

    def setUp(self):
        self.url = reverse("writing-detail", kwargs={"pk": self.writing.pk})

    def test_detail_view_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_detail_view_returns_404_for_nonexistent(self):
        url = reverse("writing-detail", kwargs={"pk": 99999})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_detail_view_uses_correct_template(self):
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, "writings/writing_detail.html")

    def test_detail_view_shows_title(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Detail Test Writing")

    def test_detail_view_shows_full_body(self):
        resp = self.client.get(self.url)
        self.assertContains(
            resp,
            "This is the full body text that should be displayed in its entirety on the detail page.",
        )

    def test_detail_view_shows_published_date(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "May 20, 2026")

    def test_detail_view_has_back_link(self):
        resp = self.client.get(self.url)
        list_url = reverse("writing-list")
        self.assertContains(resp, list_url)
        self.assertContains(resp, "Back to writings")

    def test_detail_view_shows_tags(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn("card-tag", content)
        self.assertIn("Reflection", content)

    def test_detail_view_context_has_writing(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["writing"], self.writing)


# ===================================================================
# Create View Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingCreateViewTests(TestCase):
    """Tests for WritingCreateView (staff-only create form)."""

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )
        cls.regular_user = User.objects.create_user(
            username="regular", password="pass123", is_staff=False
        )
        cls.tag_advice = _make_tag("Advice", "advice")
        cls.tag_motivation = _make_tag("Motivation", "motivation")

    def setUp(self):
        self.url = reverse("writing-create")

    # --- Access control ---

    def test_anonymous_user_redirected_to_login_get(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_anonymous_user_redirected_to_login_post(self):
        data = {
            "title": "Sneaky",
            "body": "Should not be created.",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)
        self.assertEqual(Writing.objects.count(), 0)

    def test_non_staff_user_gets_403_get(self):
        self.client.login(username="regular", password="pass123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_non_staff_user_gets_403_post(self):
        self.client.login(username="regular", password="pass123")
        data = {
            "title": "Sneaky",
            "body": "Should not be created.",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Writing.objects.count(), 0)

    # --- Staff access ---

    def test_staff_user_gets_200(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_uses_correct_template(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, "writings/writing_form.html")

    # --- Form fields ---

    def test_form_has_title_field(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertIn('name="title"', resp.content.decode())

    def test_form_has_body_field(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertIn('name="body"', resp.content.decode())

    def test_form_has_tags_field(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertIn('name="tags"', resp.content.decode())

    def test_form_has_published_date_field(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertIn('name="published_date"', resp.content.decode())

    # --- Valid submission ---

    def test_valid_submission_creates_writing(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "New Writing",
            "body": "This is the body of the new writing.",
            "tags": [self.tag_advice.pk, self.tag_motivation.pk],
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(Writing.objects.count(), 1)
        writing = Writing.objects.first()
        self.assertEqual(writing.title, "New Writing")
        self.assertEqual(writing.body, "This is the body of the new writing.")
        self.assertEqual(writing.published_date, date(2026, 3, 1))
        self.assertEqual(writing.tags.count(), 2)

    def test_valid_submission_redirects_to_detail(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "Redirect Writing",
            "body": "Body content.",
            "tags": [self.tag_advice.pk],
            "published_date": "2026-03-05",
        }
        resp = self.client.post(self.url, data)
        writing = Writing.objects.first()
        self.assertRedirects(
            resp,
            reverse("writing-detail", args=[writing.pk]),
            fetch_redirect_response=False,
        )

    # --- Missing required fields ---

    def test_missing_title_shows_form_errors(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "body": "Body content.",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("title", resp.context["form"].errors)
        self.assertEqual(Writing.objects.count(), 0)

    def test_missing_body_shows_form_errors(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "Title Only",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("body", resp.context["form"].errors)
        self.assertEqual(Writing.objects.count(), 0)

    def test_missing_published_date_shows_form_errors(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "No Date",
            "body": "Body content.",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("published_date", resp.context["form"].errors)
        self.assertEqual(Writing.objects.count(), 0)

    # --- Tags are optional ---

    def test_tags_are_optional_on_submission(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "No Tags Post",
            "body": "Body content without tags.",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(Writing.objects.count(), 1)
        writing = Writing.objects.first()
        self.assertEqual(writing.tags.count(), 0)

    # --- Invalid data ---

    def test_invalid_date_rejected(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "Bad Date",
            "body": "Body content.",
            "published_date": "not-a-date",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("published_date", resp.context["form"].errors)
        self.assertEqual(Writing.objects.count(), 0)

    def test_empty_title_is_rejected(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "",
            "body": "Body content.",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("title", resp.context["form"].errors)
        self.assertEqual(Writing.objects.count(), 0)

    def test_empty_body_is_rejected(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "Has Title",
            "body": "",
            "published_date": "2026-03-01",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("body", resp.context["form"].errors)
        self.assertEqual(Writing.objects.count(), 0)

    # --- Context and URLs ---

    def test_context_has_form(self):
        self.client.login(username="staff", password="pass123")
        resp = self.client.get(self.url)
        self.assertIn("form", resp.context)

    def test_success_url_points_to_detail(self):
        self.client.login(username="staff", password="pass123")
        data = {
            "title": "Success URL Test",
            "body": "Body content.",
            "tags": [self.tag_advice.pk],
            "published_date": "2026-06-15",
        }
        resp = self.client.post(self.url, data)
        writing = Writing.objects.get(title="Success URL Test")
        expected_url = reverse("writing-detail", args=[writing.pk])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, expected_url)

    def test_create_url_resolves_to_correct_path(self):
        url = reverse("writing-create")
        self.assertEqual(url, "/writings/create/")


# ===================================================================
# Writing Detail API URL Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingDetailAPIURLTests(TestCase):
    """Tests for the writing detail API URL resolution."""

    def test_api_url_resolves_to_correct_path(self):
        """The named URL 'writing-detail-api' should resolve to /writings/<pk>/api/."""
        url = reverse("writing-detail-api", kwargs={"pk": 1})
        self.assertEqual(url, "/writings/1/api/")

    def test_api_url_name_resolves_correctly(self):
        """Resolving /writings/<pk>/api/ should match the 'writing-detail-api' name."""
        match = resolve("/writings/42/api/")
        self.assertEqual(match.url_name, "writing-detail-api")

    def test_api_url_with_large_pk(self):
        """The API URL should work with large pk values."""
        url = reverse("writing-detail-api", kwargs={"pk": 999999})
        self.assertEqual(url, "/writings/999999/api/")

    def test_api_url_captures_pk_as_int(self):
        """The pk captured by the URL should be an integer."""
        match = resolve("/writings/7/api/")
        self.assertEqual(match.kwargs["pk"], 7)


# ===================================================================
# Writing Detail API View Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingDetailAPIViewTests(TestCase):
    """Tests for the WritingDetailAPIView JSON endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_reflection = _make_tag("Reflection", "reflection")
        cls.tag_advice = _make_tag("Advice", "advice")
        cls.writing = _make_writing(
            title="API Test Writing",
            body="This is the full body text for the API test.",
            published_date=date(2026, 3, 1),
            tags=[cls.tag_reflection, cls.tag_advice],
        )
        cls.writing_no_tags = _make_writing(
            title="No Tags Writing",
            body="A writing without any tags.",
            published_date=date(2026, 2, 15),
        )

    def _get_api(self, pk):
        url = reverse("writing-detail-api", kwargs={"pk": pk})
        return self.client.get(url)

    def test_returns_200_for_existing_writing(self):
        resp = self._get_api(self.writing.pk)
        self.assertEqual(resp.status_code, 200)

    def test_returns_json_content_type(self):
        resp = self._get_api(self.writing.pk)
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_response_contains_correct_title(self):
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        self.assertEqual(data["title"], "API Test Writing")

    def test_response_contains_correct_body_full_not_truncated(self):
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        self.assertEqual(
            data["body"],
            "This is the full body text for the API test.",
        )

    def test_response_contains_correct_published_date_format(self):
        """published_date should be formatted as 'Month Day, Year' e.g. 'March 01, 2026'."""
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        self.assertEqual(data["published_date"], "March 01, 2026")

    def test_response_contains_correct_id(self):
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        self.assertEqual(data["id"], self.writing.pk)

    def test_response_contains_tags_as_list_of_strings(self):
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        self.assertIsInstance(data["tags"], list)
        for tag_name in data["tags"]:
            self.assertIsInstance(tag_name, str)
        self.assertIn("Reflection", data["tags"])
        self.assertIn("Advice", data["tags"])

    def test_response_for_writing_with_no_tags_has_empty_list(self):
        resp = self._get_api(self.writing_no_tags.pk)
        data = resp.json()
        self.assertEqual(data["tags"], [])

    def test_response_for_writing_with_multiple_tags_has_all_tag_names(self):
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        self.assertEqual(len(data["tags"]), 2)
        tag_names = set(data["tags"])
        self.assertEqual(tag_names, {"Reflection", "Advice"})

    def test_returns_404_for_nonexistent_writing(self):
        resp = self._get_api(99999)
        self.assertEqual(resp.status_code, 404)

    def test_response_json_keys_are_exactly_correct(self):
        """The JSON response should contain exactly: id, title, body, published_date, tags."""
        resp = self._get_api(self.writing.pk)
        data = resp.json()
        expected_keys = {"id", "title", "body", "published_date", "tags"}
        self.assertEqual(set(data.keys()), expected_keys)

    def test_response_is_valid_json(self):
        """The response body should be parseable as valid JSON."""
        resp = self._get_api(self.writing.pk)
        try:
            json.loads(resp.content)
        except json.JSONDecodeError:
            self.fail("Response content is not valid JSON")


# ===================================================================
# Writing Detail API Edge Case Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingDetailAPIEdgeCaseTests(TestCase):
    """Edge-case tests for the WritingDetailAPIView."""

    def _get_api(self, pk):
        url = reverse("writing-detail-api", kwargs={"pk": pk})
        return self.client.get(url)

    def test_writing_with_single_character_body(self):
        """A writing with a very short body (single character) should return that body."""
        w = _make_writing(title="Short Body", body="X", published_date=date(2026, 1, 1))
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["body"], "X")

    def test_writing_with_very_long_body_returns_full_content(self):
        """A writing with 5000+ words should return the complete, untruncated body."""
        long_body = " ".join(["word"] * 5500)
        w = _make_writing(
            title="Long Body",
            body=long_body,
            published_date=date(2026, 1, 2),
        )
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["body"], long_body)
        self.assertEqual(len(data["body"].split()), 5500)

    def test_writing_with_html_characters_in_title(self):
        """Special HTML characters in the title should be preserved as-is in JSON."""
        w = _make_writing(
            title="<script>alert('xss')</script>",
            body="Safe body.",
            published_date=date(2026, 1, 3),
        )
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["title"], "<script>alert('xss')</script>")

    def test_writing_with_html_characters_in_body(self):
        """Special HTML characters in the body should be preserved as-is in JSON."""
        w = _make_writing(
            title="HTML Body Test",
            body='<div class="test"><p>Hello & "world"</p></div>',
            published_date=date(2026, 1, 4),
        )
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["body"], '<div class="test"><p>Hello & "world"</p></div>')

    def test_writing_with_unicode_arabic_characters_in_title(self):
        """Arabic/Unicode characters in the title should be preserved correctly."""
        arabic_title = "\u0628\u0650\u0633\u0652\u0645\u0650 \u0627\u0644\u0644\u0651\u064e\u0647\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0646\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
        w = _make_writing(
            title=arabic_title,
            body="Body text.",
            published_date=date(2026, 1, 5),
        )
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["title"], arabic_title)

    def test_writing_with_unicode_arabic_characters_in_body(self):
        """Arabic/Unicode characters in the body should be preserved correctly."""
        arabic_body = "\u0627\u0644\u062d\u0645\u062f \u0644\u0644\u0647 \u0631\u0628 \u0627\u0644\u0639\u0627\u0644\u0645\u064a\u0646"
        w = _make_writing(
            title="Arabic Body",
            body=arabic_body,
            published_date=date(2026, 1, 6),
        )
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["body"], arabic_body)

    def test_writing_with_newlines_in_body(self):
        """Newline characters in the body should be preserved in the JSON response."""
        body_with_newlines = "Line one.\nLine two.\n\nLine four after blank line."
        w = _make_writing(
            title="Newlines",
            body=body_with_newlines,
            published_date=date(2026, 1, 7),
        )
        resp = self._get_api(w.pk)
        data = resp.json()
        self.assertEqual(data["body"], body_with_newlines)
        self.assertIn("\n", data["body"])

    def test_writing_with_pk_zero_returns_404(self):
        """Requesting pk=0 should return 404 (no writing has pk=0)."""
        resp = self._get_api(0)
        self.assertEqual(resp.status_code, 404)

    def test_writing_with_negative_pk_returns_404_or_not_found(self):
        """Requesting a negative pk should either 404 or not match the URL pattern.

        Since <int:pk> only matches non-negative integers, a negative pk
        like /writings/-1/api/ should result in a 404 at the URL routing level.
        """
        resp = self.client.get("/writings/-1/api/")
        self.assertEqual(resp.status_code, 404)


# ===================================================================
# Writing Archive View Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingArchiveViewTests(TestCase):
    """Tests for the WritingArchiveView (paginated grid of all writings)."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_reflection = _make_tag("Reflection", "reflection")
        cls.tag_advice = _make_tag("Advice", "advice")
        cls.writings = []
        for i in range(15):
            tags = [cls.tag_reflection] if i % 2 == 0 else [cls.tag_advice]
            w = _make_writing(
                title=f"Archive Writing {i}",
                body=f"Body of archive writing {i}.",
                published_date=date(2026, 1, 1) + timedelta(days=i),
                tags=tags,
            )
            cls.writings.append(w)

    def setUp(self):
        self.url = reverse("writing-archive")

    def test_archive_url_returns_200(self):
        resp = self.client.get("/writings/all/")
        self.assertEqual(resp.status_code, 200)

    def test_archive_url_name_resolves_correctly(self):
        url = reverse("writing-archive")
        self.assertEqual(url, "/writings/all/")

    def test_archive_uses_correct_template(self):
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, "writings/writing_archive.html")

    def test_archive_context_has_writings(self):
        resp = self.client.get(self.url)
        self.assertIn("writings", resp.context)

    def test_archive_shows_all_writing_titles(self):
        """Page 1 + page 2 together should contain all 15 writing titles."""
        resp1 = self.client.get(self.url)
        resp2 = self.client.get(self.url, {"page": 2})
        content = resp1.content.decode() + resp2.content.decode()
        for w in self.writings:
            self.assertIn(w.title, content)

    def test_archive_cards_link_to_detail(self):
        resp = self.client.get(self.url)
        writings_on_page = resp.context["writings"]
        for w in writings_on_page:
            detail_url = reverse("writing-detail", kwargs={"pk": w.pk})
            self.assertContains(resp, detail_url)

    def test_archive_pagination_page_one_has_twelve(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["writings"]), 12)

    def test_archive_pagination_page_two_works(self):
        resp = self.client.get(self.url, {"page": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["writings"]), 3)

    def test_archive_shows_tag_filter_chips(self):
        resp = self.client.get(self.url)
        self.assertIn("tags", resp.context)
        content = resp.content.decode()
        self.assertIn("Reflection", content)
        self.assertIn("Advice", content)

    def test_archive_tag_filtering_works(self):
        resp = self.client.get(self.url, {"tag": "reflection"})
        self.assertEqual(resp.status_code, 200)
        writings = resp.context["writings"]
        for w in writings:
            self.assertIn(self.tag_reflection, w.tags.all())


# ===================================================================
# Writing Model get_absolute_url Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingModelGetAbsoluteURLTests(TestCase):
    """Tests for the Writing model's get_absolute_url method."""

    def test_get_absolute_url_returns_detail_page_url(self):
        """get_absolute_url should return the writing detail page URL."""
        w = _make_writing(
            title="Absolute URL Test",
            body="Body text.",
            published_date=date(2026, 4, 1),
        )
        expected_url = reverse("writing-detail", kwargs={"pk": w.pk})
        self.assertEqual(w.get_absolute_url(), expected_url)

    def test_get_absolute_url_for_different_pk_values(self):
        """get_absolute_url should return the correct URL for different writings."""
        w1 = _make_writing(
            title="First",
            body="Body one.",
            published_date=date(2026, 4, 2),
        )
        w2 = _make_writing(
            title="Second",
            body="Body two.",
            published_date=date(2026, 4, 3),
        )
        url1 = reverse("writing-detail", kwargs={"pk": w1.pk})
        url2 = reverse("writing-detail", kwargs={"pk": w2.pk})
        self.assertEqual(w1.get_absolute_url(), url1)
        self.assertEqual(w2.get_absolute_url(), url2)
        self.assertNotEqual(w1.get_absolute_url(), w2.get_absolute_url())

    def test_get_absolute_url_returns_string(self):
        """get_absolute_url should return a string."""
        w = _make_writing(
            title="String URL",
            body="Body.",
            published_date=date(2026, 4, 4),
        )
        self.assertIsInstance(w.get_absolute_url(), str)

    def test_get_absolute_url_starts_with_slash(self):
        """get_absolute_url should return a path starting with /."""
        w = _make_writing(
            title="Slash URL",
            body="Body.",
            published_date=date(2026, 4, 5),
        )
        self.assertTrue(w.get_absolute_url().startswith("/"))
