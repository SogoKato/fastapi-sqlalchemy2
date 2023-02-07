FROM python:3.10

WORKDIR /app

ENV PATH=$PATH:/root/.local/bin
COPY pyproject.toml poetry.lock ./

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry install

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--reload"]
