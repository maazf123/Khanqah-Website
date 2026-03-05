"""Tests for writing edit and delete functionality (staff-only, modal-based)."""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tags.models import Tag
from apps.writings.models import Writing


def _make_writing(**kwargs):
    defaults = {
        "title": "Test Writing",
        "body": "Some content here.",
        "published_date": timezone.now().date(),
    }
    defaults.update(kwargs)
    return Writing.objects.create(**defaults)


# ============================================================================
# Writing Update API
# ============================================================================


class WritingUpdateAccessTests(TestCase):
    """Only staff can access the writing update endpoint."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.writing = _make_writing()
        self.url = reverse("writing-update", kwargs={"pk": self.writing.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url, {"title": "New"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url, {"title": "New"})
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(
            self.url, {"title": "Updated", "body": "b"},
            content_type="application/json",
        )
        self.assertIn(response.status_code, [200, 302])

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class WritingUpdateAPITests(TestCase):
    """Tests for the JSON writing update endpoint."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.tag1 = Tag.objects.create(name="Fiqh")
        self.tag2 = Tag.objects.create(name="Hadith")
        self.writing = _make_writing()
        self.writing.tags.add(self.tag1)
        self.url = reverse("writing-update", kwargs={"pk": self.writing.pk})

    def test_returns_json(self):
        response = self.client.post(
            self.url, {"title": "New Title"},
            content_type="application/json",
        )
        self.assertEqual(response["Content-Type"], "application/json")

    def test_updates_title(self):
        self.client.post(
            self.url, {"title": "Updated Title"},
            content_type="application/json",
        )
        self.writing.refresh_from_db()
        self.assertEqual(self.writing.title, "Updated Title")

    def test_updates_body(self):
        self.client.post(
            self.url, {"body": "New body content"},
            content_type="application/json",
        )
        self.writing.refresh_from_db()
        self.assertEqual(self.writing.body, "New body content")

    def test_updates_tags(self):
        self.client.post(
            self.url, {"tags": [self.tag2.pk]},
            content_type="application/json",
        )
        self.writing.refresh_from_db()
        self.assertEqual(list(self.writing.tags.values_list("pk", flat=True)), [self.tag2.pk])

    def test_returns_ok_true(self):
        response = self.client.post(
            self.url, {"title": "X"},
            content_type="application/json",
        )
        self.assertTrue(response.json()["ok"])

    def test_blank_title_returns_error(self):
        response = self.client.post(
            self.url, {"title": ""},
            content_type="application/json",
        )
        data = response.json()
        self.assertFalse(data["ok"])

    def test_blank_body_returns_error(self):
        response = self.client.post(
            self.url, {"body": ""},
            content_type="application/json",
        )
        data = response.json()
        self.assertFalse(data["ok"])

    def test_nonexistent_writing_returns_404(self):
        url = reverse("writing-update", kwargs={"pk": 99999})
        response = self.client.post(
            url, {"title": "X"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_partial_update_preserves_other_fields(self):
        original_body = self.writing.body
        self.client.post(
            self.url, {"title": "Only title changed"},
            content_type="application/json",
        )
        self.writing.refresh_from_db()
        self.assertEqual(self.writing.title, "Only title changed")
        self.assertEqual(self.writing.body, original_body)

    def test_clear_tags(self):
        self.client.post(
            self.url, {"tags": []},
            content_type="application/json",
        )
        self.writing.refresh_from_db()
        self.assertEqual(self.writing.tags.count(), 0)


# ============================================================================
# Writing Delete API
# ============================================================================


class WritingDeleteAccessTests(TestCase):
    """Only staff can delete writings."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.writing = _make_writing()
        self.url = reverse("writing-delete", kwargs={"pk": self.writing.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_gets_403(self):
        self.client.login(username="user", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_delete(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_not_allowed(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class WritingDeleteAPITests(TestCase):
    """Tests for the JSON writing delete endpoint."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        self.writing = _make_writing()
        self.url = reverse("writing-delete", kwargs={"pk": self.writing.pk})

    def test_returns_json(self):
        response = self.client.post(self.url)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_returns_ok(self):
        response = self.client.post(self.url)
        self.assertTrue(response.json()["ok"])

    def test_deletes_writing(self):
        pk = self.writing.pk
        self.client.post(self.url)
        self.assertFalse(Writing.objects.filter(pk=pk).exists())

    def test_nonexistent_returns_404(self):
        url = reverse("writing-delete", kwargs={"pk": 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


# ============================================================================
# Edit/Delete buttons visible on detail page for staff only
# ============================================================================


class WritingDetailAdminButtonsTests(TestCase):
    """Edit/delete icons appear on the detail page only for staff."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pass", is_staff=True)
        self.writing = _make_writing()
        self.url = reverse("writing-detail", kwargs={"pk": self.writing.pk})

    def test_staff_sees_edit_button(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "edit-writing-modal")

    def test_staff_sees_delete_button(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "delete-writing-btn")

    def test_anonymous_does_not_see_edit_button(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "edit-writing-modal")

    def test_anonymous_does_not_see_delete_button(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "delete-writing-btn")
