# cloud-sandbox

Prototype sandbox service for agent-driven code execution.

The basic shape is:

- agents can send Python code to a stateless `/exec` endpoint
- agents can also create a session, install Python dependencies, and run multiple execs in the same workspace
- the service writes code into a workspace on disk
- code runs in a subprocess inside the sandbox container
- Kubernetes can place the pod under `gVisor` via `runtimeClassName: gvisor`
- outputs come back as JSON: stdout, stderr, exit code, duration, and artifact paths

This is intentionally small. It is the starting point for a pod-per-session sandbox,
not a full production isolation stack.

## Local run

```bash
python -m cloud_sandbox
```

The server listens on `PORT` if set, otherwise `8080`.

If you want auth, set `SANDBOX_AUTH_TOKEN` and send a bearer token on control routes:

```bash
export SANDBOX_AUTH_TOKEN=dev-token
```

## Health check

```bash
curl http://localhost:8080/health
```

## Create a session

```bash
curl -X POST http://localhost:8080/sessions \
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "ttl_seconds": 60,
    "image": "cloud-sandbox:latest",
    "runtime_class": "gvisor"
  }'
```

## Install dependencies in a session

```bash
curl -X POST http://localhost:8080/sessions/<session-id>/install \
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "packages": ["pandas==2.2.3"]
  }'
```

## Execute code

```bash
curl -X POST http://localhost:8080/exec \
  -H 'Authorization: Bearer dev-token' \
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
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "code": "print(\"hello from the session\")",
    "timeout_seconds": 10
  }'
```

## Inspect a session

```bash
curl http://localhost:8080/sessions/<session-id> \
  -H 'Authorization: Bearer dev-token'
```

```bash
curl http://localhost:8080/sessions/<session-id>/artifacts \
  -H 'Authorization: Bearer dev-token'
```

```bash
curl -X DELETE http://localhost:8080/sessions/<session-id> \
  -H 'Authorization: Bearer dev-token'
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

## What exists right now

- `GET /health`
- `GET /`
- `POST /exec`
- `POST /sessions`
- `GET /sessions/{id}`
- `DELETE /sessions/{id}`
- `POST /sessions/{id}/exec`
- `POST /sessions/{id}/install`
- `GET /sessions/{id}/artifacts`
- Python subprocess execution
- temp workspaces for each request
- session-backed workspaces and virtualenvs
- bearer auth when `SANDBOX_AUTH_TOKEN` is set
- gVisor-ready Kubernetes deployment scaffold

## What is not here yet

- gRPC
- artifact download endpoints
- object storage integration
- Kubernetes pod-per-exec orchestration
- MCP wrappers
