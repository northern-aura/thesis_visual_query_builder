# ReactFlow Query Builder — Quick Start

A short setup checklist. For the full architecture overview see [README.md](./README.md).

---

## Prerequisites

- **Node.js** ≥ 16
- **Python** ≥ 3.8
- **Docker Desktop** (must be running before `npm run dev`)

---

## First-time setup

```bash
# 1. Install all dependencies (frontend + Python)
npm run setup

# 2. Start the Docker stack (Flink + Kafka + Zookeeper)
cd running/Docker
docker-compose -f env-compose.yml up -d
cd ../..
```

`npm run setup` is shorthand for `npm install && pip install -r requirements.txt`.

---

## Run

```bash
npm run dev
```

That single command starts the Vite dev server on `http://localhost:5173`.
There is **no separate backend process** — Python script execution is handled
by `vite-plugins/execute-plugin.js`, which serves the `/api/*` routes inside
the same port.

Console output you should see:

```
✅ Loaded environment variables from .env file
✅ Execute plugin loaded - Python scripts can run directly from frontend!
  VITE v6.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

---

## Running queries

From the UI:

- **Run all** — open the Metrics Dashboard sidebar button → runs every query in `src/components/queries-list/queries.js`.
- **Run selected** — same dashboard, tick the queries you want.
- **Run individual** — pick one query from the preset list and click ▶ Execute Python.

From the CLI (Docker-direct path):

```bash
cd running/Scripts
./run_all_scripts.sh        # bash
./run_all_scripts.ps1       # PowerShell
```

---

## Where results land

| Path | What |
|---|---|
| `results/<query_slug>.jsonl` | raw event stream from the query |
| `results/metrics/<query_slug>.json` | per-query metrics (latency, accuracy, throughput) |
| `results/plots/<query_slug>/` | five PNG plots per query |
| `results/metrics/benchmark_summary.csv` | one row per query — overall summary |
| `results/benchmark_simple_report.pdf` | final assembled report |

Naive queries use the bare slug (`car_brand_ford`); optimised variants are
prefixed and tagged (`optimized_car_brand_ford_r854`).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `jobmanager container not found` | `cd running/Docker && docker-compose -f env-compose.yml up -d` |
| Port 5173 already in use | Kill the process or change `server.port` in `vite.config.js` |
| `python` not found by execute-plugin | Either create a venv at `running/Topics/Cars/Data/venv/` or ensure `python` is on PATH |
| Empty `results/plots/` after a run | Confirm Docker stack is healthy: `docker ps` should show `jobmanager`, `taskmanager`, `kafka`, `zookeeper` |
