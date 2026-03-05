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
    """Tests for the main recordings page with featured + recent layout."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_fiqh = Tag.objects.create(name="Fiqh")
        cls.tag_seerah = Tag.objects.create(name="Seerah")
        # Create 5 recordings with staggered dates so ordering is deterministic
        cls.r1 = _create_recording(
            title="Oldest Recording", speaker="Speaker A",
            description="Oldest desc.",
            recording_date=datetime.date(2025, 1, 1),
        )
        cls.r2 = _create_recording(
            title="Second Recording", speaker="Speaker B",
            recording_date=datetime.date(2025, 2, 1),
        )
        cls.r3 = _create_recording(
            title="Third Recording", speaker="Speaker C",
            recording_date=datetime.date(2025, 3, 1),
        )
        cls.r4 = _create_recording(
            title="Fourth Recording", speaker="Speaker D",
            recording_date=datetime.date(2025, 4, 1),
        )
        cls.r5 = _create_recording(
            title="Featured Recording", speaker="Mufti Abdur Rahman",
            description="A description of the featured bayan.",
            recording_date=datetime.date(2025, 5, 1),
            tags=[cls.tag_fiqh, cls.tag_seerah],
        )
        cls.list_url = reverse("recording-list")

    def test_list_view_returns_200(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_list_view_uses_correct_template(self):
        response = self.client.get(self.list_url)
        self.assertTemplateUsed(response, "recordings/recording_list.html")

    def test_context_has_featured_recording(self):
        """featured_recording is the most recent recording."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.context["featured_recording"], self.r5)

    def test_context_has_recent_recordings(self):
        """recent_recordings contains the next 3 most recent (not the featured)."""
        response = self.client.get(self.list_url)
        recent = list(response.context["recent_recordings"])
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0], self.r4)
        self.assertEqual(recent[1], self.r3)
        self.assertEqual(recent[2], self.r2)

    def test_featured_recording_title_displayed(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, "Featured Recording")

    def test_featured_recording_speaker_displayed(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, "Mufti Abdur Rahman")

    def test_featured_recording_date_displayed(self):
        response = self.client.get(self.list_url)
        # "F d, Y" format -> "May 01, 2025"
        self.assertContains(response, "May 01, 2025")

    def test_featured_recording_shows_tags(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, "Fiqh")
        self.assertContains(response, "Seerah")

    def test_recent_recordings_show_titles(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, "Fourth Recording")
        self.assertContains(response, "Third Recording")
        self.assertContains(response, "Second Recording")

    def test_recent_recordings_link_to_detail_pages(self):
        response = self.client.get(self.list_url)
        for rec in [self.r4, self.r3, self.r2]:
            detail_url = reverse("recording-detail", kwargs={"pk": rec.pk})
            self.assertContains(response, detail_url)

    def test_see_all_recordings_link_present(self):
        """'See all recordings' link points to the archive page."""
        response = self.client.get(self.list_url)
        archive_url = reverse("recording-archive")
        self.assertContains(response, archive_url)
        self.assertContains(response, "See all recordings")

    def test_no_audio_player_on_list_page(self):
        response = self.client.get(self.list_url)
        content = response.content.decode()
        self.assertNotIn("<audio", content,
                         "List view must not contain <audio element")
        self.assertNotIn("audio-player", content,
                         "List view must not contain audio-player class")

    def test_no_tag_filter_chips_on_main_page(self):
        """Main list page should NOT have tag filter chips."""
        response = self.client.get(self.list_url)
        content = response.content.decode()
        self.assertNotIn("tag-filter", content,
                         "List view must not contain tag filter chips")


class RecordingListViewFewRecordingsTests(TestCase):
    """Tests for the main page with fewer than 4 recordings."""

    def test_one_recording_featured_shows_recent_empty(self):
        """With 1 recording: featured is set, recent is empty."""
        _create_recording(title="Only One", recording_date=datetime.date(2025, 1, 1))
        response = self.client.get(reverse("recording-list"))
        self.assertEqual(response.context["featured_recording"].title, "Only One")
        self.assertEqual(len(response.context["recent_recordings"]), 0)

    def test_two_recordings_featured_is_newest_recent_has_one(self):
        """With 2 recordings: featured is newest, recent has 1."""
        _create_recording(title="Older", recording_date=datetime.date(2025, 1, 1))
        r2 = _create_recording(title="Newer", recording_date=datetime.date(2025, 2, 1))
        response = self.client.get(reverse("recording-list"))
        self.assertEqual(response.context["featured_recording"], r2)
        recent = list(response.context["recent_recordings"])
        self.assertEqual(len(recent), 1)

    def test_five_recordings_recent_has_three_not_four(self):
        """With 5 recordings: featured is newest, recent has exactly 3."""
        for i in range(5):
            _create_recording(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
            )
        response = self.client.get(reverse("recording-list"))
        recent = list(response.context["recent_recordings"])
        self.assertEqual(len(recent), 3)


