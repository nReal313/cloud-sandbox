FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -m -u 1000 sandbox

COPY README.md pyproject.toml ./
COPY cloud_sandbox ./cloud_sandbox

RUN chown -R sandbox:sandbox /app

USER sandbox

EXPOSE 8080

CMD ["python", "-m", "cloud_sandbox"]

