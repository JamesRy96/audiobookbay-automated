# File: Dockerfile
FROM python:3.14-slim

LABEL org.opencontainers.image.title="AudiobookBay Automated" \
      org.opencontainers.image.description="Search AudiobookBay and send books to your Download Client" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/meek2100/audiobookbay-automated"

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata gosu && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m appuser

# Cache locked runtime dependencies independently from application changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md AGENTS.md MANIFEST.in LICENSE entrypoint.sh ./
COPY audiobook_automated/ audiobook_automated/
RUN uv sync --frozen --no-dev --no-editable && chmod +x entrypoint.sh

EXPOSE 5078
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["/app/.venv/bin/python", "/app/audiobook_automated/healthcheck.py"]
ENTRYPOINT ["./entrypoint.sh"]
CMD []
