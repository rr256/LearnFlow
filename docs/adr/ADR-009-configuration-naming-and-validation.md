---
title: "ADR-009: Name and Validate Configuration Variables Explicitly"
status: accepted
owner: architecture-and-development
last_updated: 2026-07-31
related:
  - ../00-project-context.md
  - ../deployment/environments.md
  - ../deployment/docker.md
  - ../architecture/provider-pattern.md
---

# ADR-009: Name and Validate Configuration Variables Explicitly

## Status

Accepted — 2026-07-30

## Context

LearnFlow's deployment documents listed provisional environment-variable names before any code
read them. Two documents drifted apart while the names were still provisional:

- `deployment/environments.md` listed `API_HOST` and `API_PORT`; `deployment/docker.md` listed
  `API_BASE_URL` for what appeared to be the same concern.
- `environments.md` listed both `EMBEDDING_MODEL` and `OLLAMA_EMBEDDING_MODEL`, leaving it
  undefined which one configured the embedding model.

The architecture decision register recorded this as a deliberate deferral: *"Exact
configuration-variable names … Re-evaluate when: configuration code is implemented; the names are
then fixed in one authoritative place."* Introducing the backend configuration module fires that
trigger.

Names are cheap to change now and expensive later. Once contributors hold untracked `.env` files
and Compose definitions reference variables, a rename becomes a coordinated change across code,
containers, documentation, and every developer's machine.

## Decision

### Three variable categories

Every LearnFlow configuration variable belongs to exactly one of three categories:

| Category | Form | Purpose | Examples |
| --- | --- | --- | --- |
| **1. Core runtime** | `APP_*`, `API_*` | How the application process itself runs. Not tied to any replaceable capability. | `APP_ENV`, `APP_LOG_LEVEL`, `API_HOST`, `API_PORT` |
| **2. Capability** | `<CAPABILITY>_PROVIDER`, plus capability-level settings | Which adapter fulfils an application port, and settings that stay meaningful whichever adapter is chosen. | `AI_PROVIDER`, `EMBEDDING_PROVIDER`, `RESOURCE_STORAGE_PROVIDER`, `RESOURCE_STORAGE_PATH`, `DATABASE_URL` |
| **3. Vendor** | `<VENDOR>_<SETTING>` | Settings meaningful only to one specific vendor. | `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBEDDING_MODEL`, `POSTGRES_USER`, `CHROMA_URL` |

Categories 2 and 3 are the load-bearing distinction: a capability-level setting survives a provider
change, a vendor setting does not. `AI_PROVIDER=ollama` selects the adapter and `OLLAMA_CHAT_MODEL`
configures it; switching to a cloud provider keeps the former and replaces the latter.

Category 1 exists because process-level settings answer to no capability and name no vendor.
Without it the rule would be stated more broadly than it is true.

### `EMBEDDING_MODEL` is removed

Embeddings are configured with `EMBEDDING_PROVIDER` (category 2) plus `OLLAMA_EMBEDDING_MODEL`
(category 3). A bare `EMBEDDING_MODEL` is neither: a model identifier is meaningful only to the
vendor that serves it, so it cannot be a capability-level setting, yet the name records no vendor.
Keeping both forms also left it undefined which one applied. This follows ADR-004, which keeps
embedding configuration independent of generation configuration.

### `API_BASE_URL` is not a backend setting

`API_HOST` and `API_PORT` are the address the backend binds to. `API_BASE_URL` is the address a
client calls. These are different concerns that were conflated across two documents. The backend
owns the binding variables; the client-facing URL becomes frontend configuration when a frontend
exists.

### `deployment/environments.md` is the authoritative catalogue

One document lists every variable. Other documents link to it rather than restating it. This is
what allowed the drift above.

### Configuration is validated before the application is created

The composition root builds a typed `Settings` object from the environment and an optional local
`.env`. Invalid values raise before `create_app()` returns an application, so the process fails
fast with a safe message instead of starting in an unusable state.

Settings are injectable — `create_app(settings: Settings | None = None)` — so tests exercise wiring
without mutating the process environment.

### Variables are added when their consumer exists

The backend defines only `APP_ENV`, `APP_LOG_LEVEL`, `API_HOST`, and `API_PORT` today. Database,
AI, retrieval, and storage variables are added in the change that introduces the code reading them,
not in advance.

## Consequences

### Positive

- A contributor can derive a variable's meaning from its name without consulting a table.
- The catalogue has one authoritative home, so the drift that prompted this cannot silently recur.
- Misconfiguration fails at startup with a message naming the offending field.
- Tests configure the application without touching global environment state.
- `.env.example` stays short and honest, listing only variables that actually do something.

