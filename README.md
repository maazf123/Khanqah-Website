# Khanqah Website

A web platform for a masjid/khanqah to host, organize, and share recorded Islamic talks and lectures. Think of it as a focused lecture archive for the Muslim community -- upload recordings, tag them by topic, and let visitors browse, search, and listen directly in the browser.

## Purpose

Many masajid deliver valuable talks on topics like prayer, taqwa, respecting parents, avoiding sins, Ramadan, and more. These recordings often end up scattered across phones, hard drives, and messaging groups. This platform gives them a permanent, organized, and accessible home.

Key capabilities:

- **Upload and manage** recorded talks (admin)
- **Tag recordings** with reusable topic labels (up to 10 per recording)
- **Browse and filter** talks by topic, speaker, or date
- **Search** by title, description, or speaker name
- **Play audio** directly in the browser
- **Live stream page** for embedding a live audio/video feed

## Technology Stack

| Layer       | Technology              |
|-------------|-------------------------|
| Backend     | Python / Django         |
| Database    | PostgreSQL              |
| Frontend    | Django Templates        |
| Environment | Docker / Docker Compose |
| Storage     | Local filesystem (S3 planned) |
| Deployment  | Render (planned)        |

## Project Structure

```
Khanqah-Website/
  backend/            Django project and apps
    config/           Django settings, root URL conf, WSGI/ASGI
    apps/
      recordings/     Core app -- audio uploads, metadata, playback
      tags/           Reusable tag system for categorizing recordings
      core/           Shared utilities (future)
  templates/          Django HTML templates
  static/             CSS, JS, images
  media/              Uploaded audio files (not committed)
  docs/               Architecture, roadmap, and feature documentation
  Dockerfile          Container image definition
  docker-compose.yml  Multi-container development setup
  .env.example        Template for environment variables
  .dockerignore       Files excluded from Docker builds
```

## Running with Docker

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Steps

1. **Clone the repository**

   ```bash
   git clone <repo-url>
   cd Khanqah-Website
   ```

2. **Copy environment variables**

   ```bash
   cp .env.example .env
   ```

3. **Build and start containers**

   ```bash
   docker compose up --build
   ```

4. **Access the application**

   Open [http://localhost:8000](http://localhost:8000) in your browser.

### Stopping the containers

```bash
docker compose down
```

To also remove the database volume:

```bash
docker compose down -v
```

## Getting Started (without Docker)

### Prerequisites

- Python 3.12+
- PostgreSQL 16+

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd Khanqah-Website

# Copy environment variables
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Run migrations and start the server
cd backend
python manage.py migrate
python manage.py runserver
```

## Deployment Plan

The application will be deployed to **Render** (or a similar PaaS). Audio file storage will migrate from the local filesystem to **Amazon S3** before production deployment. Details will be documented in `docs/roadmap.md` as the project matures.

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting any work. It covers:

- Branching workflow
- Commit message conventions
- Pull request expectations
- Code style guidelines

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
