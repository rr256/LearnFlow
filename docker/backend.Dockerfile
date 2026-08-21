# LearnFlow backend image.
#
# Build context is the repository root, so this file can copy from backend/.
# See docs/deployment/docker.md for the Compose topology and configuration rules.
#
#   docker build -f docker/backend.Dockerfile .
#   docker compose up --build

FROM python:3.14-slim

# Keep the image free of .pyc files and make logs appear immediately rather than
# sitting in a buffer, which matters for `docker compose logs -f backend`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime dependencies only. Test and lint tooling from requirements-dev.txt does
# not belong in a runtime image. Copied before the source so a source-only change
# reuses the cached install layer.
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Only the application package. Tests, tooling configuration, and everything
# excluded by .dockerignore stay out of the image.
COPY backend/app ./app

# The process serves HTTP and needs no write access to its own source, so it runs
# as a dedicated unprivileged user.
RUN useradd --create-home --shell /usr/sbin/nologin learnflow

# Where learner-uploaded PDFs are kept (RES-014 to RES-017). Created here, owned
# by the unprivileged user, **before** the volume is mounted over it.
#
# That ordering is load-bearing. Docker initialises an empty named volume from
# the image's directory at the mount point, ownership included; if this path did
# not exist in the image, the volume would be created root-owned and the process
# below -- which is not root -- could not write a single file into it.
RUN mkdir -p /var/lib/learnflow/resources     && chown -R learnflow:learnflow /var/lib/learnflow

USER learnflow

# Documents the port the application listens on. Publishing is decided by
# compose.yaml, not here.
EXPOSE 8000

# `python -m app.main` is the entry point that honours API_HOST and API_PORT.
# Compose sets API_HOST=0.0.0.0 so the service accepts connections from outside
# the container; see docs/deployment/docker.md.
CMD ["python", "-m", "app.main"]
