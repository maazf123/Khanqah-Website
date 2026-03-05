import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from apps.recordings.models import Recording
from apps.tags.models import Tag


class RecordingSearchViewTestCase(TestCase):
    """Base class that sets up common test data for search view tests."""

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("recording-search")

        # Create tags
        cls.tag_fiqh = Tag.objects.create(name="Fiqh")
        cls.tag_tafsir = Tag.objects.create(name="Tafsir")
        cls.tag_seerah = Tag.objects.create(name="Seerah")

        # Dummy audio file for all recordings
        cls.audio = SimpleUploadedFile(
            "test.mp3", b"fake-audio-content", content_type="audio/mpeg"
        )

        # Recording 1: Friday Bayan by Shaykh Ahmad, tagged Fiqh
        cls.rec_friday = Recording.objects.create(
            title="Friday Bayan",
            description="A talk about patience and gratitude",
            speaker="Shaykh Ahmad",
            audio_file=SimpleUploadedFile(
                "friday.mp3", b"audio", content_type="audio/mpeg"
            ),
            recording_date=datetime.date(2025, 1, 10),
        )
        cls.rec_friday.tags.add(cls.tag_fiqh)

        # Recording 2: Monday Lecture by Mufti Bilal, tagged Tafsir
        cls.rec_monday = Recording.objects.create(
            title="Monday Lecture",
            description="Explanation of Surah Al-Fatiha",
            speaker="Mufti Bilal",
            audio_file=SimpleUploadedFile(
                "monday.mp3", b"audio", content_type="audio/mpeg"
            ),
            recording_date=datetime.date(2025, 2, 15),
        )
        cls.rec_monday.tags.add(cls.tag_tafsir)

        # Recording 3: Evening Lecture by Shaykh Ahmad, tagged Fiqh + Seerah
        cls.rec_evening = Recording.objects.create(
            title="Evening Lecture",
            description="Discussion on Seerah and early history",
            speaker="Shaykh Ahmad",
            audio_file=SimpleUploadedFile(
                "evening.mp3", b"audio", content_type="audio/mpeg"
            ),
            recording_date=datetime.date(2025, 3, 20),
        )
        cls.rec_evening.tags.add(cls.tag_fiqh, cls.tag_seerah)

    def setUp(self):
        self.client = Client()


# ── 1-2: Basic page access ──────────────────────────────────────────────────


class TestSearchPageBasic(RecordingSearchViewTestCase):
    """Tests 1-2: GET /search/ returns 200 and uses the correct template."""

    def test_search_page_returns_200(self):
        """Test 1: GET /search/ returns HTTP 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_search_page_uses_correct_template(self):
        """Test 2: Uses recordings/recording_search.html template."""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "recordings/recording_search.html")


# ── 3-4: No query / empty query ─────────────────────────────────────────────


class TestSearchNoQuery(RecordingSearchViewTestCase):
    """Tests 3-4: No query parameter or empty query shows no results."""

    def test_no_query_param_shows_no_results(self):
        """Test 3: No ?q param — page loads but no results."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 0)

    def test_empty_query_param_shows_no_results(self):
        """Test 4: Empty ?q= — page loads but no results."""
        response = self.client.get(self.url, {"q": ""})
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 0)


# ── 5-7: Search by title ────────────────────────────────────────────────────


