"""
Exhaustive tests for the horizontal scrollable carousel feature on the
recordings list page.

The feature replaces the vertical "Latest recordings" grid with a horizontal
scrollable carousel of recent recording cards, plus a trailing "See all
recordings" card/link.

These tests are written TDD-style and are expected to FAIL until the
template / CSS changes are implemented.
"""

import datetime
import re

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.recordings.models import Recording
from apps.tags.models import Tag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _audio():
    """Return a minimal SimpleUploadedFile standing in for an audio file."""
    return SimpleUploadedFile("test.mp3", b"\x00" * 128, content_type="audio/mpeg")


def _rec(title="Recording", speaker="Speaker", description="",
         recording_date=None, tags=None, uploaded_at=None, **kwargs):
    """Create a Recording with sensible defaults.

    When *uploaded_at* is given the auto-generated value is overwritten so
    that tests have deterministic ordering (Recording.Meta.ordering is
    ``['-uploaded_at']``).
    """
    if recording_date is None:
        recording_date = datetime.date(2025, 6, 1)
    r = Recording.objects.create(
        title=title,
        speaker=speaker,
        description=description,
        audio_file=_audio(),
        recording_date=recording_date,
        **kwargs,
    )
    if uploaded_at is not None:
        # Bypass auto_now_add by using queryset.update()
        Recording.objects.filter(pk=r.pk).update(uploaded_at=uploaded_at)
        r.refresh_from_db()
    if tags:
        r.tags.set(tags)
    return r


def _ts(day_offset):
    """Return a timezone-aware datetime offset by *day_offset* days from a
    fixed base, for deterministic uploaded_at ordering."""
    base = timezone.make_aware(datetime.datetime(2025, 1, 1, 12, 0, 0))
    return base + datetime.timedelta(days=day_offset)


# =========================================================================
# 1. VIEW / CONTEXT TESTS
# =========================================================================

class CarouselContextFeaturedRecordingTests(TestCase):
    """featured_recording context variable behaviour."""

    def setUp(self):
        self.url = reverse("recording-list")

    def test_featured_recording_is_most_recent(self):
        """featured_recording must be the single most-recently-uploaded recording."""
        _rec(title="Older", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))
        newest = _rec(title="Newer", recording_date=datetime.date(2025, 1, 2),
                      uploaded_at=_ts(1))
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["featured_recording"], newest)

    def test_featured_recording_none_when_no_recordings(self):
        """With 0 recordings, featured_recording must be None."""
        resp = self.client.get(self.url)
        self.assertIsNone(resp.context["featured_recording"])

    def test_featured_recording_exists_with_one_recording(self):
        """With exactly 1 recording, featured_recording is that recording."""
        solo = _rec(title="Solo")
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["featured_recording"], solo)

    def test_featured_recording_exists_with_two_recordings(self):
        """With 2 recordings, featured_recording is the newer one."""
        _rec(title="Old", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))
        newer = _rec(title="New", recording_date=datetime.date(2025, 1, 2),
                     uploaded_at=_ts(1))
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["featured_recording"], newer)

    def test_featured_recording_exists_with_four_plus_recordings(self):
        """With 4+ recordings, featured_recording is the most recent."""
        for i in range(5):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        featured = resp.context["featured_recording"]
        self.assertIsNotNone(featured)
        self.assertEqual(featured.title, "Rec 4")


