FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system tracker \
    && adduser --system --ingroup tracker tracker

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations

RUN pip install --no-cache-dir .

USER tracker
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
