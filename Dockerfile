# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn

COPY pyproject.toml README.md alembic.ini ./
COPY alembic/ alembic/
COPY schema/ schema/
COPY sql/ sql/
COPY src/ src/
COPY sample_data/ sample_data/
COPY evals/ evals/
COPY docs/ docs/

RUN pip install --no-cache-dir -e .

ENV CDP_DATA=/app/sample_data
ENV CDP_DATABASE_URL=postgresql://cdp:cdp@postgres:5432/cdp

ENTRYPOINT ["python", "-m", "cdp_cli.cli"]
CMD ["--help"]
