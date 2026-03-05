from django.test import TestCase
from django.db import IntegrityError
from django.contrib.admin.sites import site as admin_site

from apps.tags.models import Tag


class TagModelBasicCRUDTests(TestCase):
    """Tests for basic Create, Read, Update, Delete operations on the Tag model."""

    def test_create_tag_with_valid_name(self):
        """A tag can be created with a valid name."""
        tag = Tag.objects.create(name="Quran Recitation")
        self.assertIsNotNone(tag.pk)
        self.assertEqual(tag.name, "Quran Recitation")

    def test_tag_auto_generates_slug(self):
        """A newly created tag gets an auto-generated slug from its name."""
        tag = Tag.objects.create(name="Respecting Parents")
        self.assertEqual(tag.slug, "respecting-parents")

    def test_tag_str_returns_name(self):
        """The __str__ method returns the tag's name."""
        tag = Tag.objects.create(name="Dhikr")
        self.assertEqual(str(tag), "Dhikr")

    def test_tag_default_ordering_is_by_name(self):
        """The Meta ordering is set to order by name."""
        self.assertEqual(Tag._meta.ordering, ["name"])


class TagSlugGenerationTests(TestCase):
    """Tests for slug auto-generation behavior."""

    def test_slug_auto_generated_from_name(self):
        """Slug is created by slugifying the name (lowercase, hyphens for spaces)."""
        tag = Tag.objects.create(name="Respecting Parents")
        self.assertEqual(tag.slug, "respecting-parents")

    def test_slug_handles_special_characters(self):
        """Special characters are stripped or converted during slugification."""
        tag = Tag.objects.create(name="Qur'an & Sunnah!")
        # Django's slugify strips non-alphanumeric chars (except hyphens)
        self.assertEqual(tag.slug, "quran-sunnah")

    def test_slug_regenerated_if_name_changes_and_slug_cleared(self):
        """
        The current implementation only generates a slug when slug is falsy.
        If the name changes but the slug is not cleared, the old slug persists.
        To get a new slug after a name change, the slug must be cleared first.
        """
        tag = Tag.objects.create(name="Old Name")
        self.assertEqual(tag.slug, "old-name")
        # Clear slug and change name to trigger regeneration
        tag.name = "New Name"
        tag.slug = ""
        tag.save()
        self.assertEqual(tag.slug, "new-name")

    def test_slug_not_regenerated_if_name_changes_without_clearing_slug(self):
        """
        If the name changes but the slug field already has a value,
        the slug is NOT regenerated (it is preserved as-is).
        """
        tag = Tag.objects.create(name="Original")
        self.assertEqual(tag.slug, "original")
        tag.name = "Updated"
        tag.save()
        # Slug remains the old value because it was not cleared
        self.assertEqual(tag.slug, "original")

    def test_manually_set_slug_is_preserved(self):
        """A manually provided slug is not overwritten by auto-generation."""
        tag = Tag(name="My Custom Tag", slug="custom-slug-here")
        tag.save()
        self.assertEqual(tag.slug, "custom-slug-here")


class TagValidationAndConstraintTests(TestCase):
    """Tests for model field validation and database constraints."""

    def test_duplicate_name_raises_integrity_error(self):
        """Creating two tags with the same name raises IntegrityError."""
        Tag.objects.create(name="Patience")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name="Patience")

    def test_duplicate_slug_raises_integrity_error(self):
        """Creating two tags with the same slug raises IntegrityError."""
        Tag.objects.create(name="Tag One", slug="same-slug")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name="Tag Two", slug="same-slug")

    def test_name_cannot_be_blank(self):
        """A tag with a blank name should fail validation."""
        tag = Tag(name="")
        with self.assertRaises(Exception):
            tag.full_clean()

    def test_name_cannot_be_empty_on_create(self):
        """Creating a tag with an empty string name fails validation."""
        tag = Tag(name="")
        with self.assertRaises(Exception):
            tag.full_clean()

    def test_name_max_length_is_100(self):
        """The name field has a max_length of 100."""
        self.assertEqual(Tag._meta.get_field("name").max_length, 100)

    def test_name_at_exactly_100_characters_works(self):
        """A name of exactly 100 characters is accepted without error."""
        name_100 = "a" * 100
        tag = Tag(name=name_100)
        # full_clean should not raise for a 100-character name
        tag.full_clean()
        tag.save()
        self.assertEqual(len(tag.name), 100)
        self.assertIsNotNone(tag.pk)


class TagEdgeCaseTests(TestCase):
    """Tests for edge cases and less obvious behavior."""

    def test_whitespace_heavy_name_leading_trailing(self):
        """
        Leading/trailing whitespace in the name is preserved in the name field
        but slugify strips it for the slug.
        """
        tag = Tag.objects.create(name="  Tawbah  ")
        # The name is stored as-is (Django does not auto-strip CharField)
        self.assertEqual(tag.name, "  Tawbah  ")
        # Slugify strips whitespace and lowercases
        self.assertEqual(tag.slug, "tawbah")

    def test_multiple_tags_ordering(self):
        """Multiple tags are returned ordered by name alphabetically."""
        Tag.objects.create(name="Zakat")
        Tag.objects.create(name="Adab")
        Tag.objects.create(name="Muhasaba")

        tags = list(Tag.objects.values_list("name", flat=True))
        self.assertEqual(tags, ["Adab", "Muhasaba", "Zakat"])

    def test_tag_can_be_deleted(self):
        """A tag can be deleted from the database."""
        tag = Tag.objects.create(name="Temporary")
        tag_pk = tag.pk
        tag.delete()
        self.assertFalse(Tag.objects.filter(pk=tag_pk).exists())


class TagAdminIntegrationTests(TestCase):
    """Tests for admin site registration."""

    def test_tag_model_is_registered_in_admin(self):
        """The Tag model should be registered with the Django admin site."""
        self.assertIn(Tag, admin_site._registry)
