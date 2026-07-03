# Teroxx Portfolio Allocation App — Migration Runbook

**Companion to the handover deck (`Teroxx_Portfolio_App_Handover.pptx/.pdf`).**
Audience: IT (Emil). This is the concrete, command-level version of Section 4.

Prepared by Aleksander Biesaga · July 2026 · Confidential — internal use only.

---

## 0. TL;DR

The app is **one Docker container** (built from the repo `Dockerfile`, which bundles
the Python app + LibreOffice + brand fonts) plus a **managed PostgreSQL** plus a
**handful of environment variables**. No code changes are required to move it off
the current personal Render account onto Teroxx-owned cloud.

```
repo  →  container image  →  container host  →  + Postgres  →  + env vars  →  live
```

- **Health check:** `GET /health` → `200 OK`
- **Container listens on:** port **8000** (see `Dockerfile` `CMD`)
- **First boot:** database tables auto-create (SQLAlchemy `init_db()`), no migrations to run

---

## 1. Get the code

IT (Emil) has already created the Teroxx-owned GitLab group and project:

```
group:   gitlab.com/groups/teroxx-dev/internal-it/investment-advisory-and-research
project: teroxx-dev/internal-it/investment-advisory-and-research/portfolio-allocation-model
```

Aleksander is currently invited as **maintainer**, and the full codebase is already
pushed (both `main` and the `import` branch). There is also a private GitHub mirror
`abiesaga90/teroxx-portfolio-app` — **retire it after cut-over**.

```bash
git clone https://gitlab.com/teroxx-dev/internal-it/investment-advisory-and-research/portfolio-allocation-model.git
cd portfolio-allocation-model
```

**Action for IT:** take Owner on the project, wire CI/CD and deploy tokens under the
Teroxx group (not a personal account), and reduce Aleksander's access after handover.

> **On "no database":** in the kickoff chat the app was described as "FastAPI in
> Docker, no database." The code actually has a full SQLAlchemy layer and is built for
> PostgreSQL (`psycopg2-binary` is a dependency). It reads `DATABASE_URL` at startup: if
> set (likely in the Render dashboard) it uses that managed Postgres; if unset it falls
> back to local SQLite, which is ephemeral on Render's free tier. **Verify the current
> backend in the Render dashboard.** For the Teroxx deployment, use a managed RDS
> Postgres either way (§2) — a config change (`DATABASE_URL`), not a code change.

---

## 2. Provision a managed PostgreSQL

