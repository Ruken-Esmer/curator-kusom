FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-optional.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Optional neural extras: docker build --build-arg WITH_OPTIONAL=1 .
ARG WITH_OPTIONAL=0
RUN if [ "$WITH_OPTIONAL" = "1" ]; then pip install --no-cache-dir -r requirements-optional.txt; fi

COPY . .
RUN mkdir -p data/mimar data/embeddings

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