class TestSearchByTitle(RecordingSearchViewTestCase):
    """Tests 5-7: Search matches against recording title."""

    def test_search_title_case_insensitive(self):
        """Test 5: ?q=friday matches 'Friday Bayan' (case-insensitive)."""
        response = self.client.get(self.url, {"q": "friday"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)

    def test_search_title_does_not_match_unrelated(self):
        """Test 6: ?q=friday does NOT match 'Monday Lecture'."""
        response = self.client.get(self.url, {"q": "friday"})
        recordings = list(response.context["recordings"])
        self.assertNotIn(self.rec_monday, recordings)

    def test_search_title_partial_match(self):
        """Test 7: Partial match ?q=fri matches 'Friday Bayan'."""
        response = self.client.get(self.url, {"q": "fri"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)


# ── 8-9: Search by description ──────────────────────────────────────────────


class TestSearchByDescription(RecordingSearchViewTestCase):
    """Tests 8-9: Search matches against recording description."""

    def test_search_description_match(self):
        """Test 8: ?q=patience matches recording with 'patience' in description."""
        response = self.client.get(self.url, {"q": "patience"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)

    def test_search_description_partial_match(self):
        """Test 9: Partial match on description works (?q=patie)."""
        response = self.client.get(self.url, {"q": "patie"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)


# ── 10-11: Search by speaker ────────────────────────────────────────────────


class TestSearchBySpeaker(RecordingSearchViewTestCase):
    """Tests 10-11: Search matches against recording speaker."""

    def test_search_speaker_match(self):
        """Test 10: ?q=ahmad matches recording with speaker 'Shaykh Ahmad'."""
        response = self.client.get(self.url, {"q": "ahmad"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)

    def test_search_speaker_partial_match(self):
        """Test 11: Partial match on speaker works (?q=ahm)."""
        response = self.client.get(self.url, {"q": "ahm"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)


# ── 12-13: Cross-field search ───────────────────────────────────────────────


class TestSearchCrossField(RecordingSearchViewTestCase):
    """Tests 12-13: Search spans across title, description, and speaker."""

    def test_query_matches_different_fields_on_different_recordings(self):
        """Test 12: A query matching title of one recording and speaker of
        another returns both. 'ahmad' matches speaker of rec_friday and
        rec_evening."""
        response = self.client.get(self.url, {"q": "ahmad"})
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_friday, recordings)
        self.assertIn(self.rec_evening, recordings)
        # 'Monday Lecture' speaker is 'Mufti Bilal', should not appear
        self.assertNotIn(self.rec_monday, recordings)

    def test_query_matching_title_and_description_no_duplicates(self):
        """Test 13: A query matching title AND description of the same
        recording returns it once (no duplicates). 'lecture' appears in title
        of rec_monday ('Monday Lecture') and rec_evening ('Evening Lecture').
        We check no duplicates."""
        response = self.client.get(self.url, {"q": "lecture"})
        recordings = list(response.context["recordings"])
        # Count occurrences — each recording should appear exactly once
        self.assertEqual(recordings.count(self.rec_monday), 1)
        self.assertEqual(recordings.count(self.rec_evening), 1)

    def test_cross_field_title_and_speaker(self):
        """Additional cross-field: 'Bayan' is only in Friday's title,
        'Bilal' is only in Monday's speaker — query 'Bayan' should only
        return Friday, query 'Bilal' should only return Monday."""
        resp_bayan = self.client.get(self.url, {"q": "Bayan"})
        self.assertIn(self.rec_friday, list(resp_bayan.context["recordings"]))
        self.assertNotIn(self.rec_monday, list(resp_bayan.context["recordings"]))

        resp_bilal = self.client.get(self.url, {"q": "Bilal"})
        self.assertIn(self.rec_monday, list(resp_bilal.context["recordings"]))
        self.assertNotIn(self.rec_friday, list(resp_bilal.context["recordings"]))


# ── 14-15: Combined search + tag filter ─────────────────────────────────────


class TestSearchWithTagFilter(RecordingSearchViewTestCase):
    """Tests 14-15: Search combined with tag filtering."""

    def test_search_with_tag_filter(self):
        """Test 14: ?q=lecture&tag=fiqh returns only recordings matching
        search AND having the fiqh tag. 'lecture' matches Monday Lecture
        (tagged tafsir) and Evening Lecture (tagged fiqh+seerah). Only
        Evening Lecture has fiqh tag."""
        response = self.client.get(
            self.url, {"q": "lecture", "tag": self.tag_fiqh.slug}
        )
        recordings = list(response.context["recordings"])
        self.assertIn(self.rec_evening, recordings)
        self.assertNotIn(self.rec_monday, recordings)

    def test_tag_filter_without_search_shows_no_results(self):
        """Test 15: Tag filter with no search query shows no results
        (search requires a query)."""
        response = self.client.get(self.url, {"tag": self.tag_fiqh.slug})
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 0)


# ── 16: No results ──────────────────────────────────────────────────────────


class TestSearchNoResults(RecordingSearchViewTestCase):
    """Test 16: Non-matching query returns 200 with empty results."""

    def test_nonexistent_query_returns_empty(self):
        """Test 16: ?q=xyznonexistent returns 200 with empty results."""
        response = self.client.get(self.url, {"q": "xyznonexistent"})
        self.assertEqual(response.status_code, 200)
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 0)


# ── 17-18: Pagination ───────────────────────────────────────────────────────


class TestSearchPagination(TestCase):
    """Tests 17-18: Search results paginate at 10 per page."""

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("recording-search")

        # Create 15 recordings with "Lecture" in the title
        for i in range(15):
            Recording.objects.create(
                title=f"Lecture Part {i + 1:02d}",
                description="A detailed lecture",
                speaker="Shaykh Test",
                audio_file=SimpleUploadedFile(
                    f"lecture_{i}.mp3", b"audio", content_type="audio/mpeg"
                ),
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
            )

    def setUp(self):
        self.client = Client()

    def test_pagination_first_page_has_10(self):
        """Test 17: First page of search results has at most 10 items."""
        response = self.client.get(self.url, {"q": "lecture"})
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 10)

    def test_pagination_second_page_works(self):
        """Test 18: ?q=lecture&page=2 returns remaining results."""
        response = self.client.get(self.url, {"q": "lecture", "page": 2})
        self.assertEqual(response.status_code, 200)
        recordings = response.context["recordings"]
        self.assertEqual(len(recordings), 5)

    def test_paginator_total_count(self):
        """Verify the paginator reports the correct total count."""
        response = self.client.get(self.url, {"q": "lecture"})
        paginator = response.context["paginator"]
        self.assertEqual(paginator.count, 15)
        self.assertEqual(paginator.num_pages, 2)


# ── 19-21: Context variables ────────────────────────────────────────────────


class TestSearchContext(RecordingSearchViewTestCase):
    """Tests 19-21: Context includes correct query, tags, and current_tag."""

    def test_context_query_matches_q_param(self):
        """Test 19: 'query' in context matches the ?q param."""
        response = self.client.get(self.url, {"q": "friday"})
        self.assertEqual(response.context["query"], "friday")

    def test_context_query_empty_when_no_param(self):
        """'query' in context is empty string or absent when no ?q."""
        response = self.client.get(self.url)
        query = response.context.get("query", "")
        self.assertEqual(query, "")

    def test_context_tags_contains_all_tags(self):
        """Test 20: 'tags' in context contains all Tag objects."""
        response = self.client.get(self.url, {"q": "friday"})
        context_tags = list(response.context["tags"])
        self.assertIn(self.tag_fiqh, context_tags)
        self.assertIn(self.tag_tafsir, context_tags)
        self.assertIn(self.tag_seerah, context_tags)
        self.assertEqual(len(context_tags), 3)

    def test_context_tags_present_without_query(self):
        """Tags should be in context even without a search query."""
        response = self.client.get(self.url)
        context_tags = list(response.context["tags"])
        self.assertEqual(len(context_tags), 3)

    def test_context_current_tag_matches_tag_param(self):
        """Test 21: 'current_tag' in context matches the ?tag param."""
        response = self.client.get(
            self.url, {"q": "lecture", "tag": self.tag_fiqh.slug}
        )
        self.assertEqual(response.context["current_tag"], self.tag_fiqh.slug)

    def test_context_current_tag_empty_when_no_tag_param(self):
        """'current_tag' is empty string or absent when no ?tag param."""
        response = self.client.get(self.url, {"q": "lecture"})
        current_tag = response.context.get("current_tag")
        self.assertIsNone(current_tag)


# ── 22: Ordering ────────────────────────────────────────────────────────────


class TestSearchOrdering(TestCase):
    """Test 22: Search results are ordered newest first (by uploaded_at desc)."""

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("recording-search")

        # Create recordings in a specific order; uploaded_at is auto_now_add
        # so we create them sequentially — the last created is newest.
        cls.rec_old = Recording.objects.create(
            title="Lecture Old",
            description="Old lecture",
            speaker="Speaker A",
            audio_file=SimpleUploadedFile(
                "old.mp3", b"audio", content_type="audio/mpeg"
            ),
            recording_date=datetime.date(2024, 1, 1),
        )
        cls.rec_mid = Recording.objects.create(
            title="Lecture Mid",
            description="Mid lecture",
            speaker="Speaker B",
            audio_file=SimpleUploadedFile(
                "mid.mp3", b"audio", content_type="audio/mpeg"
            ),
            recording_date=datetime.date(2024, 6, 1),
        )
        cls.rec_new = Recording.objects.create(
            title="Lecture New",
            description="New lecture",
            speaker="Speaker C",
            audio_file=SimpleUploadedFile(
                "new.mp3", b"audio", content_type="audio/mpeg"
            ),
            recording_date=datetime.date(2025, 1, 1),
        )

    def setUp(self):
        self.client = Client()

    def test_results_ordered_newest_first(self):
        """Test 22: Results come back ordered by uploaded_at descending."""
        response = self.client.get(self.url, {"q": "lecture"})
        recordings = list(response.context["recordings"])
        self.assertEqual(len(recordings), 3)
        # Newest (last created) should be first
        self.assertEqual(recordings[0], self.rec_new)
        self.assertEqual(recordings[1], self.rec_mid)
        self.assertEqual(recordings[2], self.rec_old)