Create a managed Postgres on your chosen cloud (AWS RDS, Cloud SQL, Azure Database,
DigitalOcean Managed DB, or the platform's built-in add-on). A small instance is
plenty — this is a low-write advisory tool, not a high-throughput system.

Copy the connection string. SQLAlchemy 2.x expects the `postgresql://` scheme
(the app auto-rewrites a `postgres://` prefix, so either works):

```
postgresql://USER:PASSWORD@HOST:5432/teroxx
```

Enable **automated daily backups** on the new instance — that guarantees durability
regardless of what the current setup uses.

---

## 3. Provision the container host

Any Docker-capable platform works. Point it at the repo's `Dockerfile` (root of repo).

**Build/run locally to sanity-check first:**

```bash
docker build -t teroxx-portfolio-app .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/teroxx" \
  -e SESSION_SECRET="$(openssl rand -base64 32)" \
  -e TEROXX_VECTOR_CHARTS=0 \
  teroxx-portfolio-app
# then: curl -f http://localhost:8000/health
```

**Platform — aligned with Teroxx IT:**

| Platform | Notes |
|---|---|
| **AWS EKS** | Teroxx's container standard (per IT). One Deployment + Service + Ingress + RDS. See **Appendix A**. |
| AWS App Runner / ECS Fargate | Same image, AWS-native, far less to operate than a cluster. Good if lower ops is preferred. |
| Render / Railway / Fly.io | Same PaaS model as today; `render.yaml` already in repo. A quick bridge. |
| Cloud Run / Azure Container Apps | The identical container runs anywhere — noted for completeness. |

> **Port note:** the container's `CMD` binds **8000**. Platforms that inject a `$PORT`
> (Cloud Run, App Runner) should either target container port 8000 or override the
> start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

---

## 4. Set environment variables

Set these in the host's dashboard / secret manager. Full reference is on the
env-var slide of the deck.

**Required for a healthy production deploy:**

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Postgres string from step 2 |
| `SESSION_SECRET` | a **fresh** random value — `openssl rand -base64 32` |

**Recommended:**

| Variable | Value |
|---|---|
| `TEROXX_VECTOR_CHARTS` | `0` on small instances (< ~1 GB RAM) to avoid LibreOffice OOM; `1` for crisper vector charts on larger hosts |
| `CMC_API_KEY` | **Teroxx's own** CoinMarketCap key — register a Teroxx account and issue a fresh key; do not keep using the shared/personal default baked into the code |
| `COINGECKO_API_KEY` | **Teroxx's own** CoinGecko key — same: register under a Teroxx account |

> **Own your data-source keys.** Verified in `app/market_data.py`:
> - **CoinMarketCap** (`X-CMC_PRO_API_KEY`) and **CoinGecko** (`x-cg-demo-api-key`, a
>   *Demo*-tier key) are the only two sources that authenticate — and both currently fall
>   back to shared/personal default keys hard-coded in the app. Teroxx should register its
>   own accounts with these two providers and set its own keys, so usage, quotas and
>   billing sit with Teroxx.
> - **DeFiLlama** (`api.llama.fi`), **Binance** (public `fapi`/spot) and **Messari**
>   (`/metrics/v2/networks`, "no auth required") use **no key** as implemented, as does the
>   macro composite. No action needed.
> - *Caveat:* those three are free public tiers with rate limits that can change. Nothing
>   breaks without keys today; if limits ever bite, CoinGecko Pro / DeFiLlama Pro are
>   optional paid upgrades (Binance public market data needs no key).

**Optional — only for Google Doc export** (the `.gdoc` proposal button stays hidden if unset):

| Variable | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | service-account JSON (raw or base64), issued under Teroxx Workspace |
| `GOOGLE_DRIVE_FOLDER_ID` | target Drive / Shared-Drive folder |
| `GOOGLE_IMPERSONATE_SUBJECT` | user to impersonate (domain-wide delegation) |
| `GOOGLE_DOCS_SHARE` | `none` \| `domain` \| `anyone` (default `none`) |

> **Secrets are handed over separately** via password manager / vault — none are in
> this file or the deck. Rotate all shared keys as part of the move.

---

## 5. Deploy & verify

Deploy the image. On first boot the app creates its tables automatically.

```bash
# health
curl -f https://<your-host>/health          # expect 200

# then in a browser:
#  - log in (existing users: jannick / leonardo / aleksander / christopher)
#  - open the Allocator tab, build an allocation
#  - export a proposal as PDF  ← exercises LibreOffice + fonts end-to-end
```

If the PDF export works, the whole runtime (LibreOffice, Pango/Cairo, brand fonts) is
healthy. If you get a 502 on `.docx`/`.pdf`, the instance is memory-starved — set
`TEROXX_VECTOR_CHARTS=0` and/or size up.

---

## 6. Add the IT user & rotate logins

Users live in `app/auth.py` as `email → {name, "salt:sha256hash"}`. To add Emil:

```python
# generate a hash
python3 - <<'PY'
import hashlib, os
salt = os.urandom(16).hex()
pw = "CHOOSE_A_PASSWORD"
print(f"{salt}:{hashlib.sha256((salt+pw).encode()).hexdigest()}")
PY
```

Paste the `salt:hash` into `USERS` in `app/auth.py`, commit, redeploy.

> This is lightweight internal auth for a small trusted desk. If the app is ever
> exposed more widely, front it with SSO / an identity-aware proxy and move users
> out of source control.

---

## 7. Map a domain

Point a Teroxx subdomain (e.g. `portfolio.teroxx.com`) at the service and enable TLS.
Most managed platforms issue and renew the certificate automatically once you add the
custom domain and the DNS record they specify.

---

## 8. (If needed) migrate existing data

Client data is **mostly test / throwaway**, so migration can start with a **fresh**
Teroxx database — clients are re-entered as needed.

First **confirm the current backend** (Render dashboard → is `DATABASE_URL` set?):

- **If it's a managed Postgres** and holds anything worth keeping, dump and restore into
  the new Teroxx Postgres before cut-over:
  ```bash
  pg_dump "$OLD_DATABASE_URL" > dump.sql
  psql   "$NEW_DATABASE_URL" -f dump.sql
  ```
- **If it's SQLite** (`DATABASE_URL` unset, ephemeral disk) and something must be kept,
  dump the tables (`clients`, `client_lots`, `scenarios`) and load them into Postgres, or
  use `pgloader` for a one-shot SQLite→Postgres transfer. The schema is identical —
  SQLAlchemy creates it automatically on first boot.

---

## 9. Cut over

1. Confirm the new host is healthy and Research can log in.
2. Update everyone's bookmarks to the new domain.
3. **Suspend** (don't yet delete) the old personal Render service.
4. After a week of stable operation, delete the old Render app and the GitHub mirror.
5. Confirm daily Postgres backups are running.

---

## Key files (for reference)

| Path | What it is |
|---|---|
| `Dockerfile` | the entire runtime recipe (app + LibreOffice + fonts) |
| `render.yaml` | current deploy config & the env-var keys in use |
| `requirements.txt` | Python dependencies |
| `app/db.py` | SQLAlchemy models + `DATABASE_URL` resolution logic |
| `app/auth.py` | users + `SESSION_SECRET` |
| `app/main.py` | all routes / the API surface |
| `app/pdf/` | the proposal engine (DOCX master → PDF / Google Doc) |
| `docs/google_docs_setup.md` | Google Doc export setup (if enabling that feature) |
| `CLAUDE.md` | in-repo design notes & version history |

---

## Appendix A — AWS EKS reference deploy

Since AWS/EKS is Teroxx's standard, here is the shape of an EKS deployment. This is a
single small stateless service, so it stays intentionally minimal.

**Prerequisites**
- ECR repository for the image
- An RDS PostgreSQL instance reachable from the cluster (same VPC / security group)
- Secrets in AWS Secrets Manager (or Kubernetes Secrets) for `DATABASE_URL`,
  `SESSION_SECRET`, and the API keys

**1) Build & push the image to ECR**

```bash
aws ecr create-repository --repository-name teroxx-portfolio-app
docker build -t teroxx-portfolio-app .
docker tag teroxx-portfolio-app:latest <acct>.dkr.ecr.<region>.amazonaws.com/teroxx-portfolio-app:latest
docker push <acct>.dkr.ecr.<region>.amazonaws.com/teroxx-portfolio-app:latest
```

**2) Create the secret**

