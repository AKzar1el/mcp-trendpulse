# syntax=docker/dockerfile:1

FROM python:3.12.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    NLTK_DATA=/opt/nltk_data \
    HOME=/home/trendpulse \
    TMPDIR=/tmp/trendpulse \
    TRENDPULSE_BROWSER_SANDBOX=true

WORKDIR /app

COPY . /app

RUN uv sync --locked --no-dev --no-editable \
    && .venv/bin/playwright install --with-deps chromium \
    && mkdir -p "$NLTK_DATA" \
    && .venv/bin/python -m nltk.downloader -d "$NLTK_DATA" punkt punkt_tab \
    && groupadd --system --gid 10001 trendpulse \
    && useradd --system --uid 10001 --gid trendpulse --home-dir "$HOME" --create-home --shell /usr/sbin/nologin trendpulse \
    && mkdir -p "$TMPDIR" \
    && chown -R trendpulse:trendpulse "$HOME" "$TMPDIR" \
    && chmod -R a+rX /app/.venv "$PLAYWRIGHT_BROWSERS_PATH" "$NLTK_DATA" \
    && rm -rf /root/.cache /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["uvicorn", "mcp_trendpulse.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