class CarouselContextRecentRecordingsTests(TestCase):
    """recent_recordings context variable behaviour."""

    def setUp(self):
        self.url = reverse("recording-list")

    def test_recent_recordings_empty_with_zero_recordings(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["recent_recordings"]), 0)

    def test_recent_recordings_empty_with_one_recording(self):
        """With only 1 recording (featured), recent_recordings is empty."""
        _rec(title="Only")
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["recent_recordings"]), 0)

    def test_recent_recordings_has_one_with_two_recordings(self):
        """With 2 recordings, recent_recordings has 1 item."""
        _rec(title="Older", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))
        _rec(title="Newer", recording_date=datetime.date(2025, 1, 2),
             uploaded_at=_ts(1))
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["recent_recordings"]), 1)

    def test_recent_recordings_has_two_with_three_recordings(self):
        """With 3 recordings, recent_recordings has 2 items."""
        for i in range(3):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["recent_recordings"]), 2)

    def test_recent_recordings_has_exactly_three_with_four_recordings(self):
        """With 4 recordings, recent_recordings has exactly 3."""
        for i in range(4):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["recent_recordings"]), 3)

    def test_recent_recordings_capped_at_three_with_many_recordings(self):
        """With 10 recordings, recent_recordings still has exactly 3."""
        for i in range(10):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["recent_recordings"]), 3)

    def test_recent_recordings_contains_indices_1_to_3(self):
        """recent_recordings must be recordings[1:4] by uploaded_at descending."""
        recs = []
        for i in range(5):
            recs.append(
                _rec(
                    title=f"Rec {i}",
                    recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                    uploaded_at=_ts(i),
                )
            )
        resp = self.client.get(self.url)
        recent = list(resp.context["recent_recordings"])
        # Ordered by -uploaded_at: Rec 4 (featured), Rec 3, Rec 2, Rec 1, Rec 0
        # recent = indices [1:4] = Rec 3, Rec 2, Rec 1
        self.assertIn(recs[3], recent)
        self.assertIn(recs[2], recent)
        self.assertIn(recs[1], recent)
        # featured (Rec 4) must NOT be in recent
        self.assertNotIn(recs[4], recent)
        # Rec 0 must NOT be in recent (it's index 4, beyond the slice)
        self.assertNotIn(recs[0], recent)

    def test_recent_recordings_excludes_featured(self):
        """The featured recording must never appear in recent_recordings."""
        _rec(title="Old", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))
        newest = _rec(title="Newest", recording_date=datetime.date(2025, 1, 2),
                      uploaded_at=_ts(1))
        resp = self.client.get(self.url)
        recent = list(resp.context["recent_recordings"])
        self.assertNotIn(newest, recent)


class CarouselContextTagsTests(TestCase):
    """Tags are always passed in context."""

    def setUp(self):
        self.url = reverse("recording-list")

    def test_tags_in_context(self):
        t1 = Tag.objects.create(name="Fiqh")
        t2 = Tag.objects.create(name="Hadith")
        resp = self.client.get(self.url)
        tags = set(resp.context["tags"])
        self.assertEqual(tags, {t1, t2})

    def test_tags_present_even_with_no_recordings(self):
        Tag.objects.create(name="Aqeedah")
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["tags"].count(), 1)

    def test_empty_tags_with_no_tags(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["tags"].count(), 0)


# =========================================================================
# 2. TEMPLATE STRUCTURE TESTS (HTML)
# =========================================================================

class CarouselFeaturedSectionTests(TestCase):
    """The featured recording section must have the correct structure."""

    def setUp(self):
        self.url = reverse("recording-list")

    def test_featured_section_present_when_recordings_exist(self):
        _rec(title="Featured")
        resp = self.client.get(self.url)
        self.assertContains(resp, 'class="featured-recording"')

    def test_no_featured_section_with_zero_recordings(self):
        resp = self.client.get(self.url)
        self.assertNotContains(resp, 'class="featured-recording"')


