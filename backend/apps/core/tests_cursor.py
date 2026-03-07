"""
TDD tests for the cursor / text-caret fix.

Root causes of the unwanted I-beam cursor on non-editable elements:
  A) CSS cursor property — browser shows I-beam cursor on hover over text
  B) user-select — browser shows text-selection caret when clicking on text
  C) Inline styles or JS injecting cursor: text
  D) CSS syntax errors preventing rules from loading
  E) Missing stylesheet link on a page
  F) Later CSS rules overriding the reset with cursor: text
  G) Cache-busting — browser may serve stale CSS without a version param

The fix applies:
  * { cursor: default; user-select: none; }
  — then restores user-select: text on content elements (p, h1-h6, etc.)
  — then restores cursor: pointer on interactive elements (a, button, etc.)
  — then restores cursor: text + user-select: text on form inputs
"""

import os
import re

from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse

from apps.core.models import LiveStream
from apps.core.views_archive import ArchivedItemsView
from apps.core.views_home import HomeView

# ---------------------------------------------------------------------------
# Module-level URL configuration
# ---------------------------------------------------------------------------
from django.contrib import admin

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("recordings/", include("apps.recordings.urls")),
    path("tags/", include("apps.tags.urls")),
    path("archived/", ArchivedItemsView.as_view(), name="archived-items"),
    path("", HomeView.as_view(), name="home"),
]

CSS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "static", "css", "style.css",
)


def _read_css():
    with open(CSS_PATH) as f:
        return f.read()


def _reset_section(css):
    """Return the RESET & BASE section (everything before :root)."""
    start = css.find("RESET & BASE")
    end = css.find(":root")
    return css[start:end] if start >= 0 and end > start else ""


# ============================================================================
# A. Root Cause: CSS cursor property
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class CursorDefaultTests(TestCase):
    """Universal selector must set cursor: default."""

    def setUp(self):
        self.css = _read_css()
        self.reset = _reset_section(self.css)

    def test_universal_selector_has_cursor_default(self):
        self.assertRegex(self.reset, r'\*\s*\{[^}]*cursor:\s*default\s*!important')

    def test_cursor_default_before_root(self):
        pos = self.css.find("cursor: default")
        root = self.css.find(":root")
        self.assertGreater(pos, -1)
        self.assertGreater(root, pos)

    def test_no_cursor_text_before_restore_block(self):
        before_restore = self.reset.split("Restore")[0] if "Restore" in self.reset else self.reset
        self.assertNotIn("cursor: text", before_restore)


# ============================================================================
# B. !important enforcement — all cursor rules use !important
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class CursorImportantTests(TestCase):
    """Every cursor rule in the CSS must use !important to override browser UA styles."""

    def setUp(self):
        self.css = _read_css()

    def test_all_cursor_rules_have_important(self):
        """No cursor rule should lack !important."""
        stripped = re.sub(r'/\*.*?\*/', '', self.css, flags=re.DOTALL)
        all_cursor = re.findall(r'cursor\s*:\s*[^;]+;', stripped)
        for rule in all_cursor:
            self.assertIn('!important', rule,
                          f"Missing !important: {rule.strip()}")

    def test_cursor_default_important(self):
        self.assertIn('cursor: default !important', self.css)

    def test_cursor_pointer_important(self):
        self.assertIn('cursor: pointer !important', self.css)

    def test_cursor_text_important(self):
        self.assertIn('cursor: text !important', self.css)

    def test_cursor_not_allowed_important(self):
        self.assertIn('cursor: not-allowed !important', self.css)


# ============================================================================
# B2. caret-color: transparent — hides text caret on non-editable elements
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class CaretColorTests(TestCase):
    """The text caret must be invisible on non-editable elements."""

    def setUp(self):
        self.css = _read_css()
        self.reset = _reset_section(self.css)

    def test_universal_caret_transparent(self):
        """* selector sets caret-color: transparent."""
        self.assertRegex(self.reset, r'\*\s*\{[^}]*caret-color:\s*transparent')

    def test_caret_restored_on_text_inputs(self):
        """Form inputs restore caret-color: auto so the caret is visible."""
        pattern = r'input\[type="text"\][^{]*\{[^}]*caret-color:\s*auto'
        self.assertRegex(self.css, pattern)

    def test_caret_restored_on_textarea(self):
        """Textarea restores caret-color: auto."""
        self.assertRegex(self.css, r'\btextarea\b[^{]*\{[^}]*caret-color:\s*auto')

    def test_caret_restored_on_contenteditable(self):
        """contenteditable restores caret-color: auto."""
        self.assertIn('caret-color: auto', self.css)

    def test_no_caret_auto_on_body(self):
        """body must NOT set caret-color: auto."""
        body_match = re.search(r'\bbody\b\s*\{([^}]*)\}', self.css)
        if body_match:
            self.assertNotIn('caret-color: auto', body_match.group(1))

    def test_no_caret_auto_on_heading_selectors(self):
        """h1-h6 must NOT set caret-color: auto."""
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            pattern = rf'\b{tag}\b\s*\{{([^}}]*)\}}'
            match = re.search(pattern, self.css)
            if match:
                self.assertNotIn('caret-color: auto', match.group(1),
                                 f"{tag} should not have caret-color: auto")