```bash
kubectl create secret generic teroxx-portfolio-secrets \
  --from-literal=DATABASE_URL='postgresql://USER:PASSWORD@RDS-HOST:5432/teroxx' \
  --from-literal=SESSION_SECRET="$(openssl rand -base64 32)" \
  --from-literal=CMC_API_KEY='<teroxx-cmc-key>'
```

**3) Deployment + Service + Ingress** (`k8s.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: teroxx-portfolio-app
spec:
  replicas: 1
  selector: { matchLabels: { app: teroxx-portfolio-app } }
  template:
    metadata: { labels: { app: teroxx-portfolio-app } }
    spec:
      containers:
        - name: app
          image: <acct>.dkr.ecr.<region>.amazonaws.com/teroxx-portfolio-app:latest
          ports: [{ containerPort: 8000 }]
          envFrom:
            - secretRef: { name: teroxx-portfolio-secrets }
          env:
            - { name: TEROXX_VECTOR_CHARTS, value: "0" }   # bump to "1" if you give it >1Gi
          resources:
            requests: { cpu: "250m", memory: "512Mi" }
            limits:   { cpu: "1",    memory: "1Gi" }        # LibreOffice needs headroom
          readinessProbe:
            httpGet: { path: /health, port: 8000 }
            initialDelaySeconds: 15
          livenessProbe:
            httpGet: { path: /health, port: 8000 }
            initialDelaySeconds: 30
---
apiVersion: v1
kind: Service
metadata: { name: teroxx-portfolio-app }
spec:
  selector: { app: teroxx-portfolio-app }
  ports: [{ port: 80, targetPort: 8000 }]
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: teroxx-portfolio-app
  annotations:
    kubernetes.io/ingress.class: alb                       # AWS Load Balancer Controller
    alb.ingress.kubernetes.io/scheme: internal             # internal-only unless public is needed
spec:
  rules:
    - host: portfolio.teroxx.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: teroxx-portfolio-app, port: { number: 80 } } }
```

```bash
kubectl apply -f k8s.yaml
kubectl rollout status deploy/teroxx-portfolio-app
```

**Notes**
- **One replica is fine.** In-memory caches warm per-pod; horizontal scaling just means
  each pod warms its own cache. There is no sticky-session requirement beyond the signed
  cookie, which is stateless.
- **Memory:** LibreOffice (PDF export) is the memory-hungry step. Keep the 1Gi limit and
  `TEROXX_VECTOR_CHARTS=0`, or raise both together.
- **TLS:** terminate at the ALB (ACM certificate) or via cert-manager.

---

*Questions during transition: Aleksander Biesaga — aleksander.biesaga@teroxx.com*
