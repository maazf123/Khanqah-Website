"""
Exhaustive tests for the recordings views.

RecordingListView (recording-list):
- Featured recording (most recent) + 3 recent recordings
- No pagination, no filtering
- Context: featured_recording, recent_recordings, tags

RecordingArchiveView (recording-archive):
- URL: /recordings/all/, name: recording-archive
- Paginated by 10
- Filters: ?tag=<slug>, ?speaker=<name>
- Context: recordings (page object), tags, current_tag, current_speaker
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


# ---------------------------------------------------------------------------
# List view tests (featured + recent, no pagination/filtering)
# ---------------------------------------------------------------------------

class RecordingListBasicTests(TestCase):
    """Basic page loading and template tests."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")

    def test_get_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "recordings/recording_list.html")

    def test_empty_state_returns_200(self):
        self.assertEqual(Recording.objects.count(), 0)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_context_contains_all_tags(self):
        t1 = Tag.objects.create(name="Fiqh")
        t2 = Tag.objects.create(name="Tafsir")
        t3 = Tag.objects.create(name="Hadith")
        response = self.client.get(self.url)
        tags_in_ctx = set(response.context["tags"])
        self.assertEqual(tags_in_ctx, {t1, t2, t3})

    def test_tags_in_context_even_when_no_recordings(self):
        Tag.objects.create(name="Aqeedah")
        response = self.client.get(self.url)
        self.assertEqual(response.context["tags"].count(), 1)


class RecordingListDisplayTests(TestCase):
    """Tests for how recordings appear in the list view context."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-list")

    def test_featured_recording_is_most_recent(self):
        _create_recording(title="Older Lecture")
        r2 = _create_recording(title="Newer Lecture")
        response = self.client.get(self.url)
        self.assertEqual(response.context["featured_recording"], r2)

    def test_recent_recordings_excludes_featured(self):
        r1 = _create_recording(title="Oldest")
        r2 = _create_recording(title="Middle")
        r3 = _create_recording(title="Newest")
        response = self.client.get(self.url)
        self.assertEqual(response.context["featured_recording"], r3)
        recent = list(response.context["recent_recordings"])
        self.assertIn(r2, recent)
        self.assertIn(r1, recent)
        self.assertNotIn(r3, recent)

    def test_recent_recordings_max_three(self):
        for i in range(6):
            _create_recording(title=f"Rec {i}")
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["recent_recordings"]), 3)

    def test_featured_recording_none_when_empty(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.context["featured_recording"])

    def test_recording_fields_accessible(self):
        tag = Tag.objects.create(name="Tasawwuf")
        _create_recording(
            title="Special Lecture",
            speaker="Shaykh Ahmad",
            recording_date=date(2025, 6, 15),
            tags=[tag],
        )
        response = self.client.get(self.url)
        recording = response.context["featured_recording"]
        self.assertEqual(recording.title, "Special Lecture")
        self.assertEqual(recording.speaker, "Shaykh Ahmad")
        self.assertEqual(recording.recording_date, date(2025, 6, 15))
        self.assertIn(tag, recording.tags.all())


# ---------------------------------------------------------------------------
# Archive view tests (pagination + filtering)
# ---------------------------------------------------------------------------

class RecordingArchivePaginationTests(TestCase):
    """Tests for pagination on the archive view (paginate_by=10)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-archive")

    def _create_n_recordings(self, n):
        recs = []
        for i in range(n):
            recs.append(
                _create_recording(
                    title=f"Recording {i}",
                    recording_date=date.today() - timedelta(days=i),
                )
            )
        return recs

    def test_first_page_has_at_most_10(self):
        self._create_n_recordings(12)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["recordings"]), 10)

    def test_15_recordings_split_across_pages(self):
        self._create_n_recordings(15)
        page1 = self.client.get(self.url)
        page2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(page1.context["recordings"]), 10)
        self.assertEqual(len(page2.context["recordings"]), 5)

    def test_page_2_query_param(self):
        self._create_n_recordings(15)
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)

    def test_invalid_page_number_returns_404(self):
        self._create_n_recordings(15)
        response = self.client.get(self.url, {"page": 999})
        self.assertEqual(response.status_code, 404)

    def test_non_numeric_page_returns_first_page_or_404(self):
        self._create_n_recordings(5)
        response = self.client.get(self.url, {"page": "abc"})
        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 200:
            page_obj = response.context["recordings"]
            self.assertEqual(page_obj.number, 1)

    def test_exactly_10_recordings_single_page(self):
        self._create_n_recordings(10)
        response = self.client.get(self.url)
        page_obj = response.context["page_obj"]
        self.assertFalse(page_obj.has_next())
        self.assertEqual(len(response.context["recordings"]), 10)

    def test_zero_recordings_pagination(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 0)


