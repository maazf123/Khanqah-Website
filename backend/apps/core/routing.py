from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/stream/<uuid:stream_key>/", consumers.AudioStreamConsumer.as_asgi()),
]
