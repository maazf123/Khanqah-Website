# Architecture

This document describes the planned system architecture for the Masjid Audio Library.

## Overview

The Masjid Audio Library is a Django-based web application backed by PostgreSQL. It serves as a lecture archive where administrators upload and tag audio recordings, and visitors browse, search, and listen to them in the browser. A dedicated live stream page allows embedding a real-time audio or video feed.

## Data Model

### Recordings

Each recording represents a single uploaded talk or lecture.

| Field            | Type          | Notes                                      |
|------------------|---------------|--------------------------------------------|
| id               | UUID / Auto   | Primary key                                |
| title            | CharField     | Required, max 255 characters               |
| description      | TextField     | Optional, longer description of the talk   |
| speaker          | CharField     | Name of the speaker                        |
| audio_file       | FileField     | The uploaded audio file                    |
| recording_date   | DateField     | Date the talk was originally recorded      |
| tags             | ManyToMany    | Relationship to Tag model (max 10 per recording) |
| uploaded_at      | DateTimeField | Auto-set on creation                       |

### Tags

Tags are reusable labels used to categorize recordings by topic.

| Field | Type      | Notes                        |
|-------|-----------|------------------------------|
| id    | Auto      | Primary key                  |
| name  | CharField | Unique, max 100 characters   |
| slug  | SlugField | URL-friendly version of name |

- Tags are created independently and attached to recordings via a many-to-many relationship.
- A single recording can have **at most 10 tags**.
- Example tags: Prayer, Taqwa, Respecting Parents, Avoiding Sins, Ramadan.

### Live Stream Configuration

A simple model (or site-wide setting) to store live stream information.

| Field     | Type      | Notes                                  |
|-----------|-----------|----------------------------------------|
| title     | CharField | Display title for the stream           |
| embed_url | URLField  | URL or embed code for the live stream  |
| is_active | Boolean   | Whether the stream is currently live   |

## Application Structure

```
backend/
  config/          Project-level settings, root URLs, WSGI/ASGI entry points
  apps/
    recordings/    Models, views, forms, and services for audio recordings
    tags/          Tag model and views for listing/filtering tags
    core/          Shared utilities, context processors, base templates
```

## Features by Domain

### Search

Users can search recordings by:

- **Title** -- partial text match
- **Description** -- partial text match
- **Speaker** -- partial text match
- **Tags** -- filter by one or more tags

Search will initially use Django ORM queries. Full-text search via PostgreSQL `SearchVector` may be added later.

### Admin Features

Administrators (Django staff users) will be able to:

- Upload new recordings with metadata
- Create, edit, and delete tags
- Attach or remove tags from recordings
- Manage live stream configuration

The Django admin interface will be used initially, with a custom admin dashboard planned for later phases.

### Audio Playback

Recordings are played directly in the browser using the HTML5 `<audio>` element. No external player libraries are required initially.

### Live Stream

A dedicated page will embed a live audio or video stream. The embed URL is stored in the database and can be updated by admins without code changes. When no stream is active, the page displays an appropriate message.

## Storage Strategy

- **Phase 1:** Audio files stored on the local filesystem via Django's `MEDIA_ROOT`.
- **Future:** Migrate to Amazon S3 using `django-storages` and `boto3`. The `FileField` storage backend will be swapped without changing application code.

## Deployment Architecture (Planned)

- **Platform:** Render (or similar PaaS)
- **Web server:** Gunicorn behind Render's reverse proxy
- **Database:** Managed PostgreSQL (Render or external)
- **Static files:** WhiteNoise or S3
- **Media files:** S3
