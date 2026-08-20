"""MNT-001 from inside the backend container, against a fake Ollama on the host.

Two things are proved here that no other test can, because both are properties of
the **deployment topology** rather than of the code:

1. `compose.yaml` puts the AI settings on the `backend` service and **nowhere
   else** — in particular not on `frontend`, whose environment reaches a Next.js
   server that renders pages. That is a configuration assertion and needs no
   container.
2. A backend **container** can actually reach an Ollama running on the **host**,
   through `host.docker.internal`. A container's `127.0.0.1` is the container
   itself, so the host-side default address is wrong inside one; this is the test
   that would have caught that.

**No real external call is made.** The "Ollama" is a contract-shaped fake HTTP
server started by this module, bound to the host so the container can reach it.
It records exactly what it was sent, which is how the payload assertions are made
from outside the application entirely — the strongest form of the privacy check,
since it reads the bytes that left the container.

**The learner's own database is never touched.** The container is pointed at the
disposable `TEST_DATABASE_URL` database, and this module refuses to run if that
value names the development database.

The configuration half needs nothing and runs everywhere Docker is installed.
The container half additionally needs the local Compose network and a
disposable ``TEST_DATABASE_URL``, and skips where either is absent — which is
the case on CI, whose PostgreSQL is a service container on its own network.
"""

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPOSITORY_ROOT / "compose.yaml"
IMAGE = "learnflow-backend:topology-test"
CONTAINER = "learnflow-topology-test"
COMPOSE_NETWORK = "learnflow_default"

ANSWER = "Each process runs for one quantum, then goes to the back of the queue."
QUESTION = "How does round robin choose the next process?"
PASSAGE_MARKER = "vector<int>"


# -- helpers ------------------------------------------------------------------


def _docker(*args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def _docker_is_available() -> bool:
    try:
        _docker("info", timeout=30)
    except OSError, subprocess.SubprocessError:
        return False
    return True


def _compose_network_exists() -> bool:
    """Whether the local Compose network the runtime half attaches to is present.

    The container is joined to the running Compose network so it can reach the
    `postgres` service by name. That network exists on a developer's machine once
    `docker compose up` has run, and **does not exist on a CI runner**, where
    PostgreSQL is a service container on the runner's own network instead.
    """
    try:
        listed = _docker("network", "ls", "--format", "{{.Name}}", timeout=30)
    except OSError, subprocess.SubprocessError:
        return False
    return COMPOSE_NETWORK in listed.stdout.split()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("0.0.0.0", 0))
        return probe.getsockname()[1]


pytestmark = pytest.mark.skipif(
    not _docker_is_available(), reason="Docker is not available on this machine."
)


# -- the configuration half: no containers ------------------------------------


@pytest.fixture(scope="module")
def compose_config() -> dict:
    """The fully rendered Compose topology, as the engine would read it."""
    import yaml

    rendered = _docker("compose", "-f", str(COMPOSE_FILE), "config")
    return yaml.safe_load(rendered.stdout)


AI_SETTINGS = ("AI_PROVIDER", "AI_REQUEST_TIMEOUT_SECONDS", "OLLAMA_BASE_URL", "OLLAMA_CHAT_MODEL")


def test_the_backend_service_carries_every_ai_setting(compose_config: dict):
    environment = compose_config["services"]["backend"]["environment"]

    for name in AI_SETTINGS:
        assert name in environment, f"{name} is missing from the backend service"


def test_the_backend_reaches_ollama_through_the_host_gateway(compose_config: dict):
    """A container's own loopback is not the host's, so the address is fixed here."""
    backend = compose_config["services"]["backend"]

    assert backend["environment"]["OLLAMA_BASE_URL"] == "http://host.docker.internal:11434"

    # Compose renders `extra_hosts` as `name=value`, whatever separator the file
    # used, so the mapping is matched by its parts rather than by one spelling.
    mapped = {
        entry.replace(":", "=", 1).split("=", 1)[0]: entry.replace(":", "=", 1).split("=", 1)[1]
        for entry in backend["extra_hosts"]
    }
    assert mapped.get("host.docker.internal") == "host-gateway"


def test_no_ai_setting_reaches_the_frontend_service(compose_config: dict):
    """The frontend's environment feeds a server that renders pages for a browser.

    Nothing about the provider belongs there: not the address, not the model, and
    not the fact that one is configured. `API_BASE_URL` is the only value it
    needs, and it is server-side only.
    """
    environment = compose_config["services"]["frontend"].get("environment", {})

    assert set(environment) == {"API_BASE_URL"}
    for name in AI_SETTINGS:
        assert name not in environment
    assert "OLLAMA" not in json.dumps(compose_config["services"]["frontend"])


def test_no_credential_appears_anywhere_in_the_topology(compose_config: dict):
    """The provider is local and authenticates nothing, so no key exists to leak."""
    rendered = json.dumps(compose_config).upper()

    for forbidden in ("API_KEY", "OPENAI", "AZURE", "ANTHROPIC", "BEARER"):
        assert forbidden not in rendered


# -- the runtime half: a container reaching a fake Ollama on the host ---------


