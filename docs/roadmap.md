# Roadmap

Development is organized into sequential phases. Each phase builds on the previous one.

## Phase 1 -- Repository Initialization and Architecture Planning

- [x] Initialize repository structure
- [x] Create placeholder files for all apps
- [x] Write architecture documentation
- [x] Write roadmap and feature list
- [x] Set up collaboration files (README, CONTRIBUTING, LICENSE)
- [x] Create .gitignore, .env.example, docker-compose placeholder

## Phase 2 -- Database Models

- [ ] Define the `Recording` model (title, description, speaker, audio file, recording date, timestamps)
- [ ] Define the `Tag` model (name, slug)
- [ ] Establish many-to-many relationship between recordings and tags
- [ ] Enforce maximum of 10 tags per recording
- [ ] Create and run initial migrations
- [ ] Write model tests

## Phase 3 -- Admin Interface

- [ ] Register models with Django admin
- [ ] Customize admin list views (search, filters, display columns)
- [ ] Enable audio file upload through admin
- [ ] Enable tag creation and management through admin
- [ ] Enable attaching tags to recordings through admin
- [ ] Test admin workflows end-to-end

## Phase 4 -- Public Site

- [ ] Create base template with site layout and navigation
- [ ] Build recordings list page with pagination
- [ ] Build single recording detail page with audio player
- [ ] Build tag listing page
- [ ] Implement tag filtering (browse recordings by tag)
- [ ] Add HTML5 audio player to detail page
- [ ] Style pages with CSS

## Phase 5 -- Search Functionality

- [ ] Add search form to the public site
- [ ] Implement search by title
- [ ] Implement search by description
- [ ] Implement search by speaker
- [ ] Combine search with tag filtering
- [ ] Consider PostgreSQL full-text search for improved results

## Phase 6 -- Live Streaming Page

- [ ] Create live stream configuration model (or site settings)
- [ ] Build dedicated live stream page
- [ ] Embed live stream via stored URL/embed code
- [ ] Show active/inactive state
- [ ] Allow admins to update stream URL without code changes

## Phase 7 -- Deployment

- [ ] Configure production settings (environment variables, allowed hosts, HTTPS)
- [ ] Set up PostgreSQL on hosting platform
- [ ] Migrate audio storage to Amazon S3
- [ ] Configure static file serving (WhiteNoise or S3)
- [ ] Deploy to Render (or chosen PaaS)
- [ ] Set up CI/CD pipeline
- [ ] Monitor and iterate