class RecordingArchiveTagFilterTests(TestCase):
    """Tests for the ?tag=<slug> query parameter on the archive view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-archive")
        self.tag_fiqh = Tag.objects.create(name="Fiqh")
        self.tag_hadith = Tag.objects.create(name="Hadith")

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

    def test_filter_by_nonexistent_tag_returns_empty(self):
        _create_recording(title="Something", tags=[self.tag_fiqh])
        response = self.client.get(self.url, {"tag": "nonexistent-slug"})
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 0)

    def test_tag_filter_paginates(self):
        for i in range(15):
            _create_recording(
                title=f"Fiqh Rec {i}",
                recording_date=date.today() - timedelta(days=i),
                tags=[self.tag_fiqh],
            )
        for i in range(5):
            _create_recording(title=f"Hadith Rec {i}", tags=[self.tag_hadith])

        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        self.assertEqual(len(response.context["recordings"]), 10)

        response_p2 = self.client.get(
            self.url, {"tag": self.tag_fiqh.slug, "page": 2}
        )
        self.assertEqual(len(response_p2.context["recordings"]), 5)

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
        r_old = _create_recording(title="Old Fiqh", tags=[self.tag_fiqh])
        r_new = _create_recording(title="New Fiqh", tags=[self.tag_fiqh])
        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        recordings = list(response.context["recordings"])
        self.assertEqual(recordings[0], r_new)
        self.assertEqual(recordings[1], r_old)

    def test_empty_tag_param_returns_all(self):
        _create_recording(title="Rec A", tags=[self.tag_fiqh])
        _create_recording(title="Rec B", tags=[self.tag_hadith])
        response = self.client.get(self.url, {"tag": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 2)

    def test_current_tag_in_context(self):
        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        self.assertEqual(response.context["current_tag"], self.tag_fiqh.slug)

    def test_current_tag_none_when_not_filtering(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.context["current_tag"])


class RecordingArchiveSpeakerFilterTests(TestCase):
    """Tests for the ?speaker=<name> query parameter on the archive view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-archive")

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

    def test_speaker_filter_no_matches(self):
        _create_recording(title="Lecture", speaker="Shaykh Ahmad")
        response = self.client.get(self.url, {"speaker": "Nonexistent Speaker"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 0)

    def test_speaker_filter_preserves_ordering(self):
        r_old = _create_recording(title="Old", speaker="Imam Zaid")
        r_new = _create_recording(title="New", speaker="Imam Zaid")
        response = self.client.get(self.url, {"speaker": "Imam Zaid"})
        recordings = list(response.context["recordings"])
        self.assertEqual(recordings[0], r_new)
        self.assertEqual(recordings[1], r_old)

    def test_speaker_filter_paginates(self):
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
        _create_recording(title="A", speaker="Speaker A")
        _create_recording(title="B", speaker="Speaker B")
        response = self.client.get(self.url, {"speaker": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 2)

    def test_current_speaker_in_context(self):
        response = self.client.get(self.url, {"speaker": "Shaykh Ahmad"})
        self.assertEqual(response.context["current_speaker"], "Shaykh Ahmad")


class RecordingArchiveCombinedFilterTests(TestCase):
    """Tests for combining ?tag=<slug>&speaker=<name> on the archive view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("recording-archive")
        self.tag = Tag.objects.create(name="Tazkiyah")

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
        tag2 = Tag.objects.create(name="Seerah")
        _create_recording(title="A", speaker="Shaykh Ahmad", tags=[self.tag])
        _create_recording(title="B", speaker="Mufti Bilal", tags=[tag2])

        response = self.client.get(
            self.url, {"tag": tag2.slug, "speaker": "Shaykh Ahmad"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recordings"]), 0)

    def test_combined_filter_with_pagination(self):
        for i in range(12):
            _create_recording(
                title=f"Rec {i}",
                speaker="Shaykh Ahmad",
                recording_date=date.today() - timedelta(days=i),
                tags=[self.tag],
            )
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
