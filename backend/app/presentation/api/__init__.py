"""FastAPI delivery code for the LearnFlow HTTP API."""

from typing import Final

# Every public application endpoint is served under this path-based major
# version. Operational endpoints such as `GET /health` are deliberately outside
# it, so health probes keep working when a new major version is introduced.
# See docs/api/versioning.md.
API_V1_PREFIX: Final = "/api/v1"
