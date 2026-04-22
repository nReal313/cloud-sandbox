# cloud-sandbox

Prototype sandbox service for agent-driven code execution.

The basic shape is:

- agents can send Python code to a stateless `/exec` endpoint
- agents can create a session, install Python dependencies, and run multiple execs in the same workspace
- sessions can be created with GCP connector targets for BigQuery, Firestore, and GCS
- the service writes code into a workspace on disk
- code runs in a subprocess inside the sandbox container
- the generated code receives a `sandbox` object with connector helpers and capability introspection
- Kubernetes can place the pod under `gVisor` via `runtimeClassName: gvisor`
- outputs come back as JSON: stdout, stderr, exit code, duration, and artifact paths

This is intentionally small. It is the starting point for a pod-per-session sandbox,
not a full production isolation stack.

## Local run

```bash
python -m cloud_sandbox
```

The server listens on `PORT` if set, otherwise `8080`.

## Health check

```bash
curl http://localhost:8080/health
```

## Create a session

```bash
curl -X POST http://localhost:8080/sessions \
  -H 'Content-Type: application/json' \
  -d '{
    "ttl_seconds": 60,
    "image": "cloud-sandbox:latest",
    "runtime_class": "gvisor",
    "connectors": {
      "gcp": {
        "project_id": "sandbox-proj",
        "bigquery_default_dataset": "analytics",
        "gcs_bucket": "sandbox-bucket",
        "firestore_collection": "session_metadata"
      }
    }
  }'
```

The session response includes a capability manifest, and the same data is available at:

```bash
curl http://localhost:8080/capabilities
curl http://localhost:8080/sessions/<session-id>/capabilities
```

## Install dependencies in a session

```bash
curl -X POST http://localhost:8080/sessions/<session-id>/install \
  -H 'Content-Type: application/json' \
  -d '{
    "packages": ["pandas==2.2.3"]
  }'
```

## Execute code

```bash
curl -X POST http://localhost:8080/exec \
  -H 'Content-Type: application/json' \
  -d '{
    "code": "print(\"hello from the sandbox\")",
    "timeout_seconds": 10
  }'
```

Optional `files` can be supplied to create a temporary workspace before execution.

To run code inside a session:

```bash
curl -X POST http://localhost:8080/sessions/<session-id>/exec \
  -H 'Content-Type: application/json' \
  -d '{
    "code": "print(sandbox.capabilities()[\"connectors\"][\"gcp\"][\"project_id\"])",
    "timeout_seconds": 10
  }'
```

Inside generated code, the `sandbox` object exposes:

```python
df = sandbox.bigquery.query_df("select * from project.dataset.table limit 1000")
sandbox.firestore.write_metadata("runs/run_123", {"rows": len(df)})
sandbox.gcs.upload_bytes(b"payload", "gs://sandbox-bucket/artifacts/run_123.bin")
```

## Inspect a session

```bash
curl http://localhost:8080/sessions/<session-id> \
```

```bash
curl http://localhost:8080/sessions/<session-id>/artifacts
```

```bash
curl -X DELETE http://localhost:8080/sessions/<session-id>
```

## Kubernetes

The base manifests live in `k8s/base/`.

The deployment expects a cluster-level `RuntimeClass` named `gvisor`.
The pod itself is still just a container image with a Python runner inside it;
`gVisor` is the isolation layer underneath the pod.

If the cluster does not already have the runtime class, apply
`k8s/runtimeclass-gvisor.yaml` first.

Apply the base manifests after building and pushing an image:

```bash
kubectl apply -f k8s/runtimeclass-gvisor.yaml
kubectl apply -k k8s/base
```

## Workload identity

If you want the sandbox pod to use Google Cloud APIs from inside generated code, apply the Terraform stack in `terraform/` first.
It creates the Google service account, grants the GCP IAM roles, and outputs the annotation you should place on the `cloud-sandbox`
Kubernetes service account.

## What exists right now

- `GET /health`
- `GET /`
- `GET /capabilities`
- `POST /exec`
- `POST /sessions`
- `GET /sessions/{id}`
- `DELETE /sessions/{id}`
- `POST /sessions/{id}/exec`
- `POST /sessions/{id}/install`
- `GET /sessions/{id}/capabilities`
- `GET /sessions/{id}/artifacts`
- Python subprocess execution
- temp workspaces for each request
- session-backed workspaces and virtualenvs
- session-scoped GCP connector config and runtime injection
- gVisor-ready Kubernetes deployment scaffold

## What is not here yet

- gRPC
- artifact download endpoints
- object storage integration
- Kubernetes pod-per-exec orchestration
- MCP wrappers
