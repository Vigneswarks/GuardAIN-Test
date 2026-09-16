FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY backend /app/backend
COPY ai_pipeline /app/ai_pipeline
COPY extension /app/extension
COPY pwa /app/pwa
COPY admin_portal /app/admin_portal
COPY test_bench.html /app/test_bench.html
RUN mkdir -p /app/backend/models /app/data && useradd --create-home --uid 10001 guardain && chown -R guardain:guardain /app
USER guardain

EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
