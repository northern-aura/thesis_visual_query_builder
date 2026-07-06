# ReactFlow Query Builder

A visual pipeline builder that compiles drag-and-drop graphs into PyFlink jobs and runs them against a local Flink + Kafka cluster, all from a single dev server.

For a one-page setup checklist see [QUICKSTART.md](./QUICKSTART.md).

---

## Architecture: Single-Port Execution

```
Frontend (React, port 5173)
    ↓ same port
Vite Plugin (Node.js, integrated)
    ↓ docker exec
Docker Container (jobmanager)
    ↓ flink run
PyFlink Job Execution
```

There is **no separate backend process**. All `/api/*` routes are served by
`vite-plugins/execute-plugin.js` from inside the Vite dev server.

---

## How It Works

### 1. Single command startup

```bash
npm run dev
```

Starts:
- Vite dev server on `localhost:5173`
- Execute plugin (integrated in same process)
- Auto-copies helper modules (`llm_call.py`) from `running/Scripts/` into `scripts/`

Console output:

```
✅ Execute plugin loaded - Python scripts can run directly from frontend!
📦 Copied 1 helper module(s): llm_call.py

  VITE v6.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

### 2. User builds a pipeline

- Visual node-based interface
- Drag and drop nodes (Kafka Source, Decode, Resize, LLM, etc.)
- Configure parameters for each node
- Create custom nodes with custom Python code

### 3. User clicks "Execute Python"

**Frontend:**
```javascript
1. generateDirectPython(nodes, edges) → Python code
2. POST /api/execute { script_content, script_name, project_name }
3. Opens ResultsPanel (bottom drawer)
4. SSE EventSource connects to /api/execute/{id}/stream
```

**Execute plugin:**
```javascript
1. Receives script content
2. Auto-replaces localhost:9092 → kafka:9093 (Docker fix)
3. Saves to scripts/exec_TIMESTAMP_HASH.py
4. Copies helper modules if needed
5. Executes: docker exec jobmanager flink run -py /scripts/exec_XXX.py
6. Streams output via Server-Sent Events
7. Saves logs to results/logs/exec_XXX.log
```

### 4. Job runs in Flink cluster

- Submits to existing Flink cluster (jobmanager + taskmanager)
- Reads from Kafka input topics
- Applies transformations (decode, resize, LLM inference, etc.)
- Writes results to Kafka output topics

### 5. Results

- Real-time output in ResultsPanel
- Status indicators, duration, exit code
- Download logs / stop execution

---

## File Structure

```
project/
├── src/
│   ├── components/
│   │   ├── custom-nodes/      Create custom nodes
│   │   ├── execution/         MetricsDashboard + ResultsPanel
│   │   ├── export/            Menu / Execute button
│   │   ├── nodes/             Node definitions and components
│   │   ├── queries-list/      queries.js — preset query graphs
│   │   └── sidebar/           Node palette
│   ├── helpers/export/        Python code generator + templates
│   └── services/              backendClient, sseClient
│
├── vite-plugins/
│   └── execute-plugin.js      Execution engine (the only plugin)
│
├── running/
│   ├── Docker/                Docker compose + Dockerfile
│   ├── Scripts/               Helper modules (auto-copied to scripts/)
│   └── Topics/
│       ├── Cars/              Cars dataset, queries, senders
│       └── Volleyball/        Volleyball dataset, queries, senders
│
├── volleyball_dataset/        Volleyball video frames (1.7 GB)
├── scripts/                   Project Python scripts (benchmarks, plots, eval)
├── results/                   Final outputs — see "Results" below
├── vite.config.js             Wires up execute-plugin
└── package.json               npm run dev = vite only
```

---

## Running queries

From the UI:

- **Run all** — Metrics Dashboard sidebar button → runs every preset query in `src/components/queries-list/queries.js`.
- **Run selected** — same dashboard, tick a subset.
- **Run individual** — pick one preset and click ▶ Execute Python.

From the CLI (Docker-direct path):

```bash
cd running/Scripts
./run_all_scripts.sh        # bash
./run_all_scripts.ps1       # PowerShell
```

---

## Results

| Path | Contents |
|---|---|
| `results/<query_slug>.jsonl` | raw event stream from the query |
| `results/metrics/<query_slug>.json` | per-query metrics (latency, accuracy, throughput) |
| `results/plots/<query_slug>/` | five PNGs: `accuracy_bar`, `e2e_timeline`, `llm_box`, `llm_timeline`, `operator_boxes` |
| `results/metrics/benchmark_summary.csv` | one row per query — overall summary |
| `results/metrics/cache_fill_accuracy_report.csv` | accuracy breakdown |
| `results/metrics/precision_recall_summary.csv` | per-query precision / recall / F1 (see methodology below) |
| `results/metrics/count_error_rollup.csv` | count-query errors incl. **signed count deviation** |
| `results/metrics/count_per_window_scores.csv` | per-window signed count scores |
| `results/metrics/all_queries_eval.csv` | compact all-queries view (fitting metric per query) |
| `results/plots/benchmark_summary/` | aggregate cross-query charts |
| `results/benchmark_simple_report.pdf` | final assembled report |
| `results/precision_recall_report.pdf` | precision / recall / F1 across all query plans |

Naming convention:
- **Naive** — bare slug, e.g. `car_brand_ford`, `most_popular_color`, `dig_set_events_window`
- **Optimised** — `optimized_<slug>_<resolution>`, e.g. `optimized_car_brand_ford_r854`, `optimized_jump_spike_events_r854`
- **Resize / skip-frame variants** — `_resize`, `_skip_10` suffix
- **Stacked optimisation** — color filter + resize + skip on one pipeline, e.g. `optimized_red_plate_lookup_cfred_r1120_s3`
- **Per-case studies** — `case_*` prefix

Heavy intermediate files (browser PDF profiles, log dumps, cache fill backups) are gitignored under `results/` — they regenerate on a fresh run.

### Evaluation metrics & methodology

The single "overall accuracy" per query was replaced with the metric that fits each
query's answer shape. Regenerate everything with:

```bash
python3 scripts/make_precision_recall_report.py   # precision/recall/F1 + PDF
python3 scripts/make_count_error_rollup.py         # count errors + signed deviation
```

| Metric family | Applies to | Scored as |
|---|---|---|
| detection (frame) | single-target "is X present" car queries | per-frame TP/FP/FN |
| retrieval (set) | multi-value brand/colour/plate queries | distinct-value set TP/FP/FN |
| event (window) | volleyball event-presence queries | per-window TP/FP/FN |
| single-answer | most-popular / top-action / motion | exact match (P/R n/a) |
| count | spike/set/block counts | **signed count deviation** = `(pred − truth) / (pred + truth) × 100` |

Signed count deviation is bounded to ±100 %, sign-preserving (+ = over-count, − = under-count),
so it separates over- from under-counting where absolute error and closeness cannot.
The stacked-optimisation run `Optimized Red Plate Lookup (CFred+R1120+S3)` is scored under
`cars_optimized` in the precision/recall report as the combined color-filter + resize + skip case study.

---

## API endpoints (all on port 5173)

### `POST /api/execute`
Start script execution.

```json
{
  "script_name": "pipeline.py",
  "script_content": "# Python code here",
  "project_name": "My Project"
}
```

Response:
```json
{
  "execution_id": "exec_1764749821563_2152",
  "status": "queued",
  "stream_url": "/api/execute/exec_1764749821563_2152/stream"
}
```

### `GET /api/execute/:id/stream`
Server-Sent Events stream of execution output.

### `GET /api/executions`
List execution history (last 50).

### `GET /api/executions/:id/logs`
Download full logs for an execution.

### `DELETE /api/executions/:id`
Stop a running execution.

---

## Docker

### Required containers

```bash
docker ps
```

Should list: `jobmanager`, `taskmanager`, `kafka`, `zookeeper`.

### Start

```bash
cd running/Docker
docker-compose -f env-compose.yml up -d
cd ../..
```

### Volume mounts

`env-compose.yml` mounts `../../scripts:/scripts` so the jobmanager container can read generated scripts.

### Network addressing

| | Inside containers | From host |
|---|---|---|
| Kafka | `kafka:9093` | `localhost:9092` |
| Flink UI | — | `localhost:8082` |
| Zookeeper | `zookeeper:2181` | — |

The execute plugin auto-replaces `localhost:9092` → `kafka:9093` before submission.

---

## Technical details

### Execute plugin (`vite-plugins/execute-plugin.js`)

1. **Middleware integration** — adds API endpoints to Vite dev server
2. **Helper module auto-copy** — `running/Scripts/*.py` → `scripts/`
3. **Docker network fix** — `localhost:9092` → `kafka:9093`
4. **Flink submission** — `flink run -py` (not `python script.py`)
5. **SSE streaming** — real-time output via Server-Sent Events
6. **Log persistence** — `results/logs/exec_XXX.log`
7. **Process management** — tracks running executions, supports cancellation

Submission command:
```javascript
spawn('docker', ['exec', 'jobmanager', 'flink', 'run', '-py', `/scripts/${execution_id}.py`])
```

### Why `flink run` and not `python`?

`python script.py` tries to start a new local Flink cluster and fails without proper Java setup. `flink run -py` submits the job to the existing cluster — the proper way.

### Code generation (`src/helpers/export/directPythonExport.js`)

1. Topologically sort nodes (dependencies first)
2. Generate Python imports
3. Add custom node classes
4. Create Flink environment
5. Build Kafka source
6. Chain map/filter operations
7. Add Kafka sink
8. Generate `env.execute()` call

Example output:
```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource

env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = (KafkaSource.builder()
    .set_bootstrap_servers("localhost:9092")
    .set_topics("input-topic")
    .build())

stream = env.from_source(kafka_source, watermark_strategy, "Source")
stream_1 = stream.map(MapDecodeStream())
stream_2 = stream_1.map(MapResizeImage(320, 640, 180, 360))
stream_2.sink_to(kafka_sink)
env.execute("My Pipeline")
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection error` in ResultsPanel | Docker stack is down: `cd running/Docker && docker-compose -f env-compose.yml up -d` |
| Flink job fails with Kafka timeout | Topics missing: `docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic <name>` |
| `No module named 'llm_call'` | Restart `npm run dev` so helpers re-copy from `running/Scripts/` |
| `docker: command not found` (WSL) | Docker Desktop → Settings → Resources → WSL Integration → enable for your distro, restart shell |
| Empty `results/plots/` after a run | `docker ps` should show all four containers; if not, restart the stack |
| Long-running jobs disappear from UI | Jobs run detached on Flink — check `localhost:8082` for status |

---

## Configuration

### Ports
- **Frontend / API:** 5173 (Vite)
- **Flink UI:** 8082 (jobmanager)
- **Kafka:** 9092 (host) / 9093 (internal)
- **Zookeeper:** 2181

### Directories
- **Scripts:** `scripts/` — generated Python scripts
- **Results:** `results/` — logs, metrics, plots, final PDF
- **Helpers:** `running/Scripts/` — source for auto-copied modules

---

## Getting help

**Check logs:**
1. Terminal — execution logs with `[Execute]` prefix
2. Browser console (F12) — frontend errors
3. Flink Web UI (`localhost:8082`) — job errors
4. `results/logs/exec_XXX.log` — full execution logs

**Common commands:**
```bash
# Restart
Ctrl+C
npm run dev

# Docker
docker ps
docker logs jobmanager
docker logs kafka

# Kafka
docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Inspect a run
ls scripts/
cat results/logs/exec_XXXXX.log
```

---

Built with React + ReactFlow, Vite, Apache Flink/PyFlink, Apache Kafka, Docker, Node.js.
