import datetime

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _make_audio_file(name="test.mp3"):
    """Return a minimal SimpleUploadedFile to satisfy the FileField."""
    return SimpleUploadedFile(name, b"fake-audio-bytes", content_type="audio/mpeg")


def _create_recording(title="Test Recording", speaker="Test Speaker",
                      description="", recording_date=None, tags=None):
    """Helper to create a Recording with sensible defaults."""
    if recording_date is None:
        recording_date = datetime.date(2025, 6, 15)
    recording = Recording.objects.create(
        title=title,
        speaker=speaker,
        description=description,
        audio_file=_make_audio_file(f"{title}.mp3"),
        recording_date=recording_date,
    )
    if tags:
        recording.tags.add(*tags)
    return recording


# ---------------------------------------------------------------------------
# Model Tests (1-6)
# ---------------------------------------------------------------------------

class RecordingModelTests(TestCase):
    """Tests 1-6: Recording model creation, __str__, ordering, blank
    description, tags, and tag limit validation."""

    def test_1_recording_creation_with_all_fields(self):
        """1. Recording can be created with all fields populated."""
        tag = Tag.objects.create(name="Tassawuf")
        recording = Recording.objects.create(
            title="Friday Bayan",
            description="A detailed bayan on tawakkul.",
            speaker="Mufti Abdur Rahman",
            audio_file=_make_audio_file(),
            recording_date=datetime.date(2025, 2, 28),
        )
        recording.tags.add(tag)

        self.assertIsNotNone(recording.pk)
        self.assertEqual(recording.title, "Friday Bayan")
        self.assertEqual(recording.description, "A detailed bayan on tawakkul.")
        self.assertEqual(recording.speaker, "Mufti Abdur Rahman")
        self.assertEqual(recording.recording_date, datetime.date(2025, 2, 28))
        self.assertIsNotNone(recording.uploaded_at)
        self.assertIn(tag, recording.tags.all())

    def test_2_recording_str_method(self):
        """2. __str__ returns 'title - speaker'."""
        recording = _create_recording(title="Morning Dhikr", speaker="Sheikh Ahmad")
        self.assertEqual(str(recording), "Morning Dhikr - Sheikh Ahmad")

    def test_3_recording_ordering_by_uploaded_at_desc(self):
        """3. Recordings are ordered by -uploaded_at (newest first)."""
        r1 = _create_recording(title="First")
        r2 = _create_recording(title="Second")
        r3 = _create_recording(title="Third")
        recordings = list(Recording.objects.all())
        self.assertEqual(recordings[0], r3)
        self.assertEqual(recordings[1], r2)
        self.assertEqual(recordings[2], r1)

    def test_4_recording_with_blank_description(self):
        """4. Recording can be created with a blank description (defaults to '')."""
        recording = _create_recording(title="No Description", description="")
        self.assertEqual(recording.description, "")
        # full_clean should not raise
        recording.full_clean()

    def test_5_recording_with_tags(self):
        """5. Recording can have multiple tags via the M2M relationship."""
        tag1 = Tag.objects.create(name="Fiqh")
        tag2 = Tag.objects.create(name="Seerah")
        tag3 = Tag.objects.create(name="Dhikr")
        recording = _create_recording(title="Tagged Recording", tags=[tag1, tag2, tag3])
        self.assertEqual(recording.tags.count(), 3)
        self.assertIn(tag1, recording.tags.all())
        self.assertIn(tag2, recording.tags.all())
        self.assertIn(tag3, recording.tags.all())

    def test_6_tag_validation_max_10_tags(self):
        """6. clean() raises ValidationError when more than 10 tags are assigned."""
        tags = [Tag.objects.create(name=f"Tag{i}") for i in range(11)]
        recording = _create_recording(title="Too Many Tags")
        recording.tags.add(*tags)
        self.assertEqual(recording.tags.count(), 11)
        with self.assertRaises(ValidationError):
            recording.clean()

    def test_6b_exactly_10_tags_is_allowed(self):
        """6b. clean() does NOT raise when exactly 10 tags are assigned."""
        tags = [Tag.objects.create(name=f"OkTag{i}") for i in range(10)]
        recording = _create_recording(title="Ten Tags")
        recording.tags.add(*tags)
        self.assertEqual(recording.tags.count(), 10)
        # Should not raise
        recording.clean()


