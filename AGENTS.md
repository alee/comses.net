# CoMSES.Net Agent Guide

## Agent Operating Principles

This file defines mandatory rules for coding agents working in this repository.

Decision priority:

1. Security, correctness, and data integrity
2. Maintainability and readability
3. Consistency with existing patterns

General approach:

- Make minimal, focused changes
- Do not refactor unrelated code
- Prefer extending existing patterns over introducing new abstractions
- Avoid duplicate logic; centralize reusable behavior
- If requirements are ambiguous, choose the simplest correct solution and state assumptions or ask for more input
- Do not introduce new dependencies or architectural patterns without clear justification

## Domain Invariants

This platform manages scientific software artifacts and publication metadata. The following are non-negotiable:

- Published model releases are immutable archival objects
- Never modify published artifacts in place; create a new version
- DOI assignment is version-specific and must not be changed retroactively
- Citation metadata must remain accurate and stable for each published version
- Metadata is consumed by external systems; preserve schema integrity and avoid lossy transforms
- Review and publication transitions must be explicit, auditable, and safe to retry without side effects (idempotent)
- File storage and database state must remain consistent; avoid partial updates
- Never modify model-release storage directly; use the repository's release filesystem API so archival manifests, checksums, and database state remain consistent.
- Background tasks that affect publication or metadata must be safe to retry
- Permission checks must be enforced in the backend at object level
- Ensure consistent permission enforcement across views, APIs, and background tasks
- Default deny: do not expose restricted or unpublished content without explicit authorization

## Security and Engineering Baseline

- Validate and sanitize all external inputs at the serializer or form layer before reaching model or business logic
- Avoid raw SQL unless explicitly justified and reviewed
- Protect sensitive data; never expose secrets in code or responses
- Reuse existing permission and role-checking patterns
- When in doubt, choose the more secure implementation

## Backend Conventions (Django)

- Follow existing placement of domain logic; use models for model-specific invariants and dedicated modules for multi-model workflows.
- Put reusable or nontrivial query logic in QuerySet methods and expose via model managers using `as_manager()`
- Compose QuerySet methods at call sites; avoid constructing complex ORM queries inline
- Do not bypass ORM, serializers, or permissions without explicit justification
- Generate migrations; do not hand-write migration files unless required and always review auto-generated migrations before committing
- The Huey task queue runs `immediate: False`, so the consumer process does not auto-reload on code changes. After changing task code in `tasks.py`, restart the affected service before verifying behavior, do not assume a code change to a task took effect.

## Frontend Conventions (Vue)

- Frontend naming: Use `snake_case` for app entrypoints and API composable modules, `camelCase` for store modules, `PascalCase` for Vue component files, and lowercase or `kebab-case` for directories. Examples: apps/release_editor.ts, composables/api/release_editor.ts, stores/releaseEditor.ts, and components/release-editor/App.vue.
- Use Vue 3 Composition API with script setup
- Prefer Bootstrap utility classes before custom styling
- Keep API client logic in composables under `frontend/src/composables/api/`
- The Django REST API is not consistently transformed between snake_case and camelCase; `frontend/src/types.ts` has both conventions depending on whether a field is raw API response shape or a mapped view type. Check the existing type definition before assuming a field's casing.
- Be careful with date parsing assumptions from API responses

## Testing Expectations

- Add or update tests for bug fixes, behavior changes, and nontrivial logic.
- Prefer targeted test execution during development
- Use repository-standard containerized commands for running tests and tooling
- For targeted Django tests, run exactly: `make test TEST_ARGS=<dotted.test.path>`
- `make test` destroys and reinitializes the database from scratch on every run (via `deploy/test.sh`); never run it against a database whose state needs to be preserved
- If `make test` fails in WSL with Docker daemon or credential-helper errors, prompt the user to start Docker Desktop for Windows and confirm before retrying

## Environment and Commands

- Use Docker Compose workflow for local development
- Store agent runbooks, plans, checkpoints, and handoff artifacts in `docs/agents/`
- Keep reusable templates in `docs/agents/templates/`
- See `docs/agents/commands.md` for a minimal command index used by humans and agents
- Prefer repo-root-relative paths for links (for example, `docs/agents/commands.md`), not machine-absolute paths (for example, `/home/...`).
- Keep operational runbooks, backup and restore procedures, and full command catalogs in project docs
- Keep this file policy-focused; avoid long procedural walkthroughs
- `CLAUDE.md` should import this file (`@AGENTS.md`) rather than duplicate it, to avoid the two drifting apart
