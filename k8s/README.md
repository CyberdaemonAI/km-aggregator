# Kubernetes Deployment

Internal deployment manifests are not included in this repository.

## What you need

- A Kubernetes cluster with:
  - `pgvector/pgvector:pg16` compatible PostgreSQL (or CloudNativePG operator)
  - Access to an Ollama inference endpoint (in-cluster or external)
  - A secret containing `MATTERMOST_WEBHOOK_URL` and optional `PROM_MEMORY_URL`

## Suggested manifest structure

```
k8s/
├── namespace.yaml
├── deployment.yaml
├── service.yaml
├── configmap.yaml        # non-secret env vars
├── secret.yaml           # MATTERMOST_WEBHOOK_URL, PROM_MEMORY_URL (gitignored)
└── postgres/
    └── cluster.yaml      # CloudNativePG or StatefulSet
```

## Quick reference

```bash
# Build and push image
docker build -t your-registry/km-aggregator:latest .
docker push your-registry/km-aggregator:latest

# Create secret
kubectl create secret generic km-aggregator-secrets \
  --from-literal=MATTERMOST_WEBHOOK_URL=https://... \
  --from-literal=PROM_MEMORY_URL=http://...

# Apply manifests
kubectl apply -f k8s/
```

## Health check

```bash
kubectl port-forward svc/km-aggregator 8000:8000
curl http://localhost:8000/health
```