class _FakeOllama(BaseHTTPRequestHandler):
    """A contract-shaped stand-in for Ollama's `/api/generate`."""

    received: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 - the name BaseHTTPRequestHandler requires
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        type(self).received.append(body)

        payload = json.dumps({"response": ANSWER, "done": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        """Silence the default stderr logging; a prompt must never reach a log."""


@pytest.fixture(scope="module")
def fake_ollama() -> Iterator[tuple[int, list[dict]]]:
    """A fake Ollama bound so the container can reach it through the host."""
    _FakeOllama.received = []
    port = _free_port()
    server = HTTPServer(("0.0.0.0", port), _FakeOllama)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, _FakeOllama.received
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def container_database_url(request: pytest.FixtureRequest) -> str:
    """The disposable database, addressed as the container will see it.

    Refuses anything that is not the configured test database. The container is a
    real backend and would write real rows; pointing it at the development
    database is the one mistake this file must make impossible.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set.")
    if "learnflow_test" not in url:
        pytest.skip("TEST_DATABASE_URL must name a disposable database, not the learner's own.")
    # Inside the Compose network the database is `postgres`, not a published port.
    return "postgresql+psycopg://learnflow:learnflow@postgres:5432/learnflow_test"


@pytest.fixture(scope="module")
def seeded_test_database(container_database_url: str) -> str:
    """One learner, one resource, one note — written from the host, read by the container."""
    from fastapi.testclient import TestClient
    from sqlalchemy import text as sql

    from app.application.use_cases.seed_curriculum import SeedCurriculum
    from app.composition.app_factory import create_app
    from app.composition.config import Settings
    from app.infrastructure.persistence.curriculum_seed_repository import (
        SqlAlchemyCurriculumSeedRepository,
    )
    from app.infrastructure.persistence.engine import (
        create_database_engine,
        create_session_factory,
    )
    from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

    host_url = os.environ["TEST_DATABASE_URL"]
    engine = create_database_engine(host_url)

    # Start from an empty schema, then migrate, exactly as conftest does.
    with engine.begin() as connection:
        connection.execute(sql("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(sql("CREATE SCHEMA public"))
    subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        cwd=REPOSITORY_ROOT / "backend",
        env={**os.environ, "DATABASE_URL": host_url},
        capture_output=True,
        text=True,
        check=True,
    )

    with create_session_factory(engine)() as session:
        SeedCurriculum(
            SqlAlchemyCurriculumSeedRepository(session),
            clock=lambda: datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        )(load_curriculum_seed(GATE_CSE_CURRICULUM_FILE))
        session.commit()

    app = create_app(Settings(database_url=host_url))
    with TestClient(app) as client:
        client.patch("/api/v1/learner/profile", json={"display_name": "Asha"})
        programs = client.get("/api/v1/curriculum/programs").json()["data"]
        version = next(p for p in programs if p["code"] == "gate-cse")["active_curriculum_version"]
        tree = client.get(f"/api/v1/curriculum/versions/{version['id']}/tree").json()["data"]

        found: list[dict] = []

        def walk(entries: list[dict]) -> None:
            for topic in entries:
                if topic["is_trackable"]:
                    found.append(topic)
                walk(topic["subtopics"])

        for subject in tree["subjects"]:
            walk(subject["topics"])
        topic = next(t for t in found if "schedul" in t["name"].lower())

        resource = client.post(
            "/api/v1/resources",
            json={
                "resource_type": "note",
                "title": "Operating Systems notes",
                "source_label": "Blue binder",
                "topic_ids": [topic["id"]],
            },
        ).json()["data"]
        client.post(
            f"/api/v1/resources/{resource['id']}/notes",
            json={
                "title": "Round robin",
                "body": (
                    "Schedulers keep ready processes in a "
                    f"{PASSAGE_MARKER} queue and give each one a quantum."
                ),
            },
        )
    engine.dispose()
    return topic["id"]


@pytest.fixture(scope="module")
def running_backend(
    container_database_url: str, seeded_test_database: str, fake_ollama: tuple[int, list[dict]]
) -> Iterator[str]:
    """The backend, in a container, wired exactly as Compose wires it.

    **Skipped where the Compose network is absent**, which is the case on CI: the
    container joins that network to reach the `postgres` service by name, and a
    runner has PostgreSQL as a service container on a different network instead.
    The configuration assertions above need no container and run everywhere, so
    CI still checks the topology — what it cannot check is the host-gateway path,
    which is a property of a developer's own machine.
    """
    if not _compose_network_exists():
        pytest.skip(
            f"The {COMPOSE_NETWORK!r} network is not present. Run `docker compose up -d` "
            "to exercise the container half of this file."
        )
    ollama_port, _ = fake_ollama
    _docker("build", "-f", "docker/backend.Dockerfile", "-t", IMAGE, ".", timeout=900)
    _docker("rm", "-f", CONTAINER, check=False, timeout=60)

    published = _free_port()
    _docker(
        "run",
        "-d",
        "--name",
        CONTAINER,
        "--network",
        COMPOSE_NETWORK,
        # The mapping compose.yaml declares, and the reason this test exists.
        "--add-host",
        "host.docker.internal:host-gateway",
        "-e",
        f"DATABASE_URL={container_database_url}",
        "-e",
        "API_HOST=0.0.0.0",
        "-e",
        "API_PORT=8000",
        "-e",
        "AI_PROVIDER=ollama",
        "-e",
        "AI_REQUEST_TIMEOUT_SECONDS=30",
        "-e",
        f"OLLAMA_BASE_URL=http://host.docker.internal:{ollama_port}",
        "-e",
        "OLLAMA_CHAT_MODEL=llama3.1:8b",
        "-p",
        f"127.0.0.1:{published}:8000",
        IMAGE,
        timeout=120,
    )

    base = f"http://127.0.0.1:{published}"
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as response:
                if response.status == 200:
                    break
        except urllib.error.URLError, TimeoutError, ConnectionError:
            time.sleep(1)
    else:
        logs = _docker("logs", CONTAINER, check=False).stdout
        _docker("rm", "-f", CONTAINER, check=False)
        pytest.fail(f"The backend container did not become healthy.\n{logs}")

    try:
        yield base
    finally:
        _docker("rm", "-f", CONTAINER, check=False, timeout=60)


def _ask(base: str, topic_id: str, question: str = QUESTION) -> dict:
    request = urllib.request.Request(
        f"{base}/api/v1/mentor/questions",
        data=json.dumps({"topic_id": topic_id, "question": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.loads(response.read())["data"]


def test_the_container_reaches_ollama_on_the_host_and_answers(
    running_backend: str, seeded_test_database: str, fake_ollama: tuple[int, list[dict]]
):
    """The topology proof: container → host gateway → Ollama → cited answer."""
    _, received = fake_ollama
    received.clear()

    data = _ask(running_backend, seeded_test_database)

    assert data["outcome"] == "answered"
    assert data["answer"] == ANSWER
    assert len(received) == 1, "the container did not reach the fake Ollama exactly once"


def test_the_container_sends_only_the_question_and_the_passages(
    running_backend: str, seeded_test_database: str, fake_ollama: tuple[int, list[dict]]
):
    """Read from the bytes that actually left the container, not from a fake port.

    This is the strongest form of the payload check: the assertions are made
    outside the application, on what the provider received over a socket.
    """
    _, received = fake_ollama
    received.clear()

    data = _ask(running_backend, seeded_test_database)
    sent = received[0]

    assert sent["model"] == "llama3.1:8b"
    assert sent["stream"] is False

    everything = f"{sent['prompt']}\n{sent['system']}"
    assert QUESTION in everything
    assert PASSAGE_MARKER in everything, "the retrieved passage did not reach the provider"

    # No identifier of any kind, and no title the learner gave anything.
    for identifier in (
        data["topic_id"],
        data["passages"][0]["note_id"],
        data["passages"][0]["resource_id"],
    ):
        assert identifier not in everything
    assert data["passages"][0]["note_title"] not in everything
    assert data["passages"][0]["resource_title"] not in everything

    # Nothing beyond the documented four fields is in the request body at all.
    assert set(sent) == {"model", "system", "prompt", "stream"}


def test_the_container_returns_the_passages_the_answer_was_grounded_in(
    running_backend: str, seeded_test_database: str
):
    data = _ask(running_backend, seeded_test_database)

    assert data["passages"], "an answered result carried no citation"
    passage = data["passages"][0]
    assert passage["note_title"] == "Round robin"
    assert passage["resource_title"] == "Operating Systems notes"
    assert PASSAGE_MARKER in passage["passage"], "a literal was mangled in transit"


def test_the_container_calls_no_provider_when_retrieval_has_no_evidence(
    running_backend: str, fake_ollama: tuple[int, list[dict]]
):
    """The central rule, proved where it matters most: nothing left the container.

    The topic is real and the learner has linked nothing to it, so retrieval
    returns empty and **the fake Ollama records no request at all**.
    """
    _, received = fake_ollama
    received.clear()

    programs = json.loads(
        urllib.request.urlopen(f"{running_backend}/api/v1/curriculum/programs", timeout=10).read()
    )["data"]
    version = next(p for p in programs if p["code"] == "gate-cse")["active_curriculum_version"]
    tree = json.loads(
        urllib.request.urlopen(
            f"{running_backend}/api/v1/curriculum/versions/{version['id']}/tree", timeout=10
        ).read()
    )["data"]

    unlinked: list[dict] = []

    def walk(entries: list[dict]) -> None:
        for topic in entries:
            if topic["is_trackable"] and "schedul" not in topic["name"].lower():
                unlinked.append(topic)
            walk(topic["subtopics"])

    for subject in tree["subjects"]:
        walk(subject["topics"])

    data = _ask(running_backend, unlinked[0]["id"], "Explain this to me.")

    assert data["outcome"] == "no_linked_material"
    assert data["answer"] is None
    assert data["passages"] == []
    assert received == [], "the container called the provider with no evidence to ground an answer"