# ---------------------------------------------------------------------------
# List View Tests (7-19)
# ---------------------------------------------------------------------------

class RecordingListViewTests(TestCase):
    """Tests 7-19: Recording list view behaviour, template, content, filtering,
    pagination, and the critical absence of audio player elements."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_fiqh = Tag.objects.create(name="Fiqh")
        cls.tag_seerah = Tag.objects.create(name="Seerah")
        cls.recording = Recording.objects.create(
            title="Friday Bayan",
            description="A description of the bayan.",
            speaker="Mufti Abdur Rahman",
            audio_file=_make_audio_file("friday.mp3"),
            recording_date=datetime.date(2025, 2, 28),
        )
        cls.recording.tags.add(cls.tag_fiqh, cls.tag_seerah)
        cls.list_url = reverse("recording-list")

    def test_7_list_view_returns_200(self):
        """7. List view returns HTTP 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_8_list_view_uses_correct_template(self):
        """8. List view uses recordings/recording_list.html template."""
        response = self.client.get(self.list_url)
        self.assertTemplateUsed(response, "recordings/recording_list.html")

    def test_9_list_view_shows_recording_titles(self):
        """9. List view displays recording titles."""
        response = self.client.get(self.list_url)
        self.assertContains(response, self.recording.title)

    def test_10_list_view_shows_recording_speakers(self):
        """10. List view displays recording speakers."""
        response = self.client.get(self.list_url)
        self.assertContains(response, self.recording.speaker)

    def test_11_list_view_shows_recording_dates(self):
        """11. List view displays recording dates."""
        response = self.client.get(self.list_url)
        # Template formats date as "M d, Y" e.g. "Feb 28, 2025"
        formatted_date = "Feb 28, 2025"
        self.assertContains(response, formatted_date)

    def test_12_list_view_shows_tags_on_cards(self):
        """12. List view shows tags on recording cards."""
        response = self.client.get(self.list_url)
        self.assertContains(response, "Fiqh")
        self.assertContains(response, "Seerah")

    def test_13_list_view_does_not_contain_audio_player(self):
        """13. List view does NOT contain audio player elements.

        The audio player (including <audio tags, .audio-player class, and
        .play-btn class) should only appear on the detail page, not on
        the list page.
        """
        response = self.client.get(self.list_url)
        content = response.content.decode()
        self.assertNotIn("<audio", content,
                         "List view must not contain <audio element")
        self.assertNotIn("audio-player", content,
                         "List view must not contain audio-player class")
        self.assertNotIn("play-btn", content,
                         "List view must not contain play-btn class")

    def test_14_each_card_links_to_detail_page(self):
        """14. Each recording card has a link to its detail page."""
        response = self.client.get(self.list_url)
        detail_url = reverse("recording-detail", kwargs={"pk": self.recording.pk})
        self.assertContains(response, detail_url)

    def test_14b_card_link_is_within_anchor_tag(self):
        """14b. The detail URL appears inside an <a href=...> tag."""
        response = self.client.get(self.list_url)
        detail_url = reverse("recording-detail", kwargs={"pk": self.recording.pk})
        content = response.content.decode()
        self.assertIn(f'href="{detail_url}"', content)