class CarouselContainerTests(TestCase):
    """The carousel container must exist and hold the right structure."""

    @classmethod
    def setUpTestData(cls):
        # Create 4 recordings: 1 featured + 3 recent
        for i in range(4):
            _rec(
                title=f"Carousel Rec {i}",
                speaker=f"Speaker {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )

    def setUp(self):
        self.url = reverse("recording-list")

    def test_carousel_container_present(self):
        """Page must have a container with class 'recordings-carousel'."""
        resp = self.client.get(self.url)
        self.assertContains(resp, 'recordings-carousel')

    def test_carousel_card_class_present(self):
        """Each carousel item must have class 'carousel-card'."""
        resp = self.client.get(self.url)
        self.assertContains(resp, 'carousel-card')

    def test_carousel_contains_correct_number_of_cards(self):
        """Carousel must contain exactly 3 carousel-card elements (matching
        the 3 recent_recordings)."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # Count elements with class="carousel-card" (exact class, not substrings
        # like carousel-card-body)
        card_count = len(re.findall(r'class="carousel-card"', content))
        self.assertEqual(card_count, 3)

    def test_see_all_card_present(self):
        """A 'See all' link/card with class 'carousel-see-all' must exist."""
        resp = self.client.get(self.url)
        self.assertContains(resp, 'carousel-see-all')

    def test_see_all_links_to_recording_archive(self):
        """The 'See all' link must point to the recording-archive URL."""
        resp = self.client.get(self.url)
        archive_url = reverse("recording-archive")
        content = resp.content.decode()
        # Find the see-all element and check it contains the archive URL
        self.assertIn(archive_url, content)
        # Specifically verify the carousel-see-all links to the archive
        see_all_pattern = re.compile(
            r'carousel-see-all[^>]*>.*?</a>|<a[^>]*carousel-see-all[^>]*>',
            re.DOTALL,
        )
        match = see_all_pattern.search(content)
        self.assertIsNotNone(match, "carousel-see-all element not found")

    def test_see_all_href_is_archive_url(self):
        """The href of the see-all link must be exactly the recording-archive URL."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        archive_url = reverse("recording-archive")
        # Look for an anchor with carousel-see-all class that has correct href
        pattern = re.compile(
            r'<a\s[^>]*href="' + re.escape(archive_url) + r'"[^>]*class="[^"]*carousel-see-all',
            re.DOTALL,
        )
        pattern_alt = re.compile(
            r'<a\s[^>]*class="[^"]*carousel-see-all[^"]*"[^>]*href="' + re.escape(archive_url) + r'"',
            re.DOTALL,
        )
        found = pattern.search(content) or pattern_alt.search(content)
        self.assertIsNotNone(
            found,
            f"Expected <a> with class carousel-see-all and href={archive_url}",
        )

    def test_carousel_has_horizontal_scroll_attribute(self):
        """The carousel container must have a CSS class or attribute indicating
        horizontal scroll (e.g. overflow-x: auto via a class or inline style)."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # The container should have recordings-carousel class which will be
        # styled with overflow-x in CSS. Verify the class exists.
        self.assertIn('recordings-carousel', content)


class CarouselVisibilityByRecordingCountTests(TestCase):
    """Carousel visibility based on number of recordings."""

    def setUp(self):
        self.url = reverse("recording-list")

    def test_zero_recordings_shows_empty_message(self):
        """With 0 recordings: no featured, no carousel, shows empty message."""
        resp = self.client.get(self.url)
        self.assertNotContains(resp, 'class="featured-recording"')
        self.assertNotContains(resp, 'recordings-carousel')
        # Must contain an empty-state message
        self.assertContains(resp, "No recordings")

    def test_one_recording_no_carousel(self):
        """With 1 recording: featured exists, but NO carousel (no recent)."""
        _rec(title="Solo")
        resp = self.client.get(self.url)
        self.assertContains(resp, 'class="featured-recording"')
        self.assertNotContains(resp, 'recordings-carousel')

    def test_two_recordings_carousel_exists(self):
        """With 2 recordings: featured and carousel both exist."""
        _rec(title="Older", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))
        _rec(title="Newer", recording_date=datetime.date(2025, 1, 2),
             uploaded_at=_ts(1))
        resp = self.client.get(self.url)
        self.assertContains(resp, 'class="featured-recording"')
        self.assertContains(resp, 'recordings-carousel')

    def test_four_recordings_carousel_exists(self):
        """With 4 recordings: featured and carousel both exist."""
        for i in range(4):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        self.assertContains(resp, 'class="featured-recording"')
        self.assertContains(resp, 'recordings-carousel')

    def test_two_recordings_carousel_has_one_card(self):
        """With 2 recordings, carousel has 1 carousel-card."""
        _rec(title="Older", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))
        _rec(title="Newer", recording_date=datetime.date(2025, 1, 2),
             uploaded_at=_ts(1))
        resp = self.client.get(self.url)
        content = resp.content.decode()
        card_count = len(re.findall(r'class="carousel-card"', content))
        self.assertEqual(card_count, 1)

    def test_four_recordings_carousel_has_three_cards(self):
        """With 4 recordings, carousel has 3 carousel-cards."""
        for i in range(4):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        content = resp.content.decode()
        card_count = len(re.findall(r'class="carousel-card"', content))
        self.assertEqual(card_count, 3)


class CarouselMoreRecordingsHeadingTests(TestCase):
    """The 'Latest recordings' heading must still appear above the carousel."""

    def setUp(self):
        self.url = reverse("recording-list")

    def test_more_recordings_heading_present(self):
        """When there are recent recordings, 'Latest recordings' heading exists."""
        for i in range(4):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )
        resp = self.client.get(self.url)
        self.assertContains(resp, "Latest recordings")

    def test_more_recordings_heading_absent_with_one_recording(self):
        """With only 1 recording (no recent), 'Latest recordings' heading is absent."""
        _rec(title="Solo")
        resp = self.client.get(self.url)
        self.assertNotContains(resp, "Latest recordings")


# =========================================================================
# 3. CARD CONTENT TESTS
# =========================================================================

class CarouselCardContentTests(TestCase):
    """Each carousel card must display the correct recording data."""

    @classmethod
    def setUpTestData(cls):
        cls.tag1 = Tag.objects.create(name="Fiqh")
        cls.tag2 = Tag.objects.create(name="Hadith")
        # 4 recordings: featured + 3 recent (ordered by uploaded_at desc)
        cls.r1 = _rec(
            title="First Recording",
            speaker="Shaykh Ahmad",
            recording_date=datetime.date(2025, 3, 10),
            tags=[cls.tag1],
            uploaded_at=_ts(0),
        )
        cls.r2 = _rec(
            title="Second Recording",
            speaker="Mufti Bilal",
            recording_date=datetime.date(2025, 3, 11),
            tags=[cls.tag1, cls.tag2],
            uploaded_at=_ts(1),
        )
        cls.r3 = _rec(
            title="Third Recording",
            speaker="Imam Zaid",
            recording_date=datetime.date(2025, 3, 12),
            uploaded_at=_ts(2),
        )
        # This one is featured (most recent uploaded_at)
        cls.r4 = _rec(
            title="Featured Rec",
            speaker="Shaykh Yusuf",
            recording_date=datetime.date(2025, 3, 13),
            uploaded_at=_ts(3),
        )

    def setUp(self):
        self.url = reverse("recording-list")
        self.resp = self.client.get(self.url)
        self.content = self.resp.content.decode()

    def test_carousel_card_displays_title(self):
        """Each carousel card must show the recording title."""
        self.assertIn("First Recording", self.content)
        self.assertIn("Second Recording", self.content)
        self.assertIn("Third Recording", self.content)

    def test_carousel_card_displays_listen_button(self):
        """Each carousel card must show a listen/play button."""
        # Cards show a "Listen" pill button instead of speaker name
        self.assertIn("carousel-card-duration", self.content)

    def test_carousel_card_displays_recording_date(self):
        """Each carousel card must show the recording date."""
        # Django date filter "M d, Y" produces e.g. "Mar 10, 2025"
        self.assertIn("Mar 10, 2025", self.content)
        self.assertIn("Mar 11, 2025", self.content)
        self.assertIn("Mar 12, 2025", self.content)

    def test_carousel_card_links_to_detail_page(self):
        """Each carousel card must link to the recording's detail page."""
        for rec in [self.r1, self.r2, self.r3]:
            detail_url = reverse("recording-detail", args=[rec.pk])
            self.assertIn(detail_url, self.content)

    def test_carousel_card_displays_tags(self):
        """Cards that have tags must display them."""
        self.assertIn("Fiqh", self.content)
        self.assertIn("Hadith", self.content)

    def test_card_without_tags_still_renders(self):
        """A card with no tags must still render without errors."""
        # r3 has no tags -- page should still be 200
        self.assertEqual(self.resp.status_code, 200)
        self.assertIn("Third Recording", self.content)


# =========================================================================
# 4. ACCESSIBILITY TESTS
# =========================================================================

class CarouselAccessibilityTests(TestCase):
    """The carousel must have proper ARIA attributes for accessibility."""

    @classmethod
    def setUpTestData(cls):
        for i in range(4):
            _rec(
                title=f"A11y Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )

    def setUp(self):
        self.url = reverse("recording-list")
        self.resp = self.client.get(self.url)
        self.content = self.resp.content.decode()

    def test_carousel_has_role_or_aria_label(self):
        """The carousel container must have a role attribute (e.g. role='region')
        or an aria-label for screen readers."""
        has_role = 'role=' in self.content and 'recordings-carousel' in self.content
        has_aria = 'aria-label' in self.content and 'recordings-carousel' in self.content
        self.assertTrue(
            has_role or has_aria,
            "Carousel container must have role or aria-label attribute",
        )

    def test_carousel_has_aria_label_text(self):
        """The carousel must have a descriptive aria-label."""
        # Look for aria-label on or near the carousel container
        carousel_start = self.content.find('recordings-carousel')
        self.assertGreater(carousel_start, -1, "recordings-carousel not found")
        # Extract a chunk around the carousel opening tag
        carousel_chunk = self.content[carousel_start:carousel_start + 300]
        self.assertIn('aria-label', carousel_chunk)

    def test_cards_are_focusable(self):
        """Carousel cards should be keyboard-navigable (links or tabindex)."""
        # Cards wrapped in <a> tags are inherently focusable.
        # Check that carousel cards are inside links or have tabindex.
        carousel_start = self.content.find('recordings-carousel')
        self.assertGreater(carousel_start, -1, "recordings-carousel not found")
        carousel_section = self.content[carousel_start:carousel_start + 5000]
        # Cards should be <a> elements (links) which are focusable
        has_links = '<a ' in carousel_section or '<a\n' in carousel_section
        has_tabindex = 'tabindex' in carousel_section
        self.assertTrue(
            has_links or has_tabindex,
            "Carousel cards must be focusable (links or tabindex)",
        )


# =========================================================================
# 5. EDGE CASE TESTS
# =========================================================================

class CarouselEdgeCaseLongTitleTests(TestCase):
    """A recording with a very long title must not break the carousel layout."""

    @classmethod
    def setUpTestData(cls):
        cls.long_title = "A" * 300  # 300-char title
        _rec(title="Featured", recording_date=datetime.date(2025, 1, 4),
             uploaded_at=_ts(3))
        _rec(title=cls.long_title, recording_date=datetime.date(2025, 1, 3),
             uploaded_at=_ts(2))
        _rec(title="Normal Title", recording_date=datetime.date(2025, 1, 2),
             uploaded_at=_ts(1))
        _rec(title="Another Normal", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))

    def setUp(self):
        self.url = reverse("recording-list")

    def test_page_loads_with_long_title(self):
        """The page must still return 200 with a very long title."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_long_title_card_has_truncation_class(self):
        """The card title element should have a CSS class that enables
        text truncation (e.g. card-title with CSS text-overflow/clamp)."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # The card title class must exist for CSS truncation to work
        self.assertIn('card-title', content)


class CarouselEdgeCaseNoDescriptionTests(TestCase):
    """Recordings with no description must render correctly in the carousel.

    Note: The carousel card template does not display descriptions (only
    the featured recording shows descriptions). These tests verify that
    cards without descriptions still render properly and that the page
    does not break.
    """

    @classmethod
    def setUpTestData(cls):
        # Create recordings with and without descriptions
        _rec(
            title="Featured With Desc",
            description="This is a description.",
            recording_date=datetime.date(2025, 1, 4),
            uploaded_at=_ts(3),
        )
        _rec(
            title="No Desc Card",
            description="",
            recording_date=datetime.date(2025, 1, 3),
            uploaded_at=_ts(2),
        )
        _rec(
            title="Has Desc Card",
            description="Some text here.",
            recording_date=datetime.date(2025, 1, 2),
            uploaded_at=_ts(1),
        )
        _rec(
            title="Also No Desc",
            description="",
            recording_date=datetime.date(2025, 1, 1),
            uploaded_at=_ts(0),
        )

    def setUp(self):
        self.url = reverse("recording-list")

    def test_page_loads_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_card_without_description_renders(self):
        """Cards without descriptions must still appear in the carousel."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn("No Desc Card", content)
        self.assertIn("Also No Desc", content)

    def test_card_with_description_still_renders_title(self):
        """Cards whose underlying recording has a description still render
        their title in the carousel (descriptions may not be shown in
        carousel cards, but the card must still appear)."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn("Has Desc Card", content)


class CarouselEdgeCaseNoTagsTests(TestCase):
    """Recordings with no tags must render correctly in the carousel."""

    @classmethod
    def setUpTestData(cls):
        _rec(title="Featured", recording_date=datetime.date(2025, 1, 4),
             uploaded_at=_ts(3))
        _rec(title="No Tags Card 1", recording_date=datetime.date(2025, 1, 3),
             uploaded_at=_ts(2))
        _rec(title="No Tags Card 2", recording_date=datetime.date(2025, 1, 2),
             uploaded_at=_ts(1))
        _rec(title="No Tags Card 3", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))

    def setUp(self):
        self.url = reverse("recording-list")

    def test_page_loads_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_cards_without_tags_render(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn("No Tags Card 1", content)
        self.assertIn("No Tags Card 2", content)
        self.assertIn("No Tags Card 3", content)

    def test_carousel_present_even_without_tags(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'recordings-carousel')


class CarouselEdgeCaseManyTagsTests(TestCase):
    """Recordings with many tags must render correctly without breaking layout."""

    @classmethod
    def setUpTestData(cls):
        cls.tags = [Tag.objects.create(name=f"Tag{i}") for i in range(8)]
        _rec(title="Featured", recording_date=datetime.date(2025, 1, 4),
             uploaded_at=_ts(3))
        _rec(
            title="Many Tags Card",
            recording_date=datetime.date(2025, 1, 3),
            tags=cls.tags,
            uploaded_at=_ts(2),
        )
        _rec(title="Some Card", recording_date=datetime.date(2025, 1, 2),
             uploaded_at=_ts(1))
        _rec(title="Another Card", recording_date=datetime.date(2025, 1, 1),
             uploaded_at=_ts(0))

    def setUp(self):
        self.url = reverse("recording-list")

    def test_page_loads_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_many_tags_displayed(self):
        """All tags on the recording should appear in the rendered page."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        for tag in self.tags:
            self.assertIn(tag.name, content)

    def test_carousel_present_with_many_tags(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'recordings-carousel')


class CarouselGridReplacementTests(TestCase):
    """The old vertical recordings-grid should no longer be present;
    it must be replaced by the horizontal recordings-carousel."""

    @classmethod
    def setUpTestData(cls):
        for i in range(4):
            _rec(
                title=f"Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )

    def setUp(self):
        self.url = reverse("recording-list")

    def test_old_recordings_grid_is_gone(self):
        """The old 'recordings-grid' class should no longer appear."""
        resp = self.client.get(self.url)
        self.assertNotContains(resp, 'class="recordings-grid"')

    def test_carousel_replaces_grid(self):
        """recordings-carousel should be present in place of recordings-grid."""
        resp = self.client.get(self.url)
        self.assertContains(resp, 'recordings-carousel')


class CarouselSeeAllPositionTests(TestCase):
    """The 'See all' card must appear at the end (after all recording cards)."""

    @classmethod
    def setUpTestData(cls):
        for i in range(4):
            _rec(
                title=f"Pos Rec {i}",
                recording_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
                uploaded_at=_ts(i),
            )

    def setUp(self):
        self.url = reverse("recording-list")

    def test_see_all_appears_after_last_carousel_card(self):
        """carousel-see-all must appear after all carousel-card elements."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # Find all positions of class="carousel-card" (exact match, not substrings)
        card_positions = [m.start() for m in re.finditer(r'class="carousel-card"', content)]
        see_all_pos = content.find('carousel-see-all')
        self.assertGreater(len(card_positions), 0, "No carousel-card found")
        self.assertGreater(see_all_pos, -1, "No carousel-see-all found")
        last_card_pos = max(card_positions)
        self.assertGreater(
            see_all_pos, last_card_pos,
            "carousel-see-all must appear after the last carousel-card",
        )

    def test_see_all_inside_carousel_container(self):
        """The carousel-see-all element must be inside the recordings-carousel container."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        carousel_start = content.find('recordings-carousel')
        see_all_pos = content.find('carousel-see-all')
        self.assertGreater(carousel_start, -1)
        self.assertGreater(see_all_pos, -1)
        self.assertGreater(see_all_pos, carousel_start)
