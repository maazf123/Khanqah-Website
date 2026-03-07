"""
Tests to ensure ngrok domains are always in ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS,
preventing DisallowedHost errors when accessing the site via ngrok tunnels.
"""
from django.conf import settings
from django.test import TestCase, RequestFactory, override_settings
from django.test.client import Client


class AllowedHostsConfigTest(TestCase):
    """Verify settings always include ngrok domains."""

    def test_ngrok_free_app_in_allowed_hosts(self):
        self.assertIn(".ngrok-free.app", settings.ALLOWED_HOSTS)

    def test_ngrok_free_dev_in_allowed_hosts(self):
        self.assertIn(".ngrok-free.dev", settings.ALLOWED_HOSTS)

    def test_localhost_in_allowed_hosts(self):
        self.assertIn("localhost", settings.ALLOWED_HOSTS)

    def test_127_0_0_1_in_allowed_hosts(self):
        self.assertIn("127.0.0.1", settings.ALLOWED_HOSTS)

    def test_ngrok_app_in_csrf_trusted_origins(self):
        self.assertIn("https://*.ngrok-free.app", settings.CSRF_TRUSTED_ORIGINS)

    def test_ngrok_dev_in_csrf_trusted_origins(self):
        self.assertIn("https://*.ngrok-free.dev", settings.CSRF_TRUSTED_ORIGINS)


class NgrokHostRequestTest(TestCase):
    """Test that requests from ngrok hosts are accepted (not DisallowedHost)."""

    def test_ngrok_free_dev_host_accepted(self):
        """Simulate a request with an ngrok-free.dev host header."""
        response = self.client.get(
            "/",
            HTTP_HOST="succubous-predominatingly-marilee.ngrok-free.dev",
        )
        # Should not be a 400 (DisallowedHost returns 400)
        self.assertNotEqual(response.status_code, 400)

    def test_ngrok_free_app_host_accepted(self):
        """Simulate a request with an ngrok-free.app host header."""
        response = self.client.get(
            "/",
            HTTP_HOST="some-random-name.ngrok-free.app",
        )
        self.assertNotEqual(response.status_code, 400)

    def test_localhost_host_accepted(self):
        response = self.client.get("/", HTTP_HOST="localhost")
        self.assertNotEqual(response.status_code, 400)

    def test_127_0_0_1_host_accepted(self):
        response = self.client.get("/", HTTP_HOST="127.0.0.1")
        self.assertNotEqual(response.status_code, 400)

    def test_unknown_host_rejected(self):
        """An unknown host should be rejected with 400."""
        response = self.client.get(
            "/",
            HTTP_HOST="evil-site.example.com",
        )
        self.assertEqual(response.status_code, 400)

    def test_ngrok_host_on_recordings_page(self):
        """Ensure recordings page works via ngrok host."""
        response = self.client.get(
            "/recordings/",
            HTTP_HOST="test-tunnel.ngrok-free.dev",
        )
        self.assertNotEqual(response.status_code, 400)
        self.assertIn(response.status_code, [200, 301, 302])

    def test_ngrok_host_on_writings_page(self):
        """Ensure writings page works via ngrok host."""
        response = self.client.get(
            "/writings/",
            HTTP_HOST="test-tunnel.ngrok-free.dev",
        )
        self.assertNotEqual(response.status_code, 400)
        self.assertIn(response.status_code, [200, 301, 302])

    def test_ngrok_host_on_home_page(self):
        """Ensure home page works via ngrok host."""
        response = self.client.get(
            "/",
            HTTP_HOST="test-tunnel.ngrok-free.dev",
        )
        self.assertNotEqual(response.status_code, 400)
        self.assertEqual(response.status_code, 200)
