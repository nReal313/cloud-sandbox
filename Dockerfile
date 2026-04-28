FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN useradd -m -u 1000 sandbox

# Runtime dependencies used by generated code through the sandbox connector API.
RUN python -m pip install --upgrade pip \
    && python -m pip install \
      google-cloud-bigquery \
      google-cloud-firestore \
      google-cloud-storage \
      pandas \
      pyarrow

COPY README.md pyproject.toml ./
COPY cloud_sandbox ./cloud_sandbox

RUN chown -R sandbox:sandbox /app

USER 1000

EXPOSE 8080

CMD ["python", "-m", "cloud_sandbox"]
