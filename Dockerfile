# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Include the api extra (fastapi + uvicorn) so `cdp serve` works in the image.
RUN pip install --no-cache-dir fastapi uvicorn

COPY pyproject.toml README.md ./
COPY schema/ schema/
COPY sql/ sql/
COPY src/ src/
COPY sample_data/ sample_data/
COPY docs/ docs/
COPY tests/ tests/

# Install the package itself so `python -m cdp_cli.cli` / `cdp` resolve.
RUN pip install --no-cache-dir -e .

# Keep the image simple; it runs the CLI as root for the demo.
ENV CDP_DATA=/app/sample_data
ENV CDP_DB=/app/warehouse.duckdb

# Default: build the warehouse from sample data, then drop to a shell-ish
# REPL-friendly state. First run: `docker run --rm -it <img> build --sample`
ENTRYPOINT ["python", "-m", "cdp_cli.cli"]
CMD ["--help"]
