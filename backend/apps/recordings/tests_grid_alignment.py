"""
Tests for recording grid alignment on the recordings list page.

These tests verify that the 3-column "More Recordings" grid renders
consistently aligned cards regardless of varying content (descriptions,
tags, admin actions). They test both the HTML structure and the CSS rules
that ensure proper alignment.
"""
import datetime
import os
import re

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.recordings.models import Recording
from apps.tags.models import Tag


def _audio():
    return SimpleUploadedFile("t.mp3", b"audio", content_type="audio/mpeg")


def _rec(title="Rec", speaker="Speaker", description="", date=None, tags=None):
    if date is None:
        date = datetime.date(2025, 6, 1)
    r = Recording.objects.create(
        title=title, speaker=speaker, description=description,
        audio_file=_audio(), recording_date=date,
    )
    if tags:
        r.tags.add(*tags)
    return r


# ---------------------------------------------------------------------------
# 1. HTML Structure Tests — verify the grid container and card elements
# ---------------------------------------------------------------------------

class GridContainerStructureTests(TestCase):
    """The .recordings-grid container must be present with correct children."""

    @classmethod
    def setUpTestData(cls):
        # 4 recordings: 1 featured + 3 recent
        for i in range(4):
            _rec(
                title=f"Rec {i}",
                date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
            )
        cls.url = reverse("recording-list")

    def test_recordings_grid_container_present(self):
        """The page must contain a div with class 'recordings-grid'."""
        resp = self.client.get(self.url)
        self.assertContains(resp, 'class="recordings-grid"')

    def test_grid_contains_exactly_3_card_links(self):
        """The grid must contain exactly 3 recording-card-link children."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        count = content.count('class="recording-card-link"')
        self.assertEqual(count, 3)

    def test_each_card_has_card_accent(self):
        """Each recording-card must have a .card-accent element."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        accent_count = content.count('class="card-accent"')
        self.assertEqual(accent_count, 3)

    def test_each_card_has_card_body(self):
        """Each recording-card must have a .card-body element."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        body_count = content.count('class="card-body"')
        self.assertEqual(body_count, 3)


class GridCardConsistencyMixedContentTests(TestCase):
    """Cards with varying content must still produce consistent HTML structure."""

    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name="TestTag")
        # rec1: no description, no tags
        cls.r1 = _rec(title="No Desc No Tags", date=datetime.date(2025, 1, 1))
        # rec2: has description, has tags
        cls.r2 = _rec(
            title="Has Desc Has Tags", description="Some description.",
            date=datetime.date(2025, 1, 2), tags=[cls.tag],
        )
        # rec3: no description, has tags
        cls.r3 = _rec(
            title="No Desc Has Tags", date=datetime.date(2025, 1, 3),
            tags=[cls.tag],
        )
        # rec4 (featured): has everything
        cls.r4 = _rec(
            title="Featured", description="Featured desc.",
            date=datetime.date(2025, 1, 4), tags=[cls.tag],
        )
        cls.url = reverse("recording-list")

    def test_all_3_recent_cards_rendered(self):
        """All 3 recent cards appear regardless of content mix."""
        resp = self.client.get(self.url)
        self.assertContains(resp, "No Desc No Tags")
        self.assertContains(resp, "Has Desc Has Tags")
        self.assertContains(resp, "No Desc Has Tags")

    def test_card_without_description_has_no_card_description_element(self):
        """Cards without description should not contain card-description class."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # Find the grid section
        grid_start = content.find('class="recordings-grid"')
        grid_section = content[grid_start:]
        # Count card-description occurrences (should be 1 — only r2 has desc)
        desc_count = grid_section.count('class="card-description"')
        self.assertEqual(desc_count, 1)

    def test_card_with_tags_shows_card_tags(self):
        """Cards with tags should display .card-tags section."""
        resp = self.client.get(self.url)
        self.assertContains(resp, "TestTag")

    def test_grid_still_has_3_cards_with_mixed_content(self):
        """Grid always has exactly 3 cards regardless of content variations."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        count = content.count('class="recording-card-link"')
        self.assertEqual(count, 3)


class GridWithAdminActionsTests(TestCase):
    """Cards viewed by staff include admin actions — grid must stay aligned."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            "staff", "s@test.com", "pass", is_staff=True,
        )
        for i in range(4):
            _rec(
                title=f"Admin Rec {i}",
                date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i),
            )
        cls.url = reverse("recording-list")

    def test_admin_sees_card_admin_actions_on_each_card(self):
        """Staff user sees card-admin-actions on each of the 3 recent cards."""
        self.client.login(username="staff", password="pass")
        resp = self.client.get(self.url)
        content = resp.content.decode()
        grid_start = content.find('class="recordings-grid"')
        grid_section = content[grid_start:]
        count = grid_section.count('class="card-admin-actions"')
        self.assertEqual(count, 3)

    def test_anon_user_has_no_card_admin_actions(self):
        """Anonymous user sees NO card-admin-actions in the grid."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        grid_start = content.find('class="recordings-grid"')
        if grid_start >= 0:
            grid_section = content[grid_start:]
            self.assertNotIn("card-admin-actions", grid_section)


# ---------------------------------------------------------------------------
# 2. CSS Rule Tests — verify style.css contains proper alignment rules
# ---------------------------------------------------------------------------

def _read_css():
    css_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "static", "css", "style.css"
    )
    css_path = os.path.normpath(css_path)
    with open(css_path) as f:
        return f.read()


def _extract_rule(css_text, selector):
    """Extract the CSS rule block for a given selector.

    Returns the content between { } for the FIRST occurrence of the selector
    that is NOT inside a media query (i.e., top-level rule). If the selector
    appears multiple times, returns the first match.
    """
    # Escape special characters for regex
    escaped = re.escape(selector)
    pattern = re.compile(escaped + r'\s*\{([^}]*)\}')
    match = pattern.search(css_text)
    if match:
        return match.group(1)
    return ""


class CSSGridRulesTests(TestCase):
    """The CSS must define proper layout rules for .recordings-grid."""

    def setUp(self):
        self.css = _read_css()

    def test_recordings_grid_uses_flexbox(self):
        """'.recordings-grid' must use display: flex."""
        rule = _extract_rule(self.css, ".recordings-grid")
        self.assertIn("display:", rule)
        self.assertIn("flex", rule)

    def test_recordings_grid_children_have_equal_width(self):
        """'.recordings-grid > .recording-card-link' must use flex: 1 1 0
        for equal-width cards."""
        rule = _extract_rule(self.css, ".recordings-grid > .recording-card-link")
        self.assertIn("flex:", rule)
        # Should have flex: 1 1 0 or similar
        self.assertIn("1", rule)

    def test_recordings_grid_children_are_flex_containers(self):
        """'.recordings-grid > .recording-card-link' must be display: flex
        so the card inside fills the full height."""
        rule = _extract_rule(self.css, ".recordings-grid > .recording-card-link")
        self.assertIn("display:", rule)
        self.assertIn("flex", rule)

    def test_recordings_grid_has_gap(self):
        """'.recordings-grid' must define a gap between items."""
        rule = _extract_rule(self.css, ".recordings-grid")
        self.assertIn("gap:", rule)


class CSSCardAlignmentTests(TestCase):
    """The CSS must ensure cards are properly aligned within the grid."""

    def setUp(self):
        self.css = _read_css()

    def test_recording_card_fills_width(self):
        """'.recording-card' must have width: 100% to fill the flex container."""
        rule = _extract_rule(self.css, ".recording-card")
        self.assertIn("width:", rule)
        self.assertIn("100%", rule)

    def test_recording_card_uses_flex_column(self):
        """'.recording-card' must use display: flex and flex-direction: column
        so internal content distributes vertically."""
        rule = _extract_rule(self.css, ".recording-card")
        self.assertIn("display:", rule)
        self.assertIn("flex", rule)
        self.assertIn("flex-direction:", rule)
        self.assertIn("column", rule)

    def test_card_body_grows_to_fill(self):
        """'.card-body' must use flex: 1 so it fills remaining space
        inside the card, pushing all cards to equal visual height."""
        rule = _extract_rule(self.css, ".card-body")
        self.assertIn("flex:", rule)


class CSSCardBodyFlexTests(TestCase):
    """The .card-body must use flex layout to push tags/actions to the bottom."""

    def setUp(self):
        self.css = _read_css()

    def test_card_body_is_flex_column(self):
        """'.card-body' must be display: flex; flex-direction: column."""
        rule = _extract_rule(self.css, ".card-body")
        self.assertIn("display:", rule)
        self.assertIn("flex", rule)
        self.assertIn("flex-direction:", rule)
        self.assertIn("column", rule)

    def test_card_tags_has_margin_top_auto(self):
        """'.card-tags' must have margin-top: auto to push tags to bottom of card,
        ensuring consistent alignment across cards with different content heights."""
        rule = _extract_rule(self.css, ".card-tags")
        self.assertIn("margin-top:", rule)
        self.assertIn("auto", rule)


# ---------------------------------------------------------------------------
# 3. Edge Case Tests — few recordings, single recording, etc.
# ---------------------------------------------------------------------------

class GridEdgeCaseTests(TestCase):
    """Edge cases: 0, 1, 2 recent recordings (grid with fewer than 3 cards)."""

    def test_no_recordings_no_grid(self):
        """With 0 recordings, the grid should not appear."""
        resp = self.client.get(reverse("recording-list"))
        self.assertNotContains(resp, 'class="recordings-grid"')

    def test_one_recording_no_grid(self):
        """With 1 recording (featured only), the grid should not appear."""
        _rec(title="Solo", date=datetime.date(2025, 1, 1))
        resp = self.client.get(reverse("recording-list"))
        self.assertNotContains(resp, 'class="recordings-grid"')

    def test_two_recordings_grid_has_one_card(self):
        """With 2 recordings, grid has 1 recent card."""
        _rec(title="Older", date=datetime.date(2025, 1, 1))
        _rec(title="Newer", date=datetime.date(2025, 1, 2))
        resp = self.client.get(reverse("recording-list"))
        content = resp.content.decode()
        count = content.count('class="recording-card-link"')
        self.assertEqual(count, 1)

    def test_three_recordings_grid_has_two_cards(self):
        """With 3 recordings, grid has 2 recent cards."""
        for i in range(3):
            _rec(title=f"R{i}", date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i))
        resp = self.client.get(reverse("recording-list"))
        content = resp.content.decode()
        count = content.count('class="recording-card-link"')
        self.assertEqual(count, 2)

    def test_exactly_four_recordings_grid_has_three_cards(self):
        """With 4 recordings, grid has exactly 3 recent cards (max)."""
        for i in range(4):
            _rec(title=f"R{i}", date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i))
        resp = self.client.get(reverse("recording-list"))
        content = resp.content.decode()
        count = content.count('class="recording-card-link"')
        self.assertEqual(count, 3)

    def test_ten_recordings_grid_still_has_three_cards(self):
        """With 10 recordings, grid still has exactly 3 recent cards."""
        for i in range(10):
            _rec(title=f"R{i}", date=datetime.date(2025, 1, 1) + datetime.timedelta(days=i))
        resp = self.client.get(reverse("recording-list"))
        content = resp.content.decode()
        count = content.count('class="recording-card-link"')
        self.assertEqual(count, 3)


# ---------------------------------------------------------------------------
# 4. Content Variation Alignment Tests
# ---------------------------------------------------------------------------

class CardContentVariationTests(TestCase):
    """Cards with wildly different content must still render in the grid."""

    @classmethod
    def setUpTestData(cls):
        cls.tags = [Tag.objects.create(name=f"Tag{i}") for i in range(5)]
        # Card 1: very long title, long description, many tags
        cls.r1 = _rec(
            title="A Very Long Title That Spans Multiple Lines in the Card Header Area",
            description="A very long description that should be truncated. " * 10,
            date=datetime.date(2025, 1, 1),
            tags=cls.tags,
        )
        # Card 2: short title, no description, no tags
        cls.r2 = _rec(
            title="Short",
            date=datetime.date(2025, 1, 2),
        )
        # Card 3: medium title, short description, one tag
        cls.r3 = _rec(
            title="Medium Title Here",
            description="Brief desc.",
            date=datetime.date(2025, 1, 3),
            tags=[cls.tags[0]],
        )
        # Featured
        cls.r4 = _rec(title="Featured", date=datetime.date(2025, 1, 4))
        cls.url = reverse("recording-list")

    def test_all_3_cards_render(self):
        """All 3 cards appear in the grid regardless of content length."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn("A Very Long Title", content)
        self.assertIn("Short", content)
        self.assertIn("Medium Title Here", content)

    def test_card_description_is_clamped(self):
        """CSS must clamp card descriptions with -webkit-line-clamp."""
        css = _read_css()
        rule = _extract_rule(css, ".card-description")
        self.assertIn("-webkit-line-clamp", rule)

    def test_cards_with_no_description_still_have_card_body(self):
        """Cards without descriptions still have a card-body element."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        body_count = content.count('class="card-body"')
        self.assertEqual(body_count, 3)


# ---------------------------------------------------------------------------
# 5. Responsive CSS Tests
# ---------------------------------------------------------------------------

class ResponsiveGridTests(TestCase):
    """Mobile breakpoint must switch to single-column layout."""

    def setUp(self):
        self.css = _read_css()

    def test_mobile_grid_is_single_column(self):
        """Inside a media query, .recordings-grid should stack vertically."""
        # Find media query block and check it contains .recordings-grid
        media_pattern = re.compile(
            r'@media[^{]*max-width[^{]*\{(.*)\}',
            re.DOTALL,
        )
        match = media_pattern.search(self.css)
        self.assertIsNotNone(match, "Expected a max-width media query")
        media_body = match.group(1)
        self.assertIn(".recordings-grid", media_body)
        # Check the recordings-grid rule switches to column direction
        grid_in_media = re.search(
            r'\.recordings-grid[^{]*\{([^}]*)\}', media_body
        )
        self.assertIsNotNone(grid_in_media)
        self.assertIn("flex-direction", grid_in_media.group(1))
        self.assertIn("column", grid_in_media.group(1))
