# ==============================================================
# Backend: FastAPI agent + MCP stdio server
# ==============================================================

FROM python:3.14-slim

# Faster, quieter Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so this layer caches across code changes.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Application code. Secrets are NOT copied -- see .dockerignore.
# credentials.json / token.json / .env are mounted at runtime.
COPY agent.py mcp_server.py auth.py ./

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# curl is not in the slim image; use the interpreter we already have.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status==200 else 1)"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8000"]
