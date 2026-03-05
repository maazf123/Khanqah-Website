import mimetypes
import os
import re

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.urls import path, include, re_path
from django.conf import settings

from apps.core.views_home import HomeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("writings/", include("apps.writings.urls")),
    path("livestream/", include("apps.core.urls_livestream")),
    path("recordings/", include("apps.recordings.urls")),
    path("", HomeView.as_view(), name="home"),
]


def serve_media(request, path):
    """Serve media files with Range request support for audio/video seeking."""
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.isfile(file_path):
        raise Http404

    file_size = os.path.getsize(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    range_header = request.META.get("HTTP_RANGE", "")
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)

    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        f = open(file_path, "rb")
        f.seek(start)
        response = HttpResponse(f.read(length), status=206, content_type=content_type)
        response["Content-Length"] = length
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        return response

    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = file_size
    return response


if settings.DEBUG:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve_media),
    ]
