"""
Exhaustive tests for the recordings list view (public browse page).

The view under test:
- URL: `/` (homepage), name: `recording-list`
- Django ListView on Recording model
- Template: `recordings/recording_list.html`
- Paginated by 10
- Context: `recordings` (page object), `tags` (all tags)
- Filters: `?tag=<slug>`, `?speaker=<name>`
"""

from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _fake_audio():
    """Return a minimal SimpleUploadedFile that stands in for an audio file."""
    return SimpleUploadedFile(
        "test.mp3", b"\x00" * 128, content_type="audio/mpeg"
    )


def _create_recording(title="Test", speaker="Speaker", recording_date=None,
                       tags=None, **kwargs):
    """Helper to create a Recording with sensible defaults."""
    if recording_date is None:
        recording_date = date.today()
    rec = Recording.objects.create(
        title=title,
        speaker=speaker,
        audio_file=_fake_audio(),
        recording_date=recording_date,
        **kwargs,
    )
    if tags:
        rec.tags.set(tags)
    return rec


class RecordingListBasicTests(TestCase):
    """Basic page loading and template tests."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")

    # ---- 1. GET / returns 200 ----
    def test_get_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    # ---- 2. Uses the correct template ----
    def test_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "recordings/recording_list.html")

    # ---- 3. Empty state -- no recordings, page still returns 200 ----
    def test_empty_state_returns_200(self):
        self.assertEqual(Recording.objects.count(), 0)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    # ---- 4. Context contains `tags` queryset (all tags) ----
    def test_context_contains_all_tags(self):
        t1 = Tag.objects.create(name="Fiqh")
        t2 = Tag.objects.create(name="Tafsir")
        t3 = Tag.objects.create(name="Hadith")
        response = self.client.get(self.url)
        tags_in_ctx = set(response.context["tags"])
        self.assertEqual(tags_in_ctx, {t1, t2, t3})

    def test_tags_in_context_even_when_no_recordings(self):
        """Tags should appear regardless of whether recordings exist."""
        Tag.objects.create(name="Aqeedah")
        response = self.client.get(self.url)
        self.assertEqual(response.context["tags"].count(), 1)


class RecordingListDisplayTests(TestCase):
    """Tests for how recordings appear in context."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")

    # ---- 5. Recordings appear in context ----
    def test_recordings_appear_in_context(self):
        _create_recording(title="Lecture 1")
        _create_recording(title="Lecture 2")
        response = self.client.get(self.url)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 2)

    # ---- 6. Recordings are ordered newest first (by uploaded_at) ----
    def test_recordings_ordered_newest_first(self):
        r1 = _create_recording(title="Older Lecture")
        r2 = _create_recording(title="Newer Lecture")
        # r2 was created after r1 so it should appear first
        response = self.client.get(self.url)
        recordings = list(response.context["recordings"])
        self.assertEqual(recordings[0], r2)
        self.assertEqual(recordings[1], r1)

    # ---- 7. Recording title, speaker, date, and tags accessible in context ----
    def test_recording_fields_accessible(self):
        tag = Tag.objects.create(name="Tasawwuf")
        rec = _create_recording(
            title="Special Lecture",
            speaker="Shaykh Ahmad",
            recording_date=date(2025, 6, 15),
            tags=[tag],
        )
        response = self.client.get(self.url)
        recording = response.context["recordings"][0]
        self.assertEqual(recording.title, "Special Lecture")
        self.assertEqual(recording.speaker, "Shaykh Ahmad")
        self.assertEqual(recording.recording_date, date(2025, 6, 15))
        self.assertIn(tag, recording.tags.all())


class RecordingListPaginationTests(TestCase):
    """Tests for pagination behaviour (paginate_by=10)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")

    def _create_n_recordings(self, n):
        """Create n recordings with distinct titles."""
        recs = []
        for i in range(n):
            recs.append(
                _create_recording(
                    title=f"Recording {i}",
                    recording_date=date.today() - timedelta(days=i),
                )
            )
        return recs

    # ---- 8. First page shows at most 10 recordings ----
    def test_first_page_has_at_most_10(self):
        self._create_n_recordings(12)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["recordings"]), 10)

    # ---- 9. 15 recordings -> page 1 has 10, page 2 has 5 ----
    def test_15_recordings_split_across_pages(self):
        self._create_n_recordings(15)
        page1 = self.client.get(self.url)
        page2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(page1.context["recordings"]), 10)
        self.assertEqual(len(page2.context["recordings"]), 5)

    # ---- 10. ?page=2 returns the second page ----
    def test_page_2_query_param(self):
        self._create_n_recordings(15)
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)

    # ---- 11. Invalid page number (e.g., ?page=999) returns 404 ----
    def test_invalid_page_number_returns_404(self):
        self._create_n_recordings(15)
        response = self.client.get(self.url, {"page": 999})
        self.assertEqual(response.status_code, 404)

    # ---- 12. ?page=abc returns first page or 404 ----
    def test_non_numeric_page_returns_first_page_or_404(self):
        self._create_n_recordings(5)
        response = self.client.get(self.url, {"page": "abc"})
        # Either falls back to page 1 (200) or returns 404
        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 200:
            page_obj = response.context["recordings"]
            self.assertEqual(page_obj.number, 1)

    def test_exactly_10_recordings_single_page(self):
        """Edge case: exactly paginate_by count means only 1 page."""
        self._create_n_recordings(10)
        response = self.client.get(self.url)
        page_obj = response.context["page_obj"]
        self.assertFalse(page_obj.has_next())
        self.assertEqual(len(response.context["recordings"]), 10)

    def test_zero_recordings_pagination(self):
        """With no recordings the page should still be valid."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 0)