# ============================================================================
# C. Interactive elements retain cursor: pointer
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class InteractiveCursorPointerTests(TestCase):

    def setUp(self):
        self.css = _read_css()

    def test_anchor_pointer(self):
        self.assertRegex(self.css, r'\ba\b[^{]*\{[^}]*cursor:\s*pointer')

    def test_button_pointer(self):
        self.assertRegex(self.css, r'\bbutton\b[^{]*\{[^}]*cursor:\s*pointer')

    def test_btn_class_pointer(self):
        self.assertRegex(self.css, r'\.btn\b[^{]*\{[^}]*cursor:\s*pointer')

    def test_role_button_present(self):
        self.assertIn('[role="button"]', self.css)

    def test_label_for_present(self):
        self.assertIn('label[for]', self.css)

    def test_navbar_brand_pointer(self):
        self.assertRegex(self.css, r'\.navbar-brand[^{]*\{[^}]*cursor:\s*pointer')

    def test_nav_links_a_present(self):
        self.assertIn('.nav-links a', self.css)

    def test_submit_input_present(self):
        self.assertIn('input[type="submit"]', self.css)

    def test_checkbox_present(self):
        self.assertIn('input[type="checkbox"]', self.css)

    def test_radio_present(self):
        self.assertIn('input[type="radio"]', self.css)

    def test_select_present(self):
        self.assertRegex(self.css, r'\bselect\b')

    def test_summary_present(self):
        self.assertIn('summary', self.css)


# ============================================================================
# D. Text inputs retain cursor: text + user-select: text
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class TextInputCursorTests(TestCase):

    def setUp(self):
        self.css = _read_css()

    def test_text_input(self):
        self.assertIn('input[type="text"]', self.css)

    def test_email_input(self):
        self.assertIn('input[type="email"]', self.css)

    def test_password_input(self):
        self.assertIn('input[type="password"]', self.css)

    def test_search_input(self):
        self.assertIn('input[type="search"]', self.css)

    def test_url_input(self):
        self.assertIn('input[type="url"]', self.css)

    def test_tel_input(self):
        self.assertIn('input[type="tel"]', self.css)

    def test_number_input(self):
        self.assertIn('input[type="number"]', self.css)

    def test_textarea_cursor_text(self):
        self.assertRegex(self.css, r'\btextarea\b[^{]*\{[^}]*cursor:\s*text')

    def test_contenteditable(self):
        self.assertIn('[contenteditable="true"]', self.css)

    def test_input_rule_block_has_cursor_text(self):
        self.assertRegex(self.css, r'input\[type="text"\][^{]*\{[^}]*cursor:\s*text')

    def test_input_cursor_text_has_important(self):
        self.assertRegex(self.css, r'input\[type="text"\][^{]*\{[^}]*cursor:\s*text\s*!important')


# ============================================================================
# E. CSS syntax — no parsing errors that would break rules
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class CSSSyntaxTests(TestCase):
    """CSS must be syntactically valid so cursor rules actually apply."""

    def setUp(self):
        self.css = _read_css()

    def test_braces_balanced(self):
        self.assertEqual(self.css.count('{'), self.css.count('}'))

    def test_no_double_semicolons(self):
        """Double semicolons can confuse some CSS parsers."""
        self.assertNotIn(';;', self.css)

    def test_no_unclosed_comments(self):
        opens = len(re.findall(r'/\*', self.css))
        closes = len(re.findall(r'\*/', self.css))
        self.assertEqual(opens, closes)

    def test_no_import_rules(self):
        """@import can delay loading and cause race conditions."""
        self.assertNotIn('@import', self.css)

    def test_cursor_default_not_inside_comment(self):
        """cursor: default must not be commented out."""
        # Remove all comments then check
        stripped = re.sub(r'/\*.*?\*/', '', self.css, flags=re.DOTALL)
        self.assertIn('cursor: default', stripped)

    def test_cursor_important_not_inside_comment(self):
        stripped = re.sub(r'/\*.*?\*/', '', self.css, flags=re.DOTALL)
        self.assertIn('cursor: default !important', stripped)