class RecordingArchiveViewTests(TestCase):
    """Tests for the archive page at /recordings/all/."""

    @classmethod
    def setUpTestData(cls):
        cls.tag_dhikr = Tag.objects.create(name="Dhikr")
        cls.tag_fiqh = Tag.objects.create(name="Fiqh")

        cls.recordings = []
        for i in range(15):
            rec = _create_recording(
                title=f"Archive Recording {i:02d}",
                speaker=f"Speaker {chr(65 + i % 3)}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
            )
            cls.recordings.append(rec)

        # Tag the first 5 with Dhikr, next 5 with Fiqh
        for rec in cls.recordings[:5]:
            rec.tags.add(cls.tag_dhikr)
        for rec in cls.recordings[5:10]:
            rec.tags.add(cls.tag_fiqh)

        cls.archive_url = reverse("recording-archive")

    def test_archive_returns_200(self):
        response = self.client.get(self.archive_url)
        self.assertEqual(response.status_code, 200)

    def test_archive_url_name_resolves(self):
        """URL name 'recording-archive' resolves to /recordings/all/."""
        url = reverse("recording-archive")
        self.assertEqual(url, "/recordings/all/")

    def test_archive_uses_correct_template(self):
        response = self.client.get(self.archive_url)
        self.assertTemplateUsed(response, "recordings/recording_archive.html")

    def test_archive_context_has_recordings(self):
        response = self.client.get(self.archive_url)
        self.assertIn("recordings", response.context)

    def test_archive_context_has_tags(self):
        response = self.client.get(self.archive_url)
        self.assertIn("tags", response.context)

    def test_all_recording_titles_appear_across_pages(self):
        """All 15 recording titles appear across page 1 and page 2."""
        page1 = self.client.get(self.archive_url)
        page2 = self.client.get(self.archive_url + "?page=2")
        combined = page1.content.decode() + page2.content.decode()
        for rec in self.recordings:
            self.assertIn(rec.title, combined)

    def test_archive_cards_link_to_detail_pages(self):
        response = self.client.get(self.archive_url)
        for rec in response.context["recordings"]:
            detail_url = reverse("recording-detail", kwargs={"pk": rec.pk})
            self.assertContains(response, detail_url)

    def test_archive_pagination(self):
        """15 recordings, 10 per page: page 1 has 10, page 2 has 5."""
        page1 = self.client.get(self.archive_url)
        self.assertEqual(len(page1.context["recordings"]), 10)
        page2 = self.client.get(self.archive_url + "?page=2")
        self.assertEqual(len(page2.context["recordings"]), 5)

    def test_tag_filter_chips_shown(self):
        """Archive page displays tag filter chips."""
        response = self.client.get(self.archive_url)
        self.assertContains(response, "Dhikr")
        self.assertContains(response, "Fiqh")

    def test_tag_filtering_works(self):
        """Filtering by tag slug returns only matching recordings."""
        response = self.client.get(self.archive_url + "?tag=dhikr")
        self.assertEqual(response.status_code, 200)
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 5)
        for rec in recordings:
            self.assertIn(self.tag_dhikr, rec.tags.all())

    def test_invalid_tag_returns_empty(self):
        """Filtering by a non-existent tag returns no recordings."""
        response = self.client.get(self.archive_url + "?tag=nonexistent")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 0)

    def test_search_link_present_on_archive_page(self):
        """Archive page contains a link to the search page."""
        response = self.client.get(self.archive_url)
        search_url = reverse("recording-search")
        self.assertContains(response, search_url)

    def test_back_to_recordings_link_present(self):
        """Archive page has a 'Back to recordings' link."""
        response = self.client.get(self.archive_url)
        list_url = reverse("recording-list")
        self.assertContains(response, list_url)
        self.assertContains(response, "Back to recordings")


class RecordingListViewEmptyAndContextTests(TestCase):
    """Tests for the main list page when there are no recordings."""

    def test_empty_returns_200(self):
        """Empty list view returns HTTP 200."""
        self.assertEqual(Recording.objects.count(), 0)
        response = self.client.get(reverse("recording-list"))
        self.assertEqual(response.status_code, 200)

    def test_empty_shows_no_recordings_message(self):
        """Empty list view displays 'No recordings yet' message."""
        response = self.client.get(reverse("recording-list"))
        self.assertContains(response, "No recordings yet")

    def test_empty_featured_recording_is_none(self):
        """When empty, featured_recording is None."""
        response = self.client.get(reverse("recording-list"))
        self.assertIsNone(response.context["featured_recording"])


class RecordingArchiveSearchIntegrationTests(TestCase):
    """Tests for search integration with the archive/recordings pages."""

    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name="Dhikr")
        cls.r1 = _create_recording(
            title="Morning Dhikr Session",
            speaker="Sheikh Ahmad",
            description="A morning session.",
            recording_date=datetime.date(2025, 3, 1),
            tags=[cls.tag],
        )
        cls.r2 = _create_recording(
            title="Fiqh Lesson",
            speaker="Mufti Bilal",
            description="An advanced fiqh lesson.",
            recording_date=datetime.date(2025, 3, 2),
        )
        cls.search_url = reverse("recording-search")

    def test_search_page_returns_200(self):
        response = self.client.get(self.search_url)
        self.assertEqual(response.status_code, 200)

    def test_search_with_query_returns_matching_results(self):
        response = self.client.get(self.search_url + "?q=Dhikr")
        self.assertEqual(response.status_code, 200)
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0], self.r1)

    def test_search_with_no_query_returns_no_results(self):
        response = self.client.get(self.search_url)
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 0)

    def test_search_filters_by_tag(self):
        """Search with a tag param filters results by that tag."""
        response = self.client.get(self.search_url + "?q=Session&tag=dhikr")
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0], self.r1)


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
