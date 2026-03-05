from datetime import date, timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import include, path, resolve, reverse

from apps.tags.models import Tag

from .models import Writing


# ---------------------------------------------------------------------------
# Test URL configuration
# The main urls.py may not include writings URLs yet, so we define a
# self-contained URL conf here and override ROOT_URLCONF for every test class
# that touches views/URLs.
# Templates (e.g. base.html) reference urls like 'login', 'logout', and
# 'recording-list', so we must include those patterns here as well.
# ---------------------------------------------------------------------------
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("", include("apps.recordings.urls")),
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


# ===================================================================
# List View Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingListViewTests(TestCase):
    """Tests for WritingListView."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_reflection = _make_tag("Reflection", "reflection")
        cls.tag_advice = _make_tag("Advice", "advice")
        cls.w1 = _make_writing(
            title="First Writing",
            body="Body of the first writing with enough words to test truncation.",
            published_date=date(2026, 3, 1),
            tags=[cls.tag_reflection],
        )
        cls.w2 = _make_writing(
            title="Second Writing",
            body="Body of the second writing.",
            published_date=date(2026, 2, 1),
            tags=[cls.tag_advice],
        )
        cls.w3 = _make_writing(
            title="Third Writing",
            body="Body of the third writing.",
            published_date=date(2026, 1, 1),
        )

    def setUp(self):
        self.url = reverse("writing-list")

    def test_list_view_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_list_view_uses_correct_template(self):
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, "writings/writing_list.html")

    def test_list_view_shows_titles(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "First Writing")
        self.assertContains(resp, "Second Writing")
        self.assertContains(resp, "Third Writing")

    def test_list_view_shows_published_dates(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn("2026", content)
        self.assertIn("1, 2026", content)

    def test_list_view_shows_truncated_body(self):
        long_body = " ".join(["word"] * 60)
        _make_writing(
            title="Long Body Writing",
            body=long_body,
            published_date=date(2026, 4, 1),
        )
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # truncatewords:40 means the full 60-word body should NOT appear
        self.assertNotIn(long_body, content)
        self.assertIn("word", content)
        # The ellipsis marker from truncatewords should be present
        self.assertIn("\u2026", content)

    def test_list_view_cards_link_to_detail(self):
        resp = self.client.get(self.url)
        for w in [self.w1, self.w2, self.w3]:
            detail_url = reverse("writing-detail", kwargs={"pk": w.pk})
            self.assertContains(resp, detail_url)

    def test_list_view_context_has_tags_and_current_tag(self):
        resp = self.client.get(self.url)
        self.assertIn("tags", resp.context)
        self.assertIn("current_tag", resp.context)

    def test_list_view_current_tag_is_none_when_not_filtering(self):
        resp = self.client.get(self.url)
        self.assertIsNone(resp.context["current_tag"])


# ===================================================================
# List View Pagination Tests
# ===================================================================
@override_settings(ROOT_URLCONF="apps.writings.tests")
class WritingListViewPaginationTests(TestCase):
    """Pagination-specific tests (need more objects)."""

    @classmethod
    def setUpTestData(cls):
        for i in range(15):
            _make_writing(
                title=f"Writing {i}",
                published_date=date(2026, 1, 1) + timedelta(days=i),
            )

    def setUp(self):
        self.url = reverse("writing-list")

    def test_page_one_has_twelve_items(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["writings"]), 12)

    def test_page_two_has_three_items(self):
        resp = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(resp.context["writings"]), 3)

    def test_pagination_is_indicated(self):
        resp = self.client.get(self.url)
        self.assertTrue(resp.context["is_paginated"])

    def test_page_two_link_present(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "?page=2")


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

    def test_empty_list_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_empty_list_shows_placeholder_content(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "The Sweetness of Sabr")


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
