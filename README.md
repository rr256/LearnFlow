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

## Running locally with Docker Compose

Requires Docker Desktop, or Docker Engine with the Compose plugin. `compose.yaml` currently defines
the `backend` service; PostgreSQL, ChromaDB, and the frontend join it with the code that uses them.

```bash
cp .env.example .env             # optional; documented defaults apply without it
docker compose up --build        # build and start
docker compose up --build -d     # same, in the background
docker compose logs -f backend   # follow backend logs
docker compose down              # stop, preserving named volumes
```

The API is then published on the loopback interface only:

```bash
curl http://127.0.0.1:8000/health   # {"status":"ok"}
```

`API_HOST` is fixed to `0.0.0.0` inside the container so the service accepts connections from the
host; `APP_ENV`, `APP_LOG_LEVEL`, and `API_PORT` come from your shell or `.env`, falling back to the
documented defaults. No `.env` file is ever copied into an image.

`docker compose down -v` deletes named volumes and is destructive. Do not use it as a routine stop
command. See [Docker strategy](docs/deployment/docker.md) for the full topology, image decisions, and
data rules.

## Running the backend directly

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m app.main                          # serves on API_HOST / API_PORT
python -m uvicorn app.main:app --reload      # reload workflow, own --host/--port
```

Python 3.14 is required. Before committing, run the
[local quality checks](docs/development/coding-standards.md#local-quality-checks).

## Project status

Documentation and architecture foundation, plus a minimal FastAPI backend foundation.

**Implemented**

- A FastAPI application served through a composition-root application factory.
- Validated startup configuration for `APP_ENV`, `APP_LOG_LEVEL`, `API_HOST`, and `API_PORT`.
- `GET /health`, an operational endpoint served outside `/api/v1`.
- A backend container image and a Docker Compose `backend` service. See
  [Docker strategy](docs/deployment/docker.md).
- Continuous integration on pull requests: backend tests, Ruff lint and format checks,
  documentation validation, and container build validation. See
  [CI/CD strategy](docs/deployment/ci-cd.md).

**Not implemented**

Learner features, database persistence, AI and RAG, the frontend, curriculum data, and external
integrations. Compose covers the backend only — there is no PostgreSQL, ChromaDB, or frontend
service yet. Nothing beyond the implemented items above should be inferred from the current
repository contents.
