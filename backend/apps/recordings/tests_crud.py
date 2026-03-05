import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _audio():
    return SimpleUploadedFile("test.mp3", b"fake-audio", content_type="audio/mpeg")


class AddRecordingButtonTests(TestCase):
    """The recordings list page shows an 'Add' button only for staff."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")
        self.staff = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )

    def test_anonymous_does_not_see_add_button(self):
        response = self.client.get(self.url)
        self.assertNotIn("Add Recording", response.content.decode())

    def test_staff_sees_add_button(self):
        self.client.login(username="staff", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("Add Recording", response.content.decode())

    def test_add_button_links_to_create_page(self):
        self.client.login(username="staff", password="pass123")
        response = self.client.get(self.url)
        create_url = reverse("recording-create")
        self.assertIn(create_url, response.content.decode())


class RecordingCreateAccessTests(TestCase):
    """Only staff can access the create recording page."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-create")
        self.staff = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_non_staff_gets_403(self):
        User.objects.create_user(username="regular", password="pass123")
        self.client.login(username="regular", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_gets_200(self):
        self.client.login(username="staff", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class RecordingCreateFormTests(TestCase):
    """The create page renders a form with the correct fields."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-create")
        self.staff = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )
        self.client.login(username="staff", password="pass123")

    def test_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "recordings/recording_form.html")

    def test_form_has_title_field(self):
        response = self.client.get(self.url)
        self.assertIn('name="title"', response.content.decode())

    def test_form_has_description_field(self):
        response = self.client.get(self.url)
        self.assertIn('name="description"', response.content.decode())

    def test_form_has_audio_file_field(self):
        response = self.client.get(self.url)
        self.assertIn('name="audio_file"', response.content.decode())

    def test_form_has_tags_field(self):
        response = self.client.get(self.url)
        self.assertIn('name="tags"', response.content.decode())

    def test_form_has_enctype_multipart(self):
        response = self.client.get(self.url)
        self.assertIn('enctype="multipart/form-data"', response.content.decode())

    def test_form_does_not_have_speaker_field(self):
        """Speaker is auto-set from the logged-in user."""
        response = self.client.get(self.url)
        self.assertNotIn('name="speaker"', response.content.decode())

    def test_form_does_not_have_recording_date_field(self):
        """Recording date is auto-set to today."""
        response = self.client.get(self.url)
        self.assertNotIn('name="recording_date"', response.content.decode())


class RecordingCreatePostTests(TestCase):
    """POST to the create view creates a recording and redirects."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-create")
        self.staff = User.objects.create_user(
            username="staff", password="pass123", is_staff=True
        )
        self.client.login(username="staff", password="pass123")
        self.tag = Tag.objects.create(name="Fiqh")

    def test_valid_post_creates_recording(self):
        data = {
            "title": "New Lecture",
            "description": "A new lecture.",
            "audio_file": _audio(),
            "tags": [self.tag.pk],
        }
        self.client.post(self.url, data)
        self.assertEqual(Recording.objects.count(), 1)
        rec = Recording.objects.first()
        self.assertEqual(rec.title, "New Lecture")

    def test_valid_post_redirects_to_list(self):
        data = {
            "title": "New Lecture",
            "description": "",
            "audio_file": _audio(),
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("recording-list"),
            fetch_redirect_response=False,
        )

    def test_valid_post_assigns_tags(self):
        tag2 = Tag.objects.create(name="Seerah")
        data = {
            "title": "Tagged Lecture",
            "audio_file": _audio(),
            "tags": [self.tag.pk, tag2.pk],
        }
        self.client.post(self.url, data)
        rec = Recording.objects.first()
        self.assertEqual(rec.tags.count(), 2)

    def test_missing_title_does_not_create(self):
        data = {
            "audio_file": _audio(),
        }
        response = self.client.post(self.url, data)
        self.assertEqual(Recording.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_missing_audio_does_not_create(self):
        data = {
            "title": "No Audio",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(Recording.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_tags_are_optional(self):
        data = {
            "title": "No Tags Lecture",
            "audio_file": _audio(),
        }
        self.client.post(self.url, data)
        self.assertEqual(Recording.objects.count(), 1)
        self.assertEqual(Recording.objects.first().tags.count(), 0)

    def test_recording_date_auto_set_to_today(self):
        data = {
            "title": "Auto Date",
            "audio_file": _audio(),
        }
        self.client.post(self.url, data)
        rec = Recording.objects.first()
        self.assertEqual(rec.recording_date, timezone.now().date())

    def test_speaker_auto_set_from_user(self):
        data = {
            "title": "Auto Speaker",
            "audio_file": _audio(),
        }
        self.client.post(self.url, data)
        rec = Recording.objects.first()
        self.assertEqual(rec.speaker, "staff")

    def test_anonymous_post_redirects_to_login(self):
        self.client.logout()
        data = {
            "title": "Sneaky",
            "audio_file": _audio(),
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
        self.assertEqual(Recording.objects.count(), 0)