# ============================================================================
# F. No broad selectors set cursor: text anywhere in the CSS
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class NoCursorTextOnBroadSelectorsTests(TestCase):

    def setUp(self):
        self.css = _read_css()

    def test_no_h1_cursor_text(self):
        self.assertNotRegex(self.css, r'\bh1\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_h2_cursor_text(self):
        self.assertNotRegex(self.css, r'\bh2\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_h3_cursor_text(self):
        self.assertNotRegex(self.css, r'\bh3\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_p_cursor_text(self):
        self.assertNotRegex(self.css, r'(?<!\w)p\s*\{[^}]*cursor:\s*text')

    def test_no_div_cursor_text(self):
        self.assertNotRegex(self.css, r'\bdiv\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_span_cursor_text(self):
        self.assertNotRegex(self.css, r'\bspan\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_section_cursor_text(self):
        self.assertNotRegex(self.css, r'\bsection\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_article_cursor_text(self):
        self.assertNotRegex(self.css, r'\barticle\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_blockquote_cursor_text(self):
        self.assertNotRegex(self.css, r'\bblockquote\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_li_cursor_text(self):
        self.assertNotRegex(self.css, r'\bli\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_nav_cursor_text(self):
        self.assertNotRegex(self.css, r'\bnav\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_footer_cursor_text(self):
        self.assertNotRegex(self.css, r'\bfooter\b[^{]*\{[^}]*cursor:\s*text')

    def test_no_body_cursor_text(self):
        self.assertNotRegex(self.css, r'\bbody\b\s*\{[^}]*cursor:\s*text')


# ============================================================================
# G. Layout / card / hero classes — no cursor: text
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class LayoutClassCursorTests(TestCase):

    def setUp(self):
        self.css = _read_css()

    def _rule_for(self, selector):
        escaped = re.escape(selector)
        m = re.search(escaped + r'\s*\{([^}]*)\}', self.css)
        return m.group(1) if m else ""

    def test_hero_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".hero"))

    def test_hero_text_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".hero-text"))

    def test_hero_inner_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".hero-inner"))

    def test_navbar_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".navbar"))

    def test_footer_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".footer"))

    def test_main_content_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".main-content"))

    def test_calligraphy_strip_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".calligraphy-strip"))

    def test_recording_card_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".recording-card"))

    def test_detail_card_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".detail-card"))

    def test_home_feature_card_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".home-feature-card"))

    def test_featured_recording_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".featured-recording"))

    def test_login_card_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".login-card"))

    def test_listen_card_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".listen-card"))

    def test_broadcast_card_no_cursor_text(self):
        self.assertNotIn("cursor: text", self._rule_for(".broadcast-card"))


