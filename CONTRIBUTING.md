# Contributing to Masjid Audio Library

Thank you for your interest in contributing. This document explains the workflow and conventions we follow so that collaboration stays smooth.

## Branching Workflow

We use a **feature-branch** workflow based on `main`.

1. **`main`** is the stable branch. Never push directly to `main`.
2. Create a feature branch from `main` for every piece of work:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/short-description
   ```
3. Branch naming conventions:
   - `feature/<description>` -- new functionality
   - `fix/<description>` -- bug fixes
   - `docs/<description>` -- documentation changes
   - `chore/<description>` -- tooling, config, dependency updates
4. Keep branches focused. One branch = one logical change.

## Commit Conventions

Write clear, descriptive commit messages. We follow a lightweight conventional format:

```
<type>: <short summary>

<optional body explaining why, not what>
```

**Types:**
- `feat` -- a new feature
- `fix` -- a bug fix
- `docs` -- documentation only
- `style` -- formatting, no logic change
- `refactor` -- restructuring without changing behavior
- `test` -- adding or updating tests
- `chore` -- build, config, dependency changes

**Examples:**
```
feat: add tag filtering to recordings list view
fix: prevent duplicate tags on a single recording
docs: update roadmap with Phase 3 details
```

Keep the summary line under 72 characters. Use the body for additional context when needed.

## Pull Request Expectations

1. **Open a PR** from your feature branch into `main`.
2. **Title** should follow the same `<type>: <summary>` format as commits.
3. **Description** must include:
   - What the PR does and why
   - How to test the changes
   - Any related issues (reference with `#<issue-number>`)
4. **Keep PRs small and reviewable.** If a change is large, break it into smaller PRs.
5. **All checks must pass** before merging (once CI is set up).
6. **Request at least one review** before merging.
7. **Squash and merge** is the preferred merge strategy.

## Code Style

- Follow PEP 8 for Python code.
- Use Django conventions for project structure and naming.
- Write docstrings for public functions and classes.
- Keep functions focused -- if a function does too many things, split it up.

## Questions?

If you are unsure about anything, open an issue or reach out to the maintainers before starting work. It is always better to align on approach before writing code.
