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
the `backend` and `postgres` services; ChromaDB and the frontend join them with the code that uses
them.

```bash
cp .env.example .env             # required: DATABASE_URL has no default
docker compose up --build        # build and start
docker compose up --build -d     # same, in the background
docker compose up -d postgres    # database only, for host-side Alembic or tests
docker compose logs -f backend   # follow backend logs
docker compose down              # stop, preserving named volumes
```

Apply the database schema once the services are up, then load the curated data. No step runs
automatically, and each refuses to run ahead of its predecessor:

```bash
cd backend
python -m alembic upgrade head                # create the tables
python -m scripts.seed_curriculum             # load the GATE CSE curriculum; safe to repeat
python -m scripts.seed_examination_schedule   # load the published GATE 2027 schedule; safe to repeat
python -m scripts.set_study_goal              # bind the local learner to both
```

The API is then published on the loopback interface only:

```bash
curl http://127.0.0.1:8000/health                       # {"status":"ok"}
curl http://127.0.0.1:8000/api/v1/curriculum/programs   # the seeded learning programs
```

`API_HOST` and `DATABASE_URL` are fixed inside the container — to `0.0.0.0` and to the `postgres`
service respectively — so the service accepts connections from the host and reaches the database by
its Compose name. `APP_ENV`, `APP_LOG_LEVEL`, `API_PORT`, and the `POSTGRES_*` credentials come from
your shell or `.env`, falling back to the documented defaults. No `.env` file is ever copied into an
image.

`docker compose down -v` deletes named volumes and is destructive — `postgres_data` holds your
learner data. Do not use it as a routine stop command. See
[Docker strategy](docs/deployment/docker.md) for the full topology, image decisions, and data rules.

## Running the backend directly

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m app.main                          # serves on API_HOST / API_PORT
python -m uvicorn app.main:app --reload      # reload workflow, own --host/--port
python -m alembic upgrade head               # apply the database schema
python -m scripts.seed_curriculum            # load the curated curriculum, idempotently
python -m scripts.seed_examination_schedule  # load the published examination schedule, idempotently
python -m scripts.set_study_goal             # bind the local learner to both
```

Python 3.14 is required, and `DATABASE_URL` must be set — the backend will not start without it.
Copy `.env.example` to `.env` for working local values.

Before committing, run the
[local quality checks](docs/development/coding-standards.md#local-quality-checks). The database
migration tests are not part of that set: they need PostgreSQL, so they skip unless
`TEST_DATABASE_URL` names a disposable database. CI runs them on every pull request.

## Project status

Documentation and architecture foundation, a minimal FastAPI backend foundation, the curriculum and
examination-schedule database schema with the curated data that fills both, the learner's study
goal, and the first read API over the curriculum.
[Project context](docs/00-project-context.md) is the authoritative summary of what exists.

**Implemented**

- A FastAPI application served through a composition-root application factory.
- Validated startup configuration for `APP_ENV`, `APP_LOG_LEVEL`, `APP_DEFAULT_TIMEZONE`,
  `API_HOST`, `API_PORT`, and the required `DATABASE_URL`.
- `GET /health`, an operational endpoint served outside `/api/v1`.
- The curriculum read endpoints CUR-001 to CUR-003 under `/api/v1/curriculum`: the learning-program
  list, one program with its active curriculum-version reference, and a version's subjects, topics,
  subtopics, and topic relationships. Every response uses the documented `data` envelope, and every
  failure the documented error envelope. See [API endpoints](docs/api/endpoints.md#curriculum-endpoints)
  and [ADR-014](docs/adr/ADR-014-api-response-contract.md).
- A backend container image and Docker Compose `backend` and `postgres` services. See
  [Docker strategy](docs/deployment/docker.md).
- SQLAlchemy models and Alembic migrations for the curriculum tables — learning programs, curriculum
  versions, subjects, topics, and topic relationships — the examination schedule tables, and
  `learners` and `study_goals`. See [database schema](docs/database/schema.md).
- An idempotent seed, `python -m scripts.seed_curriculum`, loading the curated GATE CSE curriculum —
  11 subjects, 65 topics and subtopics, transcribed from the official syllabus. It matches records on
  a natural key, writes only what differs, and never deletes, so repeat runs are safe. See
  [the curriculum seed](docs/database/migrations.md#the-curriculum-seed).
- A second idempotent seed, `python -m scripts.seed_examination_schedule`, loading the published GATE
  2027 schedule as dated periods with its official source and its `provisional`/`confirmed` status.
  See [the examination schedule seed](docs/database/migrations.md#the-examination-schedule-seed).
- `python -m scripts.set_study_goal`, which binds the local learner to the active curriculum version
  and the published examination window. An examination is stored as a window, never as a single
  guessed date; see [ADR-013](docs/adr/ADR-013-examination-schedule-and-study-goal.md).
- Continuous integration on pull requests: backend tests, Ruff lint and format checks,
  documentation validation, database migration checks, and container build validation. See
  [CI/CD strategy](docs/deployment/ci-cd.md).

**Not implemented**

AI and RAG, the frontend, external integrations, and every learner feature beyond choosing a
curriculum and an examination goal. The curriculum endpoints above are the only ones serving
learner-facing data, and they only read — no endpoint writes anything. The examination schedule and
the study goal are reachable only through the commands above; the learner and study-goal endpoints
are deferred until the client that consumes them exists, per
[ADR-013](docs/adr/ADR-013-examination-schedule-and-study-goal.md). The progress, resource, and
assessment tables arrive with the milestones that use them. Compose has no ChromaDB or frontend
service. Nothing beyond the implemented items above should be inferred from the current repository
contents.
