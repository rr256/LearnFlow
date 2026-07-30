"""Operational health endpoint (OPS-001).

Served outside ``/api/v1`` so container health probes and environment checks stay
stable across API major versions. See docs/api/conventions.md.

The response is a flat object rather than the ``data`` envelope used by
application endpoints, because probe tooling reads the status field directly.
This is the documented operational-endpoint exception.
"""

from fastapi import APIRouter

router = APIRouter(tags=["operational"])


@router.get("/health")
def read_health() -> dict[str, str]:
    """Report that the API process is running and able to serve requests.

    Returns no learner data, curriculum content, provider configuration, or secrets.
    """
    return {"status": "ok"}
