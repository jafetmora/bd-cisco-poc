# Cisco AI Agent – Mono‑Repo

> **Purpose**  Bootstrap directory structure, local dev workflow, and basic Git commands.

---

## 1  Folder Layout

```
repo/
├─ client/          # React PWA
├─ api/               # FastAPI + LangGraph orchestrator
├─ infra/             # Terraform or CDK modules
└─ scripts/           # Utility scripts (index build, data ingest)
```

---

## 2  Prerequisites

| Tool                | Minimum Version | Purpose           |
| ------------------- | --------------- | ----------------- |
| **Git**             |  2.40           | version control   |
| **Docker**          |  24.x           | local containers  |
| **Python**          |  3.11           | API & tooling     |
| **Node + PNPM**     |  20.x + 8.x     | React front‑end   |
| **Make** (optional) | any             | convenience tasks |

---

## 3  Clone & Bootstrap

```bash
# 1. Clone and enter repo
$ git git@github.com:jafetmora/bd-cisco-poc.git
$ cd bd-cisco-poc

# 2. Install pre‑commit hooks (lint/format)
$ pip install pre-commit && pre-commit install

# 3. Build & run both services with Docker Compose
$ docker compose up --build
```

Local endpoints:

* **FastAPI** – [http://localhost:8000/docs](http://localhost:8000/docs)
* **React**   – [http://localhost:5173](http://localhost:5173)

---

## 4  Development Branching

```text
main   ← protected, demo deploys
 dev    ← integration, staging deploys
 feature/*  ← short-lived work branches
 infra/*    ← Infra changes only
```

Create a feature branch and push:

```bash
$ git checkout -b feature/my-task
# …code…
$ git commit -m "feat: my task"
$ git push -u origin feature/my-task
```

Open a Pull Request into **test**. GitHub Actions will lint, test, and scan images.

---

## 5  Docker Quick‑start

*Build images locally*

```bash
# API
$ docker build -t ai-agent-api:dev -f api/Dockerfile .

# Front‑end
$ docker build -t ai-agent-client:dev -f client/Dockerfile .
```

*Run with Compose*

```bash
$ docker compose up
```

---

## 6  Makefile Targets *(optional)*

```makefile
make dev        # compose up (live reload)
make lint       # ruff + eslint
make test       # pytest + vitest
make clean      # docker prune + cache clear
```