### Negative

- Adding a variable now requires deciding its category rather than inventing a name, and the
  capability-versus-vendor judgement is occasionally genuinely arguable.
- Vendor-prefixed names must change if the vendor changes — for example, an `OPENAI_CHAT_MODEL`
  would replace `OLLAMA_CHAT_MODEL` rather than being a generic name that survives.
- Validation lives in the composition root, so a new setting means editing one shared module.

### Mitigations

- The three categories are few enough to state compactly in `.env.example` and the catalogue.
- When capability versus vendor is arguable, prefer the vendor form: a needless rename later is
  cheaper than a name that outlives the value it describes.
- Provider-selection variables (`<CAPABILITY>_PROVIDER`) stay stable across vendor changes; only
  the vendor-specific settings move, which is the intended signal.
- Keep `Settings` grouped by capability so it stays readable as it grows.

## Alternatives Considered

### Generic vendor-neutral names for everything

Use `EMBEDDING_MODEL`, `CHAT_MODEL`, `OLLAMA_STORAGE_PATH` — one flat naming style for everything,
with no distinction between capability-level and vendor-level settings.

**Rejected:** collapsing the distinction hides whether a value survives a provider change. A model
identifier valid for Ollama is meaningless to OpenAI, so a generic `EMBEDDING_MODEL` would keep its
name across a provider switch while its value silently became wrong. The reverse error is equally
bad: a filesystem path for learner resources is meaningful whichever storage adapter is configured,
so vendor-prefixing it would force a pointless rename. Categories 2 and 3 exist precisely to record
which of the two a setting is.

### Keep both `EMBEDDING_MODEL` and `OLLAMA_EMBEDDING_MODEL`

Treat one as a fallback for the other.

**Rejected:** two variables for one setting requires a precedence rule that every reader must learn,
and the ambiguity is precisely the defect this decision resolves.

### Read `os.environ` directly with hand-written checks

Avoid a configuration dependency.

**Rejected:** duplicates parsing, type coercion, and error reporting that `pydantic-settings`
already provides, and `pydantic` is already present as a FastAPI dependency. Hand-rolled validation
tends to drift toward inconsistent error messages.

### Define all documented variables now

Populate `Settings` with database, AI, retrieval, and storage values immediately.

**Rejected:** settings nothing reads cannot be validated meaningfully, and `.env.example` would ask
contributors to configure services that do not yet exist.

## Implementation Notes

- Configuration lives in `backend/app/composition/config.py`. Domain and application code must never
  read environment variables; only the composition root does.
- `deployment/environments.md` is updated in the same change as any new variable, per its own rules.
- `.env.example` lists only variables the backend currently reads.
- `extra="ignore"` lets unrelated variables in a developer's shell coexist without failing startup.
- Never log full connection strings, credentials, or secret values; validation errors name the field
  and the constraint, not the value's origin.

### Implementation status — 2026-07-31

This note records what has changed since the decision was accepted. The Decision, Consequences, and
Alternatives above are the accepted text and are not rewritten as variables are added.

`DATABASE_URL` is now implemented. The decision above states that variables are added when their
consumer exists, and the backend gained one: a configured SQLAlchemy engine and an Alembic
environment that read it. The sentence in *Variables are added when their consumer exists* naming
`APP_ENV`, `APP_LOG_LEVEL`, `API_HOST`, and `API_PORT` as the only defined variables describes the
state when this ADR was accepted, not the state today. AI, retrieval, and storage variables remain
unimplemented and still join in the change that reads them.

`DATABASE_URL` is a capability-level setting under the categories above, alongside the vendor-level
`POSTGRES_*` values that configure the local database service. It is also the first variable defined
with no default, and it still fails at startup naming the field, which is the fail-fast behaviour
this decision requires. The catalogue records why it has no default; that reasoning is not repeated
here.

[Environments and configuration](../deployment/environments.md) remains the authoritative catalogue.
Consult it rather than this ADR for which variables exist today; this ADR records why they are named
and validated as they are, and is not updated each time one is added.

## Related Documents

- [Project context](../00-project-context.md)
- [Environments and configuration](../deployment/environments.md) — the authoritative variable catalogue
- [Docker strategy](../deployment/docker.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [ADR-002: Use provider interfaces for external capabilities](ADR-002-provider-pattern.md)
- [ADR-004: Use Ollama as the initial local AI provider](ADR-004-ollama-local-ai-provider.md)
- [ADR-005: Use Docker Compose for local development](ADR-005-docker-compose-local-development.md)
- [Architecture decision register](../architecture/decisions.md)