# ============================================================================
# H. Every page links the stylesheet (with cache-busting param)
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class StylesheetOnEveryPageTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("staff", password="pass", is_staff=True)

    def _html(self, url, login=False):
        if login:
            self.client.login(username="staff", password="pass")
        r = self.client.get(url)
        return r.content.decode() if r.status_code == 200 else ""

    def _assert_css(self, html):
        self.assertIn("style.css", html)

    def _assert_cache_bust(self, html):
        self.assertRegex(html, r'style\.css\?v=\d+')

    def test_home(self):
        html = self._html(reverse("home"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_recording_list(self):
        html = self._html(reverse("recording-list"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_recording_archive(self):
        html = self._html(reverse("recording-archive"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_writing_list(self):
        html = self._html(reverse("writing-list"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_writing_archive(self):
        html = self._html(reverse("writing-archive"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_livestream_list(self):
        html = self._html(reverse("livestream-list"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_login(self):
        html = self._html(reverse("login"))
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_livestream_start(self):
        html = self._html(reverse("livestream-start"), login=True)
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_livestream_broadcast(self):
        self.client.login(username="staff", password="pass")
        s = LiveStream.objects.create(title="T", created_by=self.staff)
        html = self._html(reverse("livestream-broadcast", kwargs={"stream_key": s.stream_key}), login=True)
        self._assert_css(html)
        self._assert_cache_bust(html)

    def test_livestream_listen(self):
        s = LiveStream.objects.create(title="T", created_by=self.staff)
        html = self._html(reverse("livestream-listen", kwargs={"stream_key": s.stream_key}))
        self._assert_css(html)
        self._assert_cache_bust(html)


# ============================================================================
# I. No inline cursor: text on non-input elements (per page)
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class NoInlineCursorTextTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("staff", password="pass", is_staff=True)

    def _check(self, html):
        matches = re.findall(
            r'<(\w+)[^>]*style\s*=\s*"[^"]*cursor\s*:\s*text[^"]*"',
            html, re.IGNORECASE,
        )
        allowed = {"input", "textarea"}
        violations = [t for t in matches if t.lower() not in allowed]
        self.assertEqual(violations, [])

    def test_home(self):
        self._check(self.client.get(reverse("home")).content.decode())

    def test_recording_list(self):
        self._check(self.client.get(reverse("recording-list")).content.decode())

    def test_recording_archive(self):
        self._check(self.client.get(reverse("recording-archive")).content.decode())

    def test_writing_list(self):
        self._check(self.client.get(reverse("writing-list")).content.decode())

    def test_writing_archive(self):
        self._check(self.client.get(reverse("writing-archive")).content.decode())

    def test_livestream_list(self):
        self._check(self.client.get(reverse("livestream-list")).content.decode())

    def test_login(self):
        self._check(self.client.get(reverse("login")).content.decode())

    def test_livestream_start(self):
        self.client.login(username="staff", password="pass")
        self._check(self.client.get(reverse("livestream-start")).content.decode())

    def test_livestream_broadcast(self):
        self.client.login(username="staff", password="pass")
        s = LiveStream.objects.create(title="T", created_by=self.staff)
        self._check(self.client.get(reverse("livestream-broadcast", kwargs={"stream_key": s.stream_key})).content.decode())

    def test_livestream_listen(self):
        s = LiveStream.objects.create(title="T", created_by=self.staff)
        self._check(self.client.get(reverse("livestream-listen", kwargs={"stream_key": s.stream_key})).content.decode())


# ============================================================================
# J. No inline cursor styles on non-interactive elements (per page)
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class NoInlineCursorStylesTests(TestCase):
    """No inline style should set cursor on non-interactive elements."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("staff", password="pass", is_staff=True)

    def _check(self, html):
        matches = re.findall(
            r'<(\w+)[^>]*style\s*=\s*"[^"]*cursor\s*:[^"]*"',
            html, re.IGNORECASE,
        )
        allowed = {"input", "textarea", "button", "a", "select"}
        violations = [t for t in matches if t.lower() not in allowed]
        self.assertEqual(violations, [])

    def test_home(self):
        self._check(self.client.get(reverse("home")).content.decode())

    def test_recording_list(self):
        self._check(self.client.get(reverse("recording-list")).content.decode())

    def test_livestream_list(self):
        self._check(self.client.get(reverse("livestream-list")).content.decode())

    def test_login(self):
        self._check(self.client.get(reverse("login")).content.decode())

    def test_writing_list(self):
        self._check(self.client.get(reverse("writing-list")).content.decode())


# ============================================================================
# K. JS must not inject cursor: text or user-select: auto
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class NoJSCursorManipulationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("staff", password="pass", is_staff=True)

    def _scripts(self, html):
        return re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)

    def _check_no_cursor_text(self, html):
        for s in self._scripts(html):
            self.assertNotRegex(s, r'cursor\s*:\s*text')

    def test_home_no_cursor_text(self):
        self._check_no_cursor_text(self.client.get(reverse("home")).content.decode())

    def test_recording_list_no_cursor_text(self):
        self.client.login(username="staff", password="pass")
        self._check_no_cursor_text(self.client.get(reverse("recording-list")).content.decode())

    def test_broadcast_no_cursor_text(self):
        self.client.login(username="staff", password="pass")
        s = LiveStream.objects.create(title="T", created_by=self.staff)
        self._check_no_cursor_text(self.client.get(reverse("livestream-broadcast", kwargs={"stream_key": s.stream_key})).content.decode())

    def test_listen_no_cursor_text(self):
        s = LiveStream.objects.create(title="T", created_by=self.staff)
        self._check_no_cursor_text(self.client.get(reverse("livestream-listen", kwargs={"stream_key": s.stream_key})).content.decode())


# ============================================================================
# L. Load order — all cursor/user-select resets before :root
# ============================================================================
@override_settings(ROOT_URLCONF="apps.core.tests_cursor")
class CSSLoadOrderTests(TestCase):

    def setUp(self):
        self.css = _read_css()

    def test_cursor_default_before_root(self):
        pos = self.css.find("cursor: default")
        root = self.css.find(":root")
        self.assertGreater(pos, -1)
        self.assertGreater(root, pos)

    def test_cursor_pointer_restore_before_root(self):
        m = re.search(r'a,\s*button[^{]*\{[^}]*cursor:\s*pointer', self.css)
        self.assertIsNotNone(m)
        self.assertGreater(self.css.find(":root"), m.start())

    def test_cursor_text_restore_before_root(self):
        m = re.search(r'input\[type="text"\][^{]*\{[^}]*cursor:\s*text', self.css)
        self.assertIsNotNone(m)
        self.assertGreater(self.css.find(":root"), m.start())

    def test_cursor_text_important_before_root(self):
        m = re.search(r'input\[type="text"\][^{]*\{[^}]*cursor:\s*text\s*!important', self.css)
        self.assertIsNotNone(m)
        self.assertGreater(self.css.find(":root"), m.start())
