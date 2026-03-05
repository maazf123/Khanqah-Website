"""
Tests for Chunk 1 of the live streaming feature: infrastructure layer.

Verifies that ASGI, Django Channels, and Redis channel layer are properly
configured. These tests validate:

1. Settings configuration (INSTALLED_APPS, ASGI_APPLICATION, CHANNEL_LAYERS)
2. ASGI application structure (ProtocolTypeRouter with http + websocket)
3. Channel layer messaging (send/receive, groups, broadcast)
4. HTTP backwards compatibility (existing views still work under ASGI)
5. WebSocket basic connection handling (unrouted paths get rejected)
"""

import asyncio

from django.conf import settings
from django.test import TestCase, SimpleTestCase, override_settings
from django.test import Client
from django.urls import reverse

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from asgiref.sync import async_to_sync


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


# ---------------------------------------------------------------------------
# 1. Settings Configuration Tests
# ---------------------------------------------------------------------------
class SettingsConfigurationTests(TestCase):
    """Verify that all Chunk 1 settings are properly configured."""

    def test_daphne_in_installed_apps(self):
        """daphne must be listed in INSTALLED_APPS."""
        self.assertIn("daphne", settings.INSTALLED_APPS)

    def test_channels_in_installed_apps(self):
        """channels must be listed in INSTALLED_APPS."""
        self.assertIn("channels", settings.INSTALLED_APPS)

    def test_daphne_before_staticfiles(self):
        """daphne must appear before django.contrib.staticfiles in
        INSTALLED_APPS, as required by daphne's documentation."""
        apps = list(settings.INSTALLED_APPS)
        daphne_index = apps.index("daphne")
        staticfiles_index = apps.index("django.contrib.staticfiles")
        self.assertLess(
            daphne_index,
            staticfiles_index,
            "daphne must appear before django.contrib.staticfiles "
            "in INSTALLED_APPS",
        )

    def test_asgi_application_setting(self):
        """ASGI_APPLICATION must point to config.asgi.application."""
        self.assertTrue(
            hasattr(settings, "ASGI_APPLICATION"),
            "ASGI_APPLICATION setting is missing",
        )
        self.assertEqual(
            settings.ASGI_APPLICATION,
            "config.asgi.application",
        )

    def test_channel_layers_setting_exists(self):
        """CHANNEL_LAYERS setting must exist and have a 'default' key."""
        self.assertTrue(
            hasattr(settings, "CHANNEL_LAYERS"),
            "CHANNEL_LAYERS setting is missing",
        )
        self.assertIn("default", settings.CHANNEL_LAYERS)

    def test_channel_layers_backend_is_redis(self):
        """The production settings must configure RedisChannelLayer.
        (This test reads the settings module directly, not the test override.)"""
        import importlib
        import config.settings as prod_settings
        importlib.reload(prod_settings)
        backend = prod_settings.CHANNEL_LAYERS["default"]["BACKEND"]
        self.assertEqual(
            backend,
            "channels_redis.core.RedisChannelLayer",
        )


# ---------------------------------------------------------------------------
# 2. ASGI Application Tests
# ---------------------------------------------------------------------------
class ASGIApplicationTests(TestCase):
    """Verify the ASGI application is correctly wired."""

    def test_asgi_application_importable(self):
        """The application object must be importable from config.asgi."""
        from config.asgi import application
        self.assertIsNotNone(application)

    def test_application_is_protocol_type_router(self):
        """The application must be a ProtocolTypeRouter instance."""
        from config.asgi import application
        from channels.routing import ProtocolTypeRouter
        self.assertIsInstance(application, ProtocolTypeRouter)

    def test_application_handles_http(self):
        """The ProtocolTypeRouter must have an 'http' handler."""
        from config.asgi import application
        # ProtocolTypeRouter stores handlers in self.application_mapping
        self.assertIn(
            "http",
            application.application_mapping,
            "ProtocolTypeRouter does not handle 'http' protocol",
        )

    def test_application_handles_websocket(self):
        """The ProtocolTypeRouter must have a 'websocket' handler."""
        from config.asgi import application
        self.assertIn(
            "websocket",
            application.application_mapping,
            "ProtocolTypeRouter does not handle 'websocket' protocol",
        )


