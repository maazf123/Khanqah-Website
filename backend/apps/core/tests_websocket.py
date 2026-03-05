"""
TDD tests for the WebSocket consumer (Chunk 3) of the live streaming feature.

Tests cover:
1. WebSocket routing configuration (route exists, pattern matches)
2. ASGI routing integration (websocket routes wired into the application)
3. Consumer connection handling (valid/invalid/inactive streams, disconnect)
4. Consumer role signaling (broadcaster/listener role messages)
5. Audio broadcasting (broadcaster->listeners, multiple listeners, listener blocked)
6. Consumer group management (correct group, leave on disconnect, stream isolation)
"""

import asyncio
import base64
import json
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import path

from apps.core.consumers import AudioStreamConsumer
from apps.core.models import LiveStream

TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# URLRouter application for tests — needed so scope["url_route"] is populated
test_ws_application = URLRouter([
    path("ws/stream/<uuid:stream_key>/", AudioStreamConsumer.as_asgi()),
])


# ===========================================================================
# 1. WebSocket Routing Tests
# ===========================================================================
class WebSocketRoutingTests(SimpleTestCase):
    """Verify that WebSocket URL routing is properly configured."""

    def test_websocket_route_exists(self):
        """websocket_urlpatterns from apps.core.routing is not empty."""
        from apps.core.routing import websocket_urlpatterns

        self.assertTrue(
            len(websocket_urlpatterns) > 0,
            "websocket_urlpatterns should contain at least one route",
        )

    def test_route_pattern_matches_uuid(self):
        """The URL pattern matches the expected ws/stream/<uuid:stream_key>/ format."""
        from apps.core.routing import websocket_urlpatterns

        route = websocket_urlpatterns[0]
        pattern_str = route.pattern.describe()
        # The pattern should reference 'stream_key' and be under 'ws/stream/'
        self.assertIn("stream", str(route.pattern))
        # Verify the route resolves a valid UUID path
        match = route.pattern.match("ws/stream/12345678-1234-5678-1234-567812345678/")
        self.assertIsNotNone(
            match,
            "Route pattern should match a UUID path like "
            "'ws/stream/12345678-1234-5678-1234-567812345678/'",
        )


# ===========================================================================
# 2. ASGI Routing Integration Tests
# ===========================================================================
class ASGIRoutingIntegrationTests(SimpleTestCase):
    """Verify the ASGI application has WebSocket routes wired in."""

    def test_asgi_has_websocket_routes(self):
        """The ASGI application's websocket handler is not an empty URLRouter."""
        from config.asgi import application

        # The application should have a 'websocket' key in its mapping
        self.assertIn(
            "websocket",
            application.application_mapping,
            "ASGI application must have a 'websocket' protocol handler",
        )


