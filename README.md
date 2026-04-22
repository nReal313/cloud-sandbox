# cloud-sandbox

Prototype sandbox service for agent-driven code execution.

The basic shape is:

- agents send Python code to an HTTP endpoint
- the service writes that code into a temporary workspace
- the code runs in a subprocess inside the sandbox container
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
- Python subprocess execution
- temp workspaces for each request
- gVisor-ready Kubernetes deployment scaffold

## What is not here yet

- sessions
- gRPC
- artifact download endpoints
- object storage integration
- Kubernetes pod-per-exec orchestration
- MCP wrappers