# ---------------------------------------------------------------------------
# 3. Channel Layer Tests (using InMemoryChannelLayer)
# ---------------------------------------------------------------------------
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ChannelLayerTests(TestCase):
    """Test channel layer send/receive and group operations.

    Uses InMemoryChannelLayer so Redis is not required for these tests.
    """

    def setUp(self):
        """Get a fresh channel layer for each test."""
        self.channel_layer = get_channel_layer()

    def test_get_channel_layer(self):
        """get_channel_layer() must return a non-None layer."""
        self.assertIsNotNone(self.channel_layer)

    def test_send_and_receive(self):
        """Can send a message to a channel and receive it back."""
        async def _test():
            channel_name = await self.channel_layer.new_channel()
            await self.channel_layer.send(
                channel_name,
                {"type": "test.message", "text": "hello"},
            )
            message = await self.channel_layer.receive(channel_name)
            self.assertEqual(message["type"], "test.message")
            self.assertEqual(message["text"], "hello")

        async_to_sync(_test)()

    def test_group_send_and_receive(self):
        """Can add a channel to a group, send to the group, and receive."""
        async def _test():
            channel_name = await self.channel_layer.new_channel()
            group_name = "test-group"

            await self.channel_layer.group_add(group_name, channel_name)
            await self.channel_layer.group_send(
                group_name,
                {"type": "group.message", "text": "broadcast"},
            )
            message = await self.channel_layer.receive(channel_name)
            self.assertEqual(message["type"], "group.message")
            self.assertEqual(message["text"], "broadcast")

            # Clean up
            await self.channel_layer.group_discard(group_name, channel_name)

        async_to_sync(_test)()

    def test_group_broadcast_to_multiple_channels(self):
        """Multiple channels in a group all receive the broadcast."""
        async def _test():
            group_name = "broadcast-group"
            channel1 = await self.channel_layer.new_channel()
            channel2 = await self.channel_layer.new_channel()
            channel3 = await self.channel_layer.new_channel()

            await self.channel_layer.group_add(group_name, channel1)
            await self.channel_layer.group_add(group_name, channel2)
            await self.channel_layer.group_add(group_name, channel3)

            await self.channel_layer.group_send(
                group_name,
                {"type": "broadcast.msg", "data": "to-all"},
            )

            msg1 = await self.channel_layer.receive(channel1)
            msg2 = await self.channel_layer.receive(channel2)
            msg3 = await self.channel_layer.receive(channel3)

            for msg in (msg1, msg2, msg3):
                self.assertEqual(msg["type"], "broadcast.msg")
                self.assertEqual(msg["data"], "to-all")

            # Clean up
            for ch in (channel1, channel2, channel3):
                await self.channel_layer.group_discard(group_name, ch)

        async_to_sync(_test)()

    def test_group_discard_stops_receiving(self):
        """After removing a channel from a group, it no longer receives."""
        async def _test():
            group_name = "discard-group"
            channel_name = await self.channel_layer.new_channel()

            await self.channel_layer.group_add(group_name, channel_name)
            await self.channel_layer.group_discard(group_name, channel_name)

            await self.channel_layer.group_send(
                group_name,
                {"type": "after.discard", "text": "should-not-arrive"},
            )

            # The channel should have nothing to receive. We use a short
            # timeout to avoid blocking forever.
            try:
                msg = await asyncio.wait_for(
                    self.channel_layer.receive(channel_name),
                    timeout=0.1,
                )
                # If we somehow get a message, fail the test
                self.fail(
                    "Channel received a message after being discarded "
                    f"from the group: {msg}"
                )
            except asyncio.TimeoutError:
                pass  # Expected -- no message should arrive

        async_to_sync(_test)()

    def test_send_to_empty_group_no_error(self):
        """Sending to a group with no members must not raise an error."""
        async def _test():
            # group_send to a group that has never had members
            await self.channel_layer.group_send(
                "empty-group",
                {"type": "no.members", "text": "silence"},
            )

        # Should complete without raising
        async_to_sync(_test)()


# ---------------------------------------------------------------------------
# 4. HTTP Backwards Compatibility Tests
# ---------------------------------------------------------------------------
class HTTPBackwardsCompatibilityTests(TestCase):
    """Ensure existing HTTP views still work after ASGI migration."""

    def setUp(self):
        self.client = Client()

    def test_recording_list_returns_200(self):
        """The recording-list homepage must still return 200."""
        url = reverse("recording-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_page_loads(self):
        """The admin page must still load (200 or 302 redirect to login)."""
        response = self.client.get("/admin/")
        self.assertIn(
            response.status_code,
            [200, 302],
            f"Admin returned unexpected status {response.status_code}",
        )

    def test_static_url_configured(self):
        """STATIC_URL must still be set so static files are served."""
        self.assertTrue(
            hasattr(settings, "STATIC_URL"),
            "STATIC_URL setting is missing",
        )
        self.assertTrue(
            len(settings.STATIC_URL) > 0,
            "STATIC_URL must not be empty",
        )


# ---------------------------------------------------------------------------
# 5. WebSocket Basic Connection Tests
# ---------------------------------------------------------------------------
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class WebSocketBasicConnectionTests(SimpleTestCase):
    """Test WebSocket connection handling using channels.testing."""

    def test_unrouted_websocket_path_rejected(self):
        """A WebSocket connection to an unrouted path must be rejected.

        Since the URLRouter in asgi.py has an empty route list, any
        WebSocket path should fail (ValueError from URLRouter).
        """
        from config.asgi import application

        async def _test():
            communicator = WebsocketCommunicator(application, "/ws/nonexistent/")
            with self.assertRaises((ValueError, TimeoutError)):
                await communicator.connect()

        async_to_sync(_test)()

    def test_unrouted_root_websocket_rejected(self):
        """A WebSocket connection to the root path must also be rejected."""
        from config.asgi import application

        async def _test():
            communicator = WebsocketCommunicator(application, "/")
            with self.assertRaises((ValueError, TimeoutError)):
                await communicator.connect()

        async_to_sync(_test)()
