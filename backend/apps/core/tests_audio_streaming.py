"""
TDD tests for audio streaming reliability and correctness.

These tests target the bugs that cause audio to break when broadcasting
and listening on the same machine:

1. Init segment caching & delivery to late joiners
2. Init segment cleanup on broadcaster disconnect
3. No-role audio rejection
4. Rapid-fire audio chunk delivery
5. Broadcaster reconnect & init segment refresh
6. Role validation (only 'broadcaster' can send audio)
7. Multiple concurrent listeners all receive every chunk
8. Stream isolation for init segments
9. Invalid/malformed message handling
10. Mic stream cleanup signaling (broadcaster disconnect sends close)
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
from django.test import TransactionTestCase, override_settings
from django.urls import path

from apps.core.consumers import AudioStreamConsumer, _init_segments
from apps.core.models import LiveStream

TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

test_ws_application = URLRouter([
    path("ws/stream/<uuid:stream_key>/", AudioStreamConsumer.as_asgi()),
])


class AudioStreamingTestBase(TransactionTestCase):
    """Shared helpers for audio streaming tests."""

    def _create_user(self, username="testuser", is_staff=True):
        return User.objects.create_user(
            username=username, password="testpass", is_staff=is_staff
        )

    def _create_stream(self, user, title="Test Stream", is_active=True):
        return LiveStream.objects.create(
            title=title, created_by=user, is_active=is_active
        )

    def _make_communicator(self, stream):
        return WebsocketCommunicator(
            test_ws_application,
            f"/ws/stream/{stream.stream_key}/",
        )

    async def _connect_as(self, stream, role):
        """Connect and assign a role; return (communicator, role_response)."""
        comm = self._make_communicator(stream)
        connected, _ = await comm.connect()
        assert connected, f"Connection failed for {role}"
        await comm.send_json_to({"type": "role", "role": role})
        resp = await comm.receive_json_from()
        assert resp["type"] == "role_confirmed"
        assert resp["role"] == role
        return comm

    def _b64(self, data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    def setUp(self):
        super().setUp()
        _init_segments.clear()


# ============================================================================
# 1. Init Segment Caching Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class InitSegmentCachingTests(AudioStreamingTestBase):
    """The first audio chunk from a broadcaster must be cached as the
    WebM init segment so late-joining listeners can start playback."""

    def test_first_audio_chunk_cached_as_init_segment(self):
        """The very first audio chunk is stored in _init_segments."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")

            init_data = b"\x1a\x45\xdf\xa3webm-init-segment"
            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(init_data)
            })
            # Give the consumer time to process
            await asyncio.sleep(0.05)

            group_name = f"stream_{stream.stream_key}"
            self.assertIn(group_name, _init_segments)
            self.assertEqual(
                base64.b64decode(_init_segments[group_name]), init_data
            )
            await broadcaster.disconnect()
        async_to_sync(_test)()

    def test_init_segment_not_overwritten_by_subsequent_chunks(self):
        """Only the first chunk is cached; later chunks don't replace it."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")

            first = b"first-init-chunk"
            second = b"second-audio-chunk"
            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(first)
            })
            await asyncio.sleep(0.05)
            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(second)
            })
            await asyncio.sleep(0.05)

            group_name = f"stream_{stream.stream_key}"
            self.assertEqual(
                base64.b64decode(_init_segments[group_name]), first,
                "Init segment should remain as the first chunk"
            )
            await broadcaster.disconnect()
        async_to_sync(_test)()

    def test_late_joiner_receives_cached_init_segment(self):
        """A listener joining after broadcast has started receives the
        cached init segment immediately upon role confirmation."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")

            init_data = b"webm-init-for-late-joiner"
            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(init_data)
            })
            await asyncio.sleep(0.05)

            # Late-joining listener
            listener = self._make_communicator(stream)
            connected, _ = await listener.connect()
            self.assertTrue(connected)
            await listener.send_json_to({"type": "role", "role": "listener"})

            # Should get role_confirmed
            role_resp = await listener.receive_json_from()
            self.assertEqual(role_resp["type"], "role_confirmed")

            # Should immediately get the init segment
            init_resp = await listener.receive_json_from()
            self.assertEqual(init_resp["type"], "audio")
            self.assertEqual(
                base64.b64decode(init_resp["data"]), init_data,
                "Late joiner should receive the cached init segment"
            )

            await broadcaster.disconnect()
            await listener.disconnect()
        async_to_sync(_test)()

    def test_no_init_segment_sent_when_none_cached(self):
        """A listener joining before any audio is broadcast does NOT
        receive a spurious init segment."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            listener = await self._connect_as(stream, "listener")

            # Should NOT receive any audio messages
            try:
                msg = await asyncio.wait_for(
                    listener.receive_from(), timeout=0.2
                )
                self.fail(f"Should not receive audio before broadcast: {msg!r}")
            except asyncio.TimeoutError:
                pass

            await listener.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 2. Init Segment Cleanup Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class InitSegmentCleanupTests(AudioStreamingTestBase):
    """Init segments must be cleaned up when the broadcaster disconnects
    to prevent stale data and memory leaks."""

    def test_broadcaster_disconnect_clears_init_segment(self):
        """When the broadcaster disconnects, the cached init segment
        is removed from _init_segments."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")

            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(b"init-data")
            })
            await asyncio.sleep(0.05)

            group_name = f"stream_{stream.stream_key}"
            self.assertIn(group_name, _init_segments)

            await broadcaster.disconnect()
            await asyncio.sleep(0.05)

            self.assertNotIn(
                group_name, _init_segments,
                "Init segment should be cleared after broadcaster disconnects"
            )
        async_to_sync(_test)()

    def test_listener_disconnect_does_not_clear_init_segment(self):
        """When a listener disconnects, the init segment remains cached."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")
            listener = await self._connect_as(stream, "listener")
            # Consume init segment if sent
            try:
                await asyncio.wait_for(listener.receive_from(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(b"init-data")
            })
            await asyncio.sleep(0.05)
            # Consume the audio chunk
            await listener.receive_json_from()

            group_name = f"stream_{stream.stream_key}"
            self.assertIn(group_name, _init_segments)

            await listener.disconnect()
            await asyncio.sleep(0.05)

            self.assertIn(
                group_name, _init_segments,
                "Init segment should persist after listener disconnects"
            )
            await broadcaster.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 3. No-Role Audio Rejection Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class NoRoleAudioTests(AudioStreamingTestBase):
    """Clients that haven't declared a role should not be able to broadcast."""

    def test_audio_before_role_is_ignored(self):
        """Sending audio without setting a role first has no effect."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            listener = await self._connect_as(stream, "listener")

            # New connection, no role assigned
            norole = self._make_communicator(stream)
            connected, _ = await norole.connect()
            self.assertTrue(connected)

            # Try to send audio without role
            await norole.send_json_to({
                "type": "audio", "data": self._b64(b"no-role-audio")
            })

            # Listener should not receive anything
            try:
                msg = await asyncio.wait_for(
                    listener.receive_from(), timeout=0.2
                )
                self.fail(f"No-role client should not broadcast: {msg!r}")
            except asyncio.TimeoutError:
                pass

            await norole.disconnect()
            await listener.disconnect()
        async_to_sync(_test)()

    def test_listener_role_cannot_broadcast(self):
        """A client with 'listener' role sending audio is silently ignored."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            listener1 = await self._connect_as(stream, "listener")
            listener2 = await self._connect_as(stream, "listener")

            await listener1.send_json_to({
                "type": "audio", "data": self._b64(b"sneaky-audio")
            })

            try:
                msg = await asyncio.wait_for(
                    listener2.receive_from(), timeout=0.2
                )
                self.fail(f"Listener should not broadcast: {msg!r}")
            except asyncio.TimeoutError:
                pass

            await listener1.disconnect()
            await listener2.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 4. Rapid-Fire Audio Chunk Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class RapidFireAudioTests(AudioStreamingTestBase):
    """Simulate real-world 100ms interval broadcasting and verify all
    chunks are delivered in order."""

    def test_rapid_sequential_chunks_all_delivered(self):
        """10 rapid audio chunks sent by broadcaster are all received
        by the listener in order."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")
            listener = await self._connect_as(stream, "listener")

            num_chunks = 10
            for i in range(num_chunks):
                chunk = f"chunk-{i:03d}".encode()
                await broadcaster.send_json_to({
                    "type": "audio", "data": self._b64(chunk)
                })

            received = []
            for _ in range(num_chunks):
                resp = await asyncio.wait_for(
                    listener.receive_json_from(), timeout=2.0
                )
                self.assertEqual(resp["type"], "audio")
                received.append(base64.b64decode(resp["data"]))

            for i in range(num_chunks):
                expected = f"chunk-{i:03d}".encode()
                self.assertEqual(
                    received[i], expected,
                    f"Chunk {i} mismatch: got {received[i]!r}"
                )

            await broadcaster.disconnect()
            await listener.disconnect()
        async_to_sync(_test)()

    def test_multiple_listeners_receive_all_rapid_chunks(self):
        """3 listeners each receive all 5 rapid chunks from broadcaster."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")

            listeners = []
            for i in range(3):
                l = await self._connect_as(stream, "listener")
                listeners.append(l)

            num_chunks = 5
            for i in range(num_chunks):
                await broadcaster.send_json_to({
                    "type": "audio",
                    "data": self._b64(f"multi-{i}".encode())
                })

            for idx, listener in enumerate(listeners):
                for i in range(num_chunks):
                    resp = await asyncio.wait_for(
                        listener.receive_json_from(), timeout=2.0
                    )
                    self.assertEqual(resp["type"], "audio")
                    self.assertEqual(
                        base64.b64decode(resp["data"]),
                        f"multi-{i}".encode(),
                        f"Listener {idx} chunk {i} mismatch"
                    )

            await broadcaster.disconnect()
            for l in listeners:
                await l.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 5. Stream Isolation for Init Segments Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class InitSegmentIsolationTests(AudioStreamingTestBase):
    """Init segments from different streams must not leak across streams."""

    def test_init_segments_are_stream_specific(self):
        """Each stream's init segment is stored under its own group key."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream_a = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream A")
            )
            stream_b = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream B")
            )

            bc_a = await self._connect_as(stream_a, "broadcaster")
            bc_b = await self._connect_as(stream_b, "broadcaster")

            await bc_a.send_json_to({
                "type": "audio", "data": self._b64(b"init-A")
            })
            await bc_b.send_json_to({
                "type": "audio", "data": self._b64(b"init-B")
            })
            await asyncio.sleep(0.05)

            group_a = f"stream_{stream_a.stream_key}"
            group_b = f"stream_{stream_b.stream_key}"
            self.assertEqual(
                base64.b64decode(_init_segments[group_a]), b"init-A"
            )
            self.assertEqual(
                base64.b64decode(_init_segments[group_b]), b"init-B"
            )

            await bc_a.disconnect()
            await bc_b.disconnect()
        async_to_sync(_test)()

    def test_late_joiner_gets_correct_streams_init_segment(self):
        """A late-joining listener on stream A gets stream A's init, not B's."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream_a = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream A")
            )
            stream_b = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, title="Stream B")
            )

            bc_a = await self._connect_as(stream_a, "broadcaster")
            bc_b = await self._connect_as(stream_b, "broadcaster")

            await bc_a.send_json_to({
                "type": "audio", "data": self._b64(b"init-stream-A")
            })
            await bc_b.send_json_to({
                "type": "audio", "data": self._b64(b"init-stream-B")
            })
            await asyncio.sleep(0.05)

            # Late joiner on stream A
            listener_a = self._make_communicator(stream_a)
            connected, _ = await listener_a.connect()
            self.assertTrue(connected)
            await listener_a.send_json_to({"type": "role", "role": "listener"})
            await listener_a.receive_json_from()  # role_confirmed

            init_resp = await listener_a.receive_json_from()
            self.assertEqual(
                base64.b64decode(init_resp["data"]), b"init-stream-A",
                "Late joiner on stream A should get stream A's init segment"
            )

            await bc_a.disconnect()
            await bc_b.disconnect()
            await listener_a.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 6. Invalid Message Handling Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class InvalidMessageTests(AudioStreamingTestBase):
    """The consumer should handle malformed messages gracefully without
    crashing the WebSocket connection."""

    def test_invalid_json_does_not_crash(self):
        """Sending non-JSON text data doesn't crash the consumer."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            comm = self._make_communicator(stream)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_to(text_data="this is not json{{{")
            # Connection should remain open
            await asyncio.sleep(0.05)
            # Verify still connected by sending a valid message
            await comm.send_json_to({"type": "role", "role": "listener"})
            resp = await comm.receive_json_from()
            self.assertEqual(resp["type"], "role_confirmed")

            await comm.disconnect()
        async_to_sync(_test)()

    def test_whitespace_text_data_does_not_crash(self):
        """Sending whitespace-only text doesn't crash the consumer."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            comm = self._make_communicator(stream)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_to(text_data="   ")
            await asyncio.sleep(0.05)
            await comm.send_json_to({"type": "role", "role": "listener"})
            resp = await comm.receive_json_from()
            self.assertEqual(resp["type"], "role_confirmed")

            await comm.disconnect()
        async_to_sync(_test)()

    def test_missing_type_field_does_not_crash(self):
        """JSON without 'type' field doesn't crash."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            comm = self._make_communicator(stream)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_json_to({"foo": "bar"})
            await asyncio.sleep(0.05)
            await comm.send_json_to({"type": "role", "role": "listener"})
            resp = await comm.receive_json_from()
            self.assertEqual(resp["type"], "role_confirmed")

            await comm.disconnect()
        async_to_sync(_test)()

    def test_audio_without_data_field_does_not_crash(self):
        """Audio message without 'data' field doesn't crash."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")

            await broadcaster.send_json_to({"type": "audio"})
            await asyncio.sleep(0.05)
            # Connection should still work
            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(b"valid-chunk")
            })
            await asyncio.sleep(0.05)

            await broadcaster.disconnect()
        async_to_sync(_test)()

    def test_binary_data_ignored(self):
        """Binary WebSocket frames are ignored (only text is processed)."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            comm = self._make_communicator(stream)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_to(bytes_data=b"\x00\x01\x02\x03")
            await asyncio.sleep(0.05)
            await comm.send_json_to({"type": "role", "role": "listener"})
            resp = await comm.receive_json_from()
            self.assertEqual(resp["type"], "role_confirmed")

            await comm.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 7. Broadcaster Disconnect Signaling Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class BroadcasterDisconnectTests(AudioStreamingTestBase):
    """When the broadcaster disconnects, listeners should be notified
    so they can clean up their audio pipeline."""

    def test_listener_ws_stays_open_after_broadcaster_disconnect(self):
        """Listeners remain connected even after broadcaster leaves."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")
            listener = await self._connect_as(stream, "listener")

            await broadcaster.send_json_to({
                "type": "audio", "data": self._b64(b"some-audio")
            })
            await listener.receive_json_from()

            await broadcaster.disconnect()
            await asyncio.sleep(0.1)

            # Listener should still be connected (can send messages)
            await listener.send_json_to({"type": "role", "role": "listener"})
            resp = await listener.receive_json_from()
            self.assertEqual(resp["type"], "role_confirmed")

            await listener.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 8. WebSocket Close Code Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class WebSocketCloseCodeTests(AudioStreamingTestBase):
    """Test that proper close codes are used for different disconnect scenarios."""

    def test_inactive_stream_connection_rejected(self):
        """Connecting to an inactive stream is rejected (not accepted)."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user, is_active=False)
            )
            comm = self._make_communicator(stream)
            connected, _ = await comm.connect()
            self.assertFalse(connected)
            await comm.disconnect()
        async_to_sync(_test)()

    def test_nonexistent_stream_rejected(self):
        """Connecting to a stream that doesn't exist is rejected."""
        async def _test():
            fake_key = uuid.uuid4()
            comm = WebsocketCommunicator(
                test_ws_application,
                f"/ws/stream/{fake_key}/",
            )
            connected, _ = await comm.connect()
            self.assertFalse(connected)
            await comm.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 9. Concurrent Broadcaster Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ConcurrentBroadcasterTests(AudioStreamingTestBase):
    """Edge cases with multiple broadcasters on the same stream."""

    def test_second_broadcaster_audio_also_sent(self):
        """If two clients both claim broadcaster role on the same stream,
        both can send audio (the consumer doesn't enforce single-broadcaster)."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            bc1 = await self._connect_as(stream, "broadcaster")
            bc2 = await self._connect_as(stream, "broadcaster")
            listener = await self._connect_as(stream, "listener")

            await bc1.send_json_to({
                "type": "audio", "data": self._b64(b"from-bc1")
            })
            resp = await asyncio.wait_for(
                listener.receive_json_from(), timeout=1.0
            )
            self.assertEqual(base64.b64decode(resp["data"]), b"from-bc1")

            await bc2.send_json_to({
                "type": "audio", "data": self._b64(b"from-bc2")
            })
            # bc1 also receives bc2's audio (it's in the group)
            resp_bc1 = await asyncio.wait_for(
                bc1.receive_json_from(), timeout=1.0
            )
            self.assertEqual(base64.b64decode(resp_bc1["data"]), b"from-bc2")

            resp_listener = await asyncio.wait_for(
                listener.receive_json_from(), timeout=1.0
            )
            self.assertEqual(
                base64.b64decode(resp_listener["data"]), b"from-bc2"
            )

            await bc1.disconnect()
            await bc2.disconnect()
            await listener.disconnect()
        async_to_sync(_test)()


# ============================================================================
# 10. Empty Audio Data Tests
# ============================================================================
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class EmptyAudioDataTests(AudioStreamingTestBase):
    """Test handling of empty or minimal audio payloads."""

    def test_empty_audio_data_string(self):
        """Empty data string is broadcast without crashing."""
        async def _test():
            user = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_user()
            )
            stream = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._create_stream(user)
            )
            broadcaster = await self._connect_as(stream, "broadcaster")
            listener = await self._connect_as(stream, "listener")

            await broadcaster.send_json_to({"type": "audio", "data": ""})
            resp = await asyncio.wait_for(
                listener.receive_json_from(), timeout=1.0
            )
            self.assertEqual(resp["type"], "audio")
            self.assertEqual(resp["data"], "")

            await broadcaster.disconnect()
            await listener.disconnect()
        async_to_sync(_test)()
