FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir . && useradd --create-home doctor
USER doctor

ENTRYPOINT ["dataset-doctor"]
CMD ["--help"]