class RecordingListViewPaginationTests(TestCase):
    """Test 15: List view pagination."""

    @classmethod
    def setUpTestData(cls):
        cls.list_url = reverse("recording-list")
        # Create 15 recordings to test pagination (paginate_by=10)
        for i in range(15):
            Recording.objects.create(
                title=f"Recording {i:02d}",
                speaker=f"Speaker {i}",
                audio_file=_make_audio_file(f"rec{i}.mp3"),
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
            )

    def test_15_pagination_page1_has_10_recordings(self):
        """15a. Page 1 has 10 recordings."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 10)

    def test_15_pagination_page2_has_5_recordings(self):
        """15b. Page 2 has 5 recordings."""
        response = self.client.get(self.list_url + "?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 5)

    def test_15_pagination_is_paginated_flag(self):
        """15c. Context has is_paginated=True when items exceed paginate_by."""
        response = self.client.get(self.list_url)
        self.assertTrue(response.context["is_paginated"])


class RecordingListViewFilterTests(TestCase):
    """Tests 16-17: List view filtering by tag slug and speaker."""

    @classmethod
    def setUpTestData(cls):
        cls.list_url = reverse("recording-list")
        cls.tag_dhikr = Tag.objects.create(name="Dhikr")
        cls.tag_fiqh = Tag.objects.create(name="Fiqh")

        cls.r1 = Recording.objects.create(
            title="Dhikr Session",
            speaker="Speaker A",
            audio_file=_make_audio_file("dhikr.mp3"),
            recording_date=datetime.date(2025, 3, 1),
        )
        cls.r1.tags.add(cls.tag_dhikr)

        cls.r2 = Recording.objects.create(
            title="Fiqh Lesson",
            speaker="Speaker B",
            audio_file=_make_audio_file("fiqh.mp3"),
            recording_date=datetime.date(2025, 3, 2),
        )
        cls.r2.tags.add(cls.tag_fiqh)

        cls.r3 = Recording.objects.create(
            title="Another Dhikr",
            speaker="Speaker A",
            audio_file=_make_audio_file("dhikr2.mp3"),
            recording_date=datetime.date(2025, 3, 3),
        )
        cls.r3.tags.add(cls.tag_dhikr)

    def test_16_filter_by_tag_slug(self):
        """16. List view filters recordings by tag slug query parameter."""
        response = self.client.get(self.list_url + "?tag=dhikr")
        self.assertEqual(response.status_code, 200)
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 2)
        for rec in recordings:
            self.assertIn(self.tag_dhikr, rec.tags.all())

    def test_16b_filter_by_tag_excludes_unmatched(self):
        """16b. Filtering by tag excludes recordings without that tag."""
        response = self.client.get(self.list_url + "?tag=fiqh")
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0], self.r2)

    def test_17_filter_by_speaker(self):
        """17. List view filters recordings by speaker query parameter."""
        response = self.client.get(self.list_url + "?speaker=Speaker+A")
        self.assertEqual(response.status_code, 200)
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 2)
        for rec in recordings:
            self.assertEqual(rec.speaker, "Speaker A")

    def test_17b_filter_by_speaker_excludes_unmatched(self):
        """17b. Filtering by speaker excludes recordings by other speakers."""
        response = self.client.get(self.list_url + "?speaker=Speaker+B")
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0], self.r2)


class RecordingListViewEmptyAndContextTests(TestCase):
    """Tests 18-19: Empty list view and context contents."""

    def test_18_empty_list_view_returns_200(self):
        """18. List view returns 200 even when there are no recordings."""
        self.assertEqual(Recording.objects.count(), 0)
        response = self.client.get(reverse("recording-list"))
        self.assertEqual(response.status_code, 200)

    def test_19_list_view_context_contains_tags_and_recordings(self):
        """19. List view context contains 'tags' and 'recordings' keys."""
        Tag.objects.create(name="SomeTag")
        _create_recording(title="Context Test")
        response = self.client.get(reverse("recording-list"))
        self.assertIn("tags", response.context)
        self.assertIn("recordings", response.context)

    def test_19b_context_tags_contains_all_tags(self):
        """19b. The 'tags' context variable contains all Tag objects."""
        t1 = Tag.objects.create(name="Alpha")
        t2 = Tag.objects.create(name="Beta")
        response = self.client.get(reverse("recording-list"))
        context_tags = list(response.context["tags"])
        self.assertIn(t1, context_tags)
        self.assertIn(t2, context_tags)


# ---------------------------------------------------------------------------
# Detail View Tests (20-30)
# ---------------------------------------------------------------------------

class RecordingDetailViewTests(TestCase):
    """Tests 20-30: Recording detail view behaviour, template, content,
    audio player presence, and back link."""

    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name="Tazkiyah")
        cls.recording_with_desc = Recording.objects.create(
            title="Purification of the Heart",
            description="A powerful reminder on spiritual diseases.",
            speaker="Shaykh Bilal Hussain",
            audio_file=_make_audio_file("purification.mp3"),
            recording_date=datetime.date(2025, 2, 21),
        )
        cls.recording_with_desc.tags.add(cls.tag)
        cls.detail_url_with_desc = reverse(
            "recording-detail",
            kwargs={"pk": cls.recording_with_desc.pk},
        )

        cls.recording_no_desc = Recording.objects.create(
            title="Evening Dhikr",
            description="",
            speaker="Mufti Abdur Rahman",
            audio_file=_make_audio_file("dhikr.mp3"),
            recording_date=datetime.date(2025, 3, 10),
        )
        cls.detail_url_no_desc = reverse(
            "recording-detail",
            kwargs={"pk": cls.recording_no_desc.pk},
        )

    def test_20_detail_view_returns_200(self):
        """20. Detail view returns 200 for an existing recording."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertEqual(response.status_code, 200)

    def test_21_detail_view_returns_404_for_nonexistent(self):
        """21. Detail view returns 404 for a non-existent recording."""
        bad_url = reverse("recording-detail", kwargs={"pk": 99999})
        response = self.client.get(bad_url)
        self.assertEqual(response.status_code, 404)

    def test_22_detail_view_uses_correct_template(self):
        """22. Detail view uses recordings/recording_detail.html template."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertTemplateUsed(response, "recordings/recording_detail.html")

    def test_23_detail_view_shows_title(self):
        """23. Detail view displays the recording title."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "Purification of the Heart")

    def test_24_detail_view_shows_speaker(self):
        """24. Detail view displays the recording speaker."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "Shaykh Bilal Hussain")

    def test_25_detail_view_shows_date(self):
        """25. Detail view displays the recording date."""
        response = self.client.get(self.detail_url_with_desc)
        # Detail template formats as "F d, Y" e.g. "February 21, 2025"
        self.assertContains(response, "February 21, 2025")

    def test_26_detail_view_shows_description_when_present(self):
        """26. Detail view shows description when it is non-empty."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "A powerful reminder on spiritual diseases.")

    def test_27_detail_view_hides_description_when_blank(self):
        """27. Detail view does NOT show the description section when
        description is blank."""
        response = self.client.get(self.detail_url_no_desc)
        content = response.content.decode()
        # The template wraps description in a div with class "detail-description"
        # and an h3 "Description". Neither should appear for blank descriptions.
        self.assertNotIn("detail-description", content)

    def test_28_detail_view_contains_audio_player(self):
        """28. Detail view contains an audio player (has <audio tag or
        audio-player class)."""
        response = self.client.get(self.detail_url_with_desc)
        content = response.content.decode()
        has_audio_tag = "<audio" in content
        has_audio_player_class = "audio-player" in content
        self.assertTrue(
            has_audio_tag or has_audio_player_class,
            "Detail view must contain an audio player (<audio element "
            "or audio-player class)",
        )

    def test_28b_detail_view_audio_tag_present(self):
        """28b. Detail view specifically contains an <audio element."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "<audio")

    def test_28c_detail_view_audio_player_class_present(self):
        """28c. Detail view contains the audio-player class."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "audio-player")

    def test_29_detail_view_shows_tags(self):
        """29. Detail view shows the recording's tags."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "Tazkiyah")

    def test_30_detail_view_has_back_link_to_list(self):
        """30. Detail view has a back link to the recording list page."""
        response = self.client.get(self.detail_url_with_desc)
        list_url = reverse("recording-list")
        self.assertContains(response, list_url)

    def test_30b_back_link_text_present(self):
        """30b. Detail view contains 'Back to recordings' text."""
        response = self.client.get(self.detail_url_with_desc)
        self.assertContains(response, "Back to recordings")
