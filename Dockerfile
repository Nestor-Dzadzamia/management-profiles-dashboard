FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /code

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

ENV PATH="/code/.venv/bin:$PATH"
ENV PYTHONPATH=/code/src

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]