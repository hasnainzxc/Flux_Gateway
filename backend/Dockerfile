FROM python:3.12-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