class RecordingListTagFilterTests(TestCase):
    """Tests for the ?tag=<slug> query parameter filtering."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")
        self.tag_fiqh = Tag.objects.create(name="Fiqh")
        self.tag_hadith = Tag.objects.create(name="Hadith")

    # ---- 13. ?tag=<slug> filters recordings to only those with that tag ----
    def test_filter_by_tag(self):
        rec_fiqh = _create_recording(title="Fiqh Lecture", tags=[self.tag_fiqh])
        rec_hadith = _create_recording(title="Hadith Lecture", tags=[self.tag_hadith])
        rec_both = _create_recording(title="Combined", tags=[self.tag_fiqh, self.tag_hadith])

        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        recordings = list(response.context["recordings"])
        recording_ids = {r.pk for r in recordings}
        self.assertIn(rec_fiqh.pk, recording_ids)
        self.assertIn(rec_both.pk, recording_ids)
        self.assertNotIn(rec_hadith.pk, recording_ids)

    # ---- 14. ?tag=<slug> with nonexistent slug returns empty results ----
    def test_filter_by_nonexistent_tag_returns_empty(self):
        _create_recording(title="Something", tags=[self.tag_fiqh])
        response = self.client.get(self.url, {"tag": "nonexistent-slug"})
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 0)

    # ---- 15. Filtering by tag still paginates correctly ----
    def test_tag_filter_paginates(self):
        for i in range(15):
            _create_recording(
                title=f"Fiqh Rec {i}",
                recording_date=date.today() - timedelta(days=i),
                tags=[self.tag_fiqh],
            )
        # Also create some with different tag; they should NOT appear
        for i in range(5):
            _create_recording(title=f"Hadith Rec {i}", tags=[self.tag_hadith])

        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        self.assertEqual(len(response.context["recordings"]), 10)

        response_p2 = self.client.get(
            self.url, {"tag": self.tag_fiqh.slug, "page": 2}
        )
        self.assertEqual(len(response_p2.context["recordings"]), 5)

    # ---- 16. Tag filter + pagination combined works ----
    def test_tag_filter_and_pagination_combined(self):
        for i in range(12):
            _create_recording(
                title=f"Tagged Rec {i}",
                recording_date=date.today() - timedelta(days=i),
                tags=[self.tag_hadith],
            )
        response = self.client.get(
            self.url, {"tag": self.tag_hadith.slug, "page": 2}
        )
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 2)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)

    def test_tag_filter_preserves_ordering(self):
        """Filtered recordings should still be newest-first."""
        r_old = _create_recording(title="Old Fiqh", tags=[self.tag_fiqh])
        r_new = _create_recording(title="New Fiqh", tags=[self.tag_fiqh])
        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        recordings = list(response.context["recordings"])
        self.assertEqual(recordings[0], r_new)
        self.assertEqual(recordings[1], r_old)

    def test_empty_tag_param_returns_all(self):
        """An empty ?tag= should not filter (return all recordings)."""
        _create_recording(title="Rec A", tags=[self.tag_fiqh])
        _create_recording(title="Rec B", tags=[self.tag_hadith])
        response = self.client.get(self.url, {"tag": ""})
        self.assertEqual(response.status_code, 200)
        # Should return all recordings (no filtering applied)
        self.assertEqual(len(response.context["recordings"]), 2)


class RecordingListSpeakerFilterTests(TestCase):
    """Tests for the ?speaker=<name> query parameter filtering."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")

    # ---- 17. ?speaker=<name> filters recordings by speaker ----
    def test_filter_by_speaker(self):
        rec_a = _create_recording(title="Lecture A", speaker="Shaykh Ahmad")
        rec_b = _create_recording(title="Lecture B", speaker="Mufti Bilal")
        rec_c = _create_recording(title="Lecture C", speaker="Shaykh Ahmad")

        response = self.client.get(self.url, {"speaker": "Shaykh Ahmad"})
        recordings = list(response.context["recordings"])
        recording_ids = {r.pk for r in recordings}
        self.assertIn(rec_a.pk, recording_ids)
        self.assertIn(rec_c.pk, recording_ids)
        self.assertNotIn(rec_b.pk, recording_ids)
        self.assertEqual(len(recordings), 2)

    # ---- 18. Speaker filter with no matches returns empty results ----
    def test_speaker_filter_no_matches(self):
        _create_recording(title="Lecture", speaker="Shaykh Ahmad")
        response = self.client.get(self.url, {"speaker": "Nonexistent Speaker"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 0)

    def test_speaker_filter_preserves_ordering(self):
        """Filtered-by-speaker results should still be newest-first."""
        r_old = _create_recording(title="Old", speaker="Imam Zaid")
        r_new = _create_recording(title="New", speaker="Imam Zaid")
        response = self.client.get(self.url, {"speaker": "Imam Zaid"})
        recordings = list(response.context["recordings"])
        self.assertEqual(recordings[0], r_new)
        self.assertEqual(recordings[1], r_old)

    def test_speaker_filter_paginates(self):
        """Speaker filter should still respect pagination."""
        for i in range(12):
            _create_recording(
                title=f"Rec {i}",
                speaker="Shaykh Ahmad",
                recording_date=date.today() - timedelta(days=i),
            )
        _create_recording(title="Other", speaker="Mufti Bilal")

        response = self.client.get(self.url, {"speaker": "Shaykh Ahmad"})
        self.assertEqual(len(response.context["recordings"]), 10)

        response_p2 = self.client.get(
            self.url, {"speaker": "Shaykh Ahmad", "page": 2}
        )
        self.assertEqual(len(response_p2.context["recordings"]), 2)

    def test_empty_speaker_param_returns_all(self):
        """An empty ?speaker= should not filter."""
        _create_recording(title="A", speaker="Speaker A")
        _create_recording(title="B", speaker="Speaker B")
        response = self.client.get(self.url, {"speaker": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 2)


class RecordingListCombinedFilterTests(TestCase):
    """Tests for combining ?tag=<slug>&speaker=<name> filters."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")
        self.tag = Tag.objects.create(name="Tazkiyah")

    # ---- 19. ?tag=<slug>&speaker=<name> combines both filters ----
    def test_combined_tag_and_speaker_filter(self):
        rec_match = _create_recording(
            title="Match", speaker="Shaykh Ahmad", tags=[self.tag]
        )
        rec_tag_only = _create_recording(
            title="Tag Only", speaker="Mufti Bilal", tags=[self.tag]
        )
        rec_speaker_only = _create_recording(
            title="Speaker Only", speaker="Shaykh Ahmad"
        )
        rec_neither = _create_recording(
            title="Neither", speaker="Mufti Bilal"
        )

        response = self.client.get(
            self.url, {"tag": self.tag.slug, "speaker": "Shaykh Ahmad"}
        )
        recordings = list(response.context["recordings"])
        recording_ids = {r.pk for r in recordings}
        self.assertEqual(len(recordings), 1)
        self.assertIn(rec_match.pk, recording_ids)
        self.assertNotIn(rec_tag_only.pk, recording_ids)
        self.assertNotIn(rec_speaker_only.pk, recording_ids)
        self.assertNotIn(rec_neither.pk, recording_ids)

    def test_combined_filter_no_matches(self):
        """Both filters active but nothing matches the intersection."""
        tag2 = Tag.objects.create(name="Seerah")
        _create_recording(title="A", speaker="Shaykh Ahmad", tags=[self.tag])
        _create_recording(title="B", speaker="Mufti Bilal", tags=[tag2])

        response = self.client.get(
            self.url, {"tag": tag2.slug, "speaker": "Shaykh Ahmad"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 0)

    def test_combined_filter_with_pagination(self):
        """Combined filters should still paginate correctly."""
        for i in range(12):
            _create_recording(
                title=f"Rec {i}",
                speaker="Shaykh Ahmad",
                recording_date=date.today() - timedelta(days=i),
                tags=[self.tag],
            )
        # Extra recordings that should NOT appear
        _create_recording(title="Other Speaker", speaker="Mufti Bilal", tags=[self.tag])
        _create_recording(title="No Tag", speaker="Shaykh Ahmad")

        response = self.client.get(
            self.url, {"tag": self.tag.slug, "speaker": "Shaykh Ahmad"}
        )
        self.assertEqual(len(response.context["recordings"]), 10)

        response_p2 = self.client.get(
            self.url,
            {"tag": self.tag.slug, "speaker": "Shaykh Ahmad", "page": 2},
        )
        self.assertEqual(len(response_p2.context["recordings"]), 2)

    def test_combined_filter_preserves_ordering(self):
        """Combined-filter results are still newest-first."""
        r_old = _create_recording(
            title="Old", speaker="Shaykh Ahmad", tags=[self.tag]
        )
        r_new = _create_recording(
            title="New", speaker="Shaykh Ahmad", tags=[self.tag]
        )
        response = self.client.get(
            self.url, {"tag": self.tag.slug, "speaker": "Shaykh Ahmad"}
        )
        recordings = list(response.context["recordings"])
        self.assertEqual(recordings[0], r_new)
        self.assertEqual(recordings[1], r_old)
