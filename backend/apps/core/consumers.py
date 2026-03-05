import base64
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.core.models import LiveStream

# Cache the first WebM chunk (base64) per stream for late-joining listeners.
_init_segments = {}


class AudioStreamConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.stream_key = str(self.scope["url_route"]["kwargs"]["stream_key"])
        self.group_name = f"stream_{self.stream_key}"
        self.role = None

        stream = await self._get_active_stream(self.stream_key)
        if stream is None:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )
            if self.role == "broadcaster":
                _init_segments.pop(self.group_name, None)

    async def receive(self, text_data=None, bytes_data=None):
        # Everything is text — broadcaster sends JSON with base64 audio
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")

        if msg_type == "role":
            self.role = data.get("role")
            await self.send(text_data=json.dumps({
                "type": "role_confirmed",
                "role": self.role,
            }))
            # Send cached init segment to late-joining listeners
            if self.role == "listener" and self.group_name in _init_segments:
                await self.send(text_data=json.dumps({
                    "type": "audio",
                    "data": _init_segments[self.group_name],
                }))

        elif msg_type == "audio" and self.role == "broadcaster":
            audio_b64 = data.get("data", "")
            # Cache the first chunk (WebM init segment) for late joiners
            if self.group_name not in _init_segments:
                _init_segments[self.group_name] = audio_b64

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "audio.chunk",
                    "data": audio_b64,
                    "sender": self.channel_name,
                },
            )

    async def audio_chunk(self, event):
        if event.get("sender") != self.channel_name:
            await self.send(text_data=json.dumps({
                "type": "audio",
                "data": event["data"],
            }))

    @database_sync_to_async
    def _get_active_stream(self, stream_key):
        try:
            return LiveStream.objects.get(stream_key=stream_key, is_active=True)
        except LiveStream.DoesNotExist:
            return None
