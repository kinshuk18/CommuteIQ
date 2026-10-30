# Cloud Deployment Design Note

> **This document is a design exercise only. CommuteIQ has no live cloud deployment.**
> It maps each local component to plausible managed services, notes trade-offs, and is
> intended to demonstrate cloud-architecture reasoning for the MoveInSync internship portfolio.

---

## Component Mapping

| Local component | AWS | GCP | Azure | Key trade-off |
|---|---|---|---|---|
| PostgreSQL 16 | RDS for PostgreSQL (Multi-AZ) | Cloud SQL for PostgreSQL | Azure Database for PostgreSQL (Flexible) | RDS managed failover vs. Cloud SQL's built-in PITR simplicity |
| Redis 7 | ElastiCache (Redis OSS) | Memorystore for Redis | Azure Cache for Redis | ElastiCache cluster mode vs. Memorystore's simpler IAM |
| Kafka 3.7 | Amazon MSK (Managed Streaming) | Confluent Cloud on GCP / Pub/Sub | Azure Event Hubs (Kafka-protocol) | MSK is native Kafka API; Pub/Sub is push-model and requires code change |
| AI service (FastAPI) | ECS Fargate / App Runner | Cloud Run | Azure Container Apps | Fargate for long-running tasks; Cloud Run for per-request billing |
| Gateway (Spring Boot) | ECS Fargate behind ALB | Cloud Run | Azure Container Apps + APIM | ALB provides L7 routing; Cloud Run auto-scales to zero |
| Web (React/Nginx) | S3 + CloudFront | Cloud Storage + Cloud CDN | Azure Static Web Apps | CloudFront edge cache; Azure Static Web Apps integrates CI natively |
| FAISS index (file-based) | EFS (shared across tasks) / S3 presigned init | Filestore / GCS bucket | Azure Files | EFS is lowest-latency for in-process FAISS; S3 for cold re-indexing |
| MLflow tracking | Self-hosted on EC2 + S3 artifact store | Vertex AI Experiments (partial compat.) | Azure ML Experiments | Native Vertex AI avoids self-hosting; less MLflow-API compatibility |
| CI/CD | GitHub Actions + ECR | Cloud Build + Artifact Registry | GitHub Actions + ACR | GitHub Actions reuses existing `.github/workflows/` unchanged |
| Secrets | AWS Secrets Manager + Parameter Store | Secret Manager | Azure Key Vault | All three integrate with k8s External Secrets Operator |

---

## Kubernetes Target (design only)

Manifests are in [`deploy/k8s/`](../deploy/k8s/) using Kustomize:
- Gateway and AI services have HPA (CPU ≥ 60 % → scale up; max 4 replicas each).
- Resource limits: gateway 512 Mi RAM / 500 m CPU; ai 1 Gi RAM / 1000 m CPU.
- FAISS index mounted from a PVC (ReadWriteMany via EFS/Filestore) so all AI replicas
  share the same pre-built index without rebuild on every pod start.
- Liveness probe: HTTP GET `/actuator/health` (gateway) and `/health` (ai service).
- Secrets injected via `secretKeyRef`; no literal keys in manifests.

---

## Why Not Serverless-First?

The AI service holds the FAISS index and the GBR model in memory; cold-start latency
for a 459-chunk FAISS index and a ~40 MB sklearn model is ~4–6 s — acceptable for
container-reuse (ECS/Cloud Run min-instances = 1) but prohibitive for pure serverless
(Lambda/Cloud Functions).  The gateway is stateless and could be deployed as Lambda +
API Gateway if the Kafka producer is replaced with EventBridge; that refactor is out of scope.

---

*Design note — not deployed. Authored 2026-10-30.*