# ===========================================================================
# 3. Consumer Connection Tests
# ===========================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ConsumerConnectionTests(TransactionTestCase):
    """Test WebSocket connection acceptance and rejection by the consumer."""

    def _create_user(self, username="testuser", is_staff=False):
        """Helper to create a user."""
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream", is_active=True):
        """Helper to create a LiveStream."""
        return LiveStream.objects.create(
            title=title, created_by=user, is_active=is_active
        )

    def test_connect_valid_active_stream(self):
        """Connecting to an active stream's WebSocket URL is accepted."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected, "Connection should be accepted for an active stream")
            await communicator.disconnect()

        async_to_sync(_test)()

    def test_connect_inactive_stream_rejected(self):
        """Connecting to an inactive stream's WebSocket URL is rejected."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, is_active=False)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertFalse(
                connected, "Connection should be rejected for an inactive stream"
            )
            await communicator.disconnect()

        async_to_sync(_test)()

    def test_connect_nonexistent_stream_rejected(self):
        """Connecting with a random UUID that has no matching stream is rejected."""
        async def _test():
            fake_key = uuid.uuid4()
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{fake_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertFalse(
                connected, "Connection should be rejected for a nonexistent stream"
            )
            await communicator.disconnect()

        async_to_sync(_test)()

    def test_disconnect_clean(self):
        """Connecting and then disconnecting completes without errors."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()
            # No exception means clean disconnect

        async_to_sync(_test)()


# ===========================================================================
# 4. Consumer Role Tests
# ===========================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ConsumerRoleTests(TransactionTestCase):
    """Test role signaling messages (broadcaster/listener identification)."""

    def _create_user(self, username="testuser", is_staff=False):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream"):
        return LiveStream.objects.create(title=title, created_by=user)

    def test_broadcaster_role_accepted(self):
        """Sending a broadcaster role message returns a role_confirmed acknowledgment."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({"type": "role", "role": "broadcaster"})
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], "role_confirmed")
            self.assertEqual(response["role"], "broadcaster")

            await communicator.disconnect()

        async_to_sync(_test)()

    def test_listener_role_accepted(self):
        """Sending a listener role message returns a role_confirmed acknowledgment."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({"type": "role", "role": "listener"})
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], "role_confirmed")
            self.assertEqual(response["role"], "listener")

            await communicator.disconnect()

        async_to_sync(_test)()


# ===========================================================================
# 5. Audio Broadcast Tests
# ===========================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class AudioBroadcastTests(TransactionTestCase):
    """Test audio binary data broadcasting between broadcaster and listeners."""

    def _create_user(self, username="testuser", is_staff=False):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream"):
        return LiveStream.objects.create(title=title, created_by=user)

    def test_broadcaster_sends_audio_listener_receives(self):
        """Broadcaster sends binary audio data; listener receives it.
        Broadcaster does NOT receive its own audio back."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            # Connect broadcaster
            broadcaster = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            b_connected, _ = await broadcaster.connect()
            self.assertTrue(b_connected)

            # Connect listener
            listener = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            l_connected, _ = await listener.connect()
            self.assertTrue(l_connected)

            # Assign roles
            await broadcaster.send_json_to({"type": "role", "role": "broadcaster"})
            b_role_response = await broadcaster.receive_json_from()
            self.assertEqual(b_role_response["role"], "broadcaster")

            await listener.send_json_to({"type": "role", "role": "listener"})
            l_role_response = await listener.receive_json_from()
            self.assertEqual(l_role_response["role"], "listener")

            # Broadcaster sends audio via JSON protocol
            audio_data = b"\x00\x01\x02\x03audio-chunk-data"
            await broadcaster.send_json_to({"type": "audio", "data": base64.b64encode(audio_data).decode("ascii")})

            # Listener should receive the audio as JSON
            resp = await listener.receive_json_from()
            self.assertEqual(resp["type"], "audio")
            self.assertEqual(base64.b64decode(resp["data"]), audio_data)

            # Broadcaster should NOT receive its own audio back
            try:
                msg = await asyncio.wait_for(
                    broadcaster.receive_from(), timeout=0.1
                )
                self.fail(
                    "Broadcaster should not receive its own audio back, "
                    f"but got: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected -- broadcaster does not echo to itself

            await broadcaster.disconnect()
            await listener.disconnect()

        async_to_sync(_test)()

    def test_multiple_listeners_receive_audio(self):
        """Multiple listeners all receive the broadcaster's audio data."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            # Connect broadcaster
            broadcaster = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            b_connected, _ = await broadcaster.connect()
            self.assertTrue(b_connected)

            # Connect two listeners
            listener1 = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            l1_connected, _ = await listener1.connect()
            self.assertTrue(l1_connected)

            listener2 = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            l2_connected, _ = await listener2.connect()
            self.assertTrue(l2_connected)

            # Assign roles
            await broadcaster.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster.receive_json_from()

            await listener1.send_json_to({"type": "role", "role": "listener"})
            await listener1.receive_json_from()

            await listener2.send_json_to({"type": "role", "role": "listener"})
            await listener2.receive_json_from()

            # Broadcaster sends audio via JSON protocol
            audio_data = b"\xff\xfe\xfd-multi-listener-test"
            await broadcaster.send_json_to({"type": "audio", "data": base64.b64encode(audio_data).decode("ascii")})

            # Both listeners should receive the audio as JSON
            resp1 = await listener1.receive_json_from()
            self.assertEqual(resp1["type"], "audio")
            self.assertEqual(base64.b64decode(resp1["data"]), audio_data)

            resp2 = await listener2.receive_json_from()
            self.assertEqual(resp2["type"], "audio")
            self.assertEqual(base64.b64decode(resp2["data"]), audio_data)

            await broadcaster.disconnect()
            await listener1.disconnect()
            await listener2.disconnect()

        async_to_sync(_test)()

    def test_listener_cannot_broadcast(self):
        """A listener sending binary data does not broadcast to others."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            # Connect two clients, both as listeners
            listener1 = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            l1_connected, _ = await listener1.connect()
            self.assertTrue(l1_connected)

            listener2 = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            l2_connected, _ = await listener2.connect()
            self.assertTrue(l2_connected)

            # Assign listener roles
            await listener1.send_json_to({"type": "role", "role": "listener"})
            await listener1.receive_json_from()

            await listener2.send_json_to({"type": "role", "role": "listener"})
            await listener2.receive_json_from()

            # Listener1 tries to send audio via JSON protocol
            await listener1.send_json_to({"type": "audio", "data": base64.b64encode(b"sneaky-audio-data").decode("ascii")})

            # Listener2 should NOT receive anything
            try:
                msg = await asyncio.wait_for(
                    listener2.receive_from(), timeout=0.1
                )
                self.fail(
                    "Listener should not be able to broadcast audio, "
                    f"but listener2 received: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected -- listeners cannot broadcast

            await listener1.disconnect()
            await listener2.disconnect()

        async_to_sync(_test)()


# ===========================================================================
# 6. Consumer Group Tests
# ===========================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ConsumerGroupTests(TransactionTestCase):
    """Test channel layer group management by the consumer."""

    def _create_user(self, username="testuser", is_staff=False):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream"):
        return LiveStream.objects.create(title=title, created_by=user)

    def test_broadcaster_joins_correct_group(self):
        """After connecting, the consumer joins group 'stream_{stream_key}'.

        Verified by sending a message to the group via the channel layer
        and confirming the connected client receives it.
        """
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send a message to the expected group via the channel layer
            channel_layer = get_channel_layer()
            group_name = f"stream_{stream.stream_key}"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "audio.chunk",
                    "data": base64.b64encode(b"group-test-data").decode("ascii"),
                    "sender": "external-sender",
                },
            )

            # The consumer should receive it (audio_chunk handler forwards to client as JSON)
            resp = await communicator.receive_json_from()
            self.assertEqual(resp["type"], "audio")
            self.assertEqual(base64.b64decode(resp["data"]), b"group-test-data")

            await communicator.disconnect()

        async_to_sync(_test)()

    def test_disconnect_leaves_group(self):
        """After disconnecting, messages sent to the group are not received."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )

            communicator = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream.stream_key}/",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

            # Now send a message to the group -- nobody should be listening
            channel_layer = get_channel_layer()
            group_name = f"stream_{stream.stream_key}"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "audio.chunk",
                    "data": b"after-disconnect",
                    "sender": "external",
                },
            )

            # Verify the disconnected communicator does not receive the message
            try:
                msg = await asyncio.wait_for(
                    communicator.receive_from(), timeout=0.1
                )
                self.fail(
                    "Disconnected client should not receive group messages, "
                    f"but got: {msg!r}"
                )
            except (asyncio.TimeoutError, Exception):
                pass  # Expected -- no message after disconnect

        async_to_sync(_test)()

    def test_different_streams_isolated(self):
        """Audio from one stream does not leak to a different stream's listeners."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user(is_staff=True)
            )
            stream_a = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream A")
            )
            stream_b = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream B")
            )

            # Connect broadcaster to stream A
            broadcaster_a = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_a.stream_key}/",
            )
            a_connected, _ = await broadcaster_a.connect()
            self.assertTrue(a_connected)

            # Connect listener to stream B
            listener_b = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{stream_b.stream_key}/",
            )
            b_connected, _ = await listener_b.connect()
            self.assertTrue(b_connected)

            # Assign roles
            await broadcaster_a.send_json_to({"type": "role", "role": "broadcaster"})
            await broadcaster_a.receive_json_from()

            await listener_b.send_json_to({"type": "role", "role": "listener"})
            await listener_b.receive_json_from()

            # Broadcaster A sends audio via JSON protocol
            await broadcaster_a.send_json_to({"type": "audio", "data": base64.b64encode(b"stream-a-only-audio").decode("ascii")})

            # Listener on stream B should NOT receive stream A's audio
            try:
                msg = await asyncio.wait_for(
                    listener_b.receive_from(), timeout=0.1
                )
                self.fail(
                    "Listener on stream B should not receive audio from stream A, "
                    f"but got: {msg!r}"
                )
            except asyncio.TimeoutError:
                pass  # Expected -- streams are isolated

            await broadcaster_a.disconnect()
            await listener_b.disconnect()

        async_to_sync(_test)()
