# LearnFlow
An AI-powered learning platform with personalized study planning, RAG, adaptive assessments, and intelligent learning agents.

GATE Computer Science is the first curated learning program, not a fixed product boundary.

## Documentation

The [`docs/`](docs/) directory is the authoritative source of truth for this project.

**Start here:** [docs/00-project-context.md](docs/00-project-context.md) — the mandatory entry point and master index. Read it before proposing or implementing any change.

| Where to look | For |
| --- | --- |
| [Documentation home](docs/README.md) | Navigation across the whole documentation set |
| [Architecture decision register](docs/architecture/decisions.md) | Approved and deferred decisions at a glance |
| [Architecture Decision Records](docs/adr/) | Durable rationale, alternatives, and consequences |
| [Product vision](docs/vision/vision.md) and [MVP scope](docs/requirements/mvp.md) | What LearnFlow is and what the first release covers |
| [Documentation standards](docs/development/documentation-standards.md) | How this documentation is written and maintained |

## Project status

Documentation and architecture foundation, plus a minimal FastAPI backend foundation.

**Implemented**

- A FastAPI application served through a composition-root application factory.
- Validated startup configuration for `APP_ENV`, `APP_LOG_LEVEL`, `API_HOST`, and `API_PORT`.
- `GET /health`, an operational endpoint served outside `/api/v1`.

**Not implemented**

Learner features, database persistence, Docker, AI and RAG, the frontend, curriculum data, and
external integrations. Nothing beyond the three items above should be inferred from the current
repository contents.
