# Feature List

A detailed description of all planned features for the Masjid Audio Library.

---

## 1. Recording Management (Admin)

### 1.1 Upload Recordings
Administrators can upload audio files through the admin interface. Each upload requires a title and audio file at minimum. Optional fields include description, speaker name, recording date, and tags.

### 1.2 Edit Recording Metadata
Administrators can update any field on an existing recording -- title, description, speaker, recording date, and tags -- without re-uploading the audio file.

### 1.3 Delete Recordings
Administrators can delete recordings. This removes the database entry and the associated audio file from storage.

---

## 2. Tag System

### 2.1 Create Tags
Administrators can create reusable tags representing topics. Each tag has a unique name and an auto-generated URL-friendly slug. Example tags: Prayer, Taqwa, Respecting Parents, Avoiding Sins, Ramadan.

### 2.2 Attach Tags to Recordings
Tags are attached to recordings via a many-to-many relationship. Each recording can have a maximum of 10 tags. Tags can be added or removed from a recording at any time.

### 2.3 Edit and Delete Tags
Administrators can rename or delete tags. Deleting a tag removes it from all associated recordings.

### 2.4 Browse Tags
Visitors can see a list of all available tags and click any tag to view the recordings associated with it.

---

## 3. Public Browsing

### 3.1 Recordings List
A paginated list of all recordings, ordered by most recent. Each entry shows the title, speaker, recording date, and associated tags.

### 3.2 Recording Detail Page
A dedicated page for each recording displaying full metadata (title, description, speaker, date, tags) and an embedded audio player.

### 3.3 Filter by Tag
Visitors can filter the recordings list by selecting one or more tags. Only recordings matching the selected tags are shown.

### 3.4 Filter by Speaker
Visitors can filter recordings by speaker name.

---

## 4. Audio Playback

### 4.1 In-Browser Player
Each recording detail page includes an HTML5 audio player that allows visitors to play, pause, seek, and adjust volume directly in the browser. No plugins or external libraries required.

### 4.2 Supported Formats
The platform will accept common audio formats (MP3, WAV, OGG). MP3 is the primary expected format.

---

## 5. Search

### 5.1 Search by Title
Visitors can enter a search query that matches against recording titles (partial, case-insensitive match).

### 5.2 Search by Description
The search also matches against recording descriptions.

### 5.3 Search by Speaker
The search also matches against speaker names.

### 5.4 Combined Search and Filter
Search results can be further narrowed by applying tag filters.

### 5.5 Full-Text Search (Future Enhancement)
Upgrade from basic `icontains` queries to PostgreSQL full-text search using `SearchVector` and `SearchRank` for more relevant results.

---

## 6. Live Stream

### 6.1 Live Stream Page
A dedicated page on the site for live audio or video streaming. This is separate from the recordings archive.

### 6.2 Configurable Stream Source
The live stream URL or embed code is stored in the database. Administrators can update it without modifying code or redeploying.

### 6.3 Active/Inactive State
The live stream page shows whether a stream is currently active. When inactive, visitors see a message indicating no live stream is available and are directed to browse recorded talks.

---

## 7. User Experience

### 7.1 Responsive Design
The site will be usable on desktop and mobile devices.

### 7.2 Clean Navigation
A simple navigation bar provides access to: Home, Browse Recordings, Tags, Live Stream.

### 7.3 Pagination
Long lists of recordings are paginated to keep pages fast and readable.

---

## 8. Administration

### 8.1 Django Admin Interface
Initial administration is done through Django's built-in admin interface with customized list views, filters, and search.

### 8.2 Custom Admin Dashboard (Future)
A dedicated admin dashboard outside of Django admin for a more streamlined upload and management experience.

---

## 9. Deployment and Infrastructure

### 9.1 Environment Configuration
All sensitive settings (secret key, database credentials, S3 keys) are managed via environment variables.

### 9.2 Cloud Storage
Audio files will migrate from local filesystem storage to Amazon S3 using `django-storages`.

### 9.3 PaaS Deployment
The application will be deployed to Render or a similar platform-as-a-service provider.

### 9.4 CI/CD (Future)
Automated testing and deployment pipeline triggered on merge to `main`.
