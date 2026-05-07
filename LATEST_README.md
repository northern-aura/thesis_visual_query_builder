# ReactFlow Query Builder - Latest Implementation

**Last Updated:** December 3, 2025

---

## 🎯 Current Architecture: Simplified Single-Port Execution

### What We Built

A **streamlined execution system** that runs PyFlink jobs directly from the web interface without needing a separate Python backend.

**Now:**
```
Frontend (React, port 5173)
    ↓ Same Port
Vite Plugin (Node.js, integrated)
    ↓ Docker Exec
Docker Container (jobmanager)
    ↓ Flink Run
PyFlink Job Execution
```

---

## 🔧 How It Works

### 1. Single Command Startup
```bash
npm run dev
```

**What starts:**
- ✅ Vite dev server on `localhost:5173`
- ✅ Execute plugin (integrated in same process)
- ✅ Auto-copies helper modules (`llm_call.py`) to scripts directory

**Console output:**
```
✅ Execute plugin loaded - Python scripts can run directly from frontend!
📦 Copied 1 helper module(s): llm_call.py

  VITE v6.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

### 2. User Builds Pipeline
- Visual node-based interface
- Drag and drop nodes (Kafka Source, Decode, Resize, LLM, etc.)
- Configure parameters for each node
- Create custom nodes with custom Python code

### 3. User Clicks "Execute Python"
**Frontend flow:**
```javascript
1. generateDirectPython(nodes, edges) → Python code
2. POST /api/execute { script_content, script_name, project_name }
3. Opens ResultsPanel (bottom drawer)
4. SSE EventSource connects to /api/execute/{id}/stream
```

**Backend (Vite Plugin) flow:**
```javascript
1. Receives script content
2. Auto-replaces localhost:9092 → kafka:9093 (Docker fix)
3. Saves to scripts/exec_TIMESTAMP_HASH.py
4. Copies helper modules if needed
5. Executes: docker exec jobmanager flink run -py /scripts/exec_XXX.py
6. Streams output via Server-Sent Events
7. Saves logs to results/exec_XXX.log
```

### 4. Job Runs in Flink Cluster
- Submits to existing Flink cluster (jobmanager + taskmanager)
- Processes data from Kafka input topics
- Applies transformations (decode, resize, LLM inference, etc.)
- Writes results to Kafka output topics

### 5. User Sees Results
- Real-time output in ResultsPanel
- Execution status (running, completed, failed)
- Duration and exit code
- Download logs option
- Stop execution option

---

## 📁 File Structure

```
project/
├── src/
│   ├── components/
│   │   ├── custom-nodes/
│   │   │   ├── CustomNodeModal.jsx      # Create custom nodes
│   │   │   └── CustomNodes.css
│   │   ├── execution/
│   │   │   ├── ResultsPanel.jsx         # Real-time results display
│   │   │   └── ResultsPanel.css
│   │   ├── export/
│   │   │   └── exportButton.jsx         # Menu with Execute button
│   │   ├── nodes/
│   │   │   ├── defaultNodes.ts          # Node definitions
│   │   │   └── Nodes.jsx                # Node components
│   │   └── sidebar/
│   │       └── Sidebar.jsx              # Node palette
│   ├── helpers/export/
│   │   ├── directPythonExport.js        # Python code generator
│   │   └── Methodtemplates.js           # Python templates
│   └── services/
│       ├── backendClient.js             # API client
│       └── sseClient.js                 # SSE streaming client
│
├── vite-plugins/
│   ├── execute-plugin.js                # ⭐ NEW: Execution engine
│   └── backend-launcher.js              # OLD: No longer used
│
├── backend/                             # OLD: Python FastAPI (not used)
│   └── ...
│
├── running/
│   ├── Docker/
│   │   ├── env-compose.yml              # Docker Compose config
│   │   └── pyflink.Dockerfile
│   └── Scripts/
│       └── llm_call.py                  # Helper module (auto-copied)
│
├── scripts/                             # Generated execution scripts
│   ├── exec_XXXXX.py
│   └── llm_call.py                      # Auto-copied helper
│
├── results/                             # Execution results
│   ├── exec_XXXXX.log                   # Full logs
│   └── exec_XXXXX_results.txt           # Output
│
├── vite.config.js                       # Uses execute-plugin
└── package.json                         # npm run dev = vite only
```

---

## 🔌 API Endpoints (All on Port 5173)

### POST `/api/execute`
Start script execution

**Request:**
```json
{
  "script_name": "pipeline.py",
  "script_content": "# Full Python code here",
  "project_name": "My Project"
}
```

**Response:**
```json
{
  "execution_id": "exec_1764749821563_2152",
  "status": "queued",
  "stream_url": "/api/execute/exec_1764749821563_2152/stream"
}
```

### GET `/api/execute/:id/stream`
Server-Sent Events stream of execution output

**Events:**
```
data: {"type":"started","execution_id":"exec_XXX","timestamp":"..."}
data: {"type":"info","data":"Submitting job to Flink cluster...","timestamp":"..."}
data: {"type":"stdout","data":"Job has been submitted with JobID ...","timestamp":"..."}
data: {"type":"completed","exit_code":0,"duration_seconds":1.23,"timestamp":"..."}
```

### GET `/api/executions`
List execution history (last 50)

### GET `/api/executions/:id/logs`
Download full logs for an execution

### DELETE `/api/executions/:id`
Stop a running execution

---

## 🐳 Docker Integration

### Required Containers
```bash
docker ps
```

Should show:
- `jobmanager` - Flink job manager
- `taskmanager` - Flink task manager
- `kafka` - Kafka message broker
- `zookeeper` - Kafka coordination

### Start Containers
```bash
cd running/Docker
docker-compose -f env-compose.yml up -d
cd ../..
```

### Volume Mounts
The `env-compose.yml` mounts:
```yaml
volumes:
  - ../../scripts:/scripts  # Scripts accessible in container
```

This allows the jobmanager container to access generated scripts.

### Network Addressing
**Inside Docker containers:**
- Kafka: `kafka:9093` (internal network)
- Zookeeper: `zookeeper:2181`

**From host machine:**
- Kafka: `localhost:9092`
- Flink UI: `localhost:8082`

**Auto-replacement:** The execute plugin automatically converts `localhost:9092` → `kafka:9093` before execution.

---

## 🚀 Features

### ✅ Visual Pipeline Builder
- Drag and drop interface
- Pre-built nodes: Kafka Source/Sink, Decode, Resize, LLM, Grayscale, etc.
- Connect nodes to build data pipelines
- Real-time parameter configuration

### ✅ Custom Nodes
- Click "Custom" card (gear icon) in sidebar
- Define: label, icon, color, parameters, Python class, method
- Save and reuse like default nodes
- Export custom nodes as JSON

### ✅ Python Code Generation
- Converts visual pipeline to PyFlink code
- Supports all node types and custom nodes
- Generates proper Flink streaming code
- Includes imports, classes, and execution logic

### ✅ Script Execution
- One-click execution from UI
- Runs in Flink cluster (proper distributed execution)
- Real-time output streaming
- Status tracking (running, completed, failed)
- Duration and exit code reporting

### ✅ Results Management
- Real-time results in bottom drawer panel
- Color-coded status indicators
- Auto-scroll with pause/resume
- Download logs
- Stop running executions

### ✅ Export Options
- Export pipeline as JSON
- Export as Python script
- Batch export (10 variations)
- Export custom nodes
- Screenshot capture

---

## 🔍 How to Use

### 1. Start the Application
```bash
# First time only - install dependencies
npm install

# Start everything
npm run dev
```

Open: http://localhost:5173

### 2. Build Your Pipeline

**Add Source:**
- Drag "Kafka Source" from sidebar
- Configure: Server (`localhost:9092`), Group ID, Topic

**Add Processing:**
- Drag nodes: Decode, Resize, LLM, etc.
- Connect nodes by dragging from output to input
- Configure parameters for each node

**Add Sink:**
- Drag "Kafka Sink"
- Configure: Server (`localhost:9092`), Topic

### 3. Execute

**Click Menu (bottom right) → ▶ Execute Python**

**What happens:**
1. Pipeline converted to Python code
2. Script saved to `scripts/` directory
3. Helper modules copied automatically
4. `localhost:9092` → `kafka:9093` (Docker fix applied)
5. Job submitted to Flink: `docker exec jobmanager flink run -py /scripts/exec_XXX.py`
6. Results Panel opens at bottom
7. Real-time output streams to UI

**Monitor:**
- ResultsPanel shows live output
- Terminal shows execution logs: `[Execute] ▶️  Starting: exec_XXX`
- Flink Web UI: http://localhost:8082 (see job status, metrics)

### 4. Check Results

**In UI:**
- ResultsPanel shows stdout/stderr
- Status indicator (green = success, red = failed, yellow = running)
- Duration and exit code displayed

**In Files:**
- `scripts/exec_XXX.py` - Generated script
- `results/exec_XXX.log` - Full execution logs
- `results/exec_XXX_results.txt` - Output data

**In Kafka:**
- Results written to output topic
- Use Kafka consumer to read:
```bash
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic YOUR_OUTPUT_TOPIC \
  --from-beginning
```

---

## 🛠️ Technical Details

### Execute Plugin Implementation

**File:** `vite-plugins/execute-plugin.js`

**Key features:**
1. **Middleware Integration:** Adds API endpoints to Vite dev server
2. **Helper Module Auto-Copy:** Copies `.py` files from `running/Scripts/` to `scripts/`
3. **Docker Network Fix:** Replaces `localhost:9092` with `kafka:9093`
4. **Flink Submission:** Uses `flink run -py` for proper job submission
5. **SSE Streaming:** Real-time output via Server-Sent Events
6. **Log Persistence:** Saves logs to files for later retrieval
7. **Process Management:** Tracks running executions, supports cancellation

**Execution command:**
```javascript
spawn('docker', [
  'exec',
  'jobmanager',
  'flink',
  'run',
  '-py',
  `/scripts/${execution_id}.py`
])
```

### Why Flink Run?

**Not:** `python script.py` (tries to start new cluster, fails)
**Yes:** `flink run -py script.py` (submits to existing cluster)

This is the **proper way** to submit jobs to a Flink cluster.

### Code Generation

**File:** `src/helpers/export/directPythonExport.js`

**Process:**
1. Topologically sort nodes (dependencies first)
2. Generate Python imports
3. Add custom node classes
4. Create Flink environment
5. Build Kafka source
6. Chain map/filter operations
7. Add Kafka sink
8. Generate `env.execute()` call

**Example generated code:**
```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource

env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = KafkaSource.builder()\
  .set_bootstrap_servers("localhost:9092")\
  .set_topics("input-topic")\
  .build()

stream = env.from_source(kafka_source, watermark_strategy, "Source")
stream_1 = stream.map(MapDecodeStream())
stream_2 = stream_1.map(MapResizeImage(320, 640, 180, 360))

stream_2.sink_to(kafka_sink)
env.execute("My Pipeline")
```

---

## 🐛 Troubleshooting

### Execution Fails: "Connection error"

**Symptoms:** ResultsPanel shows "Connection error" immediately

**Causes:**
1. Docker containers not running
2. SSE connection failed
3. Script has syntax errors

**Fix:**
```bash
# Check Docker containers
docker ps

# Should see: jobmanager, taskmanager, kafka, zookeeper
# If not running:
cd running/Docker
docker-compose -f env-compose.yml up -d
```

### Job Failed: "Timed out waiting for a node assignment"

**Symptoms:** Flink Web UI shows job failed with Kafka timeout

**Cause:** Kafka not accessible or topics don't exist

**Fix:**
```bash
# Check Kafka is running
docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Create topics if needed
docker exec kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create --topic input-topic

docker exec kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create --topic output-topic
```

### Module Not Found: "No module named 'llm_call'"

**Symptoms:** Script fails with import error

**Cause:** Helper modules not copied

**Fix:**
Restart dev server - helper modules auto-copy on startup:
```bash
Ctrl+C
npm run dev
```

Look for: `📦 Copied 1 helper module(s): llm_call.py`

### Docker Not Available

**Symptoms:** `docker: command not found` or `Docker not available`

**On Windows with WSL2:**
1. Open Docker Desktop
2. Go to Settings → Resources → WSL Integration
3. Enable integration with your WSL distro
4. Restart WSL terminal

**Test:**
```bash
docker ps
```

Should show container list (even if empty).

---

## 📊 Monitoring

### Flink Web UI
**URL:** http://localhost:8082

**Features:**
- Running jobs list
- Job details (start time, duration, status)
- Task metrics and parallelism
- JobManager/TaskManager status
- Log files

### Terminal Logs
**Execution logs:**
```
[Execute] 📝 Script saved: exec_1764749821563_2152
[Execute] ▶️  Starting: exec_1764749821563_2152
[Execute] [exec_1764749821563_2152] Job has been submitted with JobID ...
[Execute] ✅ Finished: exec_1764749821563_2152 (exit code: 0, duration: 5.32s)
```

### Kafka Topics
**Monitor input:**
```bash
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic input-topic
```

**Monitor output:**
```bash
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic output-topic
```

---

## 🔄 What Changed from Original

### Removed
- ❌ Python FastAPI backend (separate process on port 3001)
- ❌ Backend launcher plugin
- ❌ CORS proxy configuration
- ❌ npm-run-all parallel script execution
- ❌ Complex SSE connection through proxy

### Added
- ✅ Execute plugin (integrated in Vite)
- ✅ Single-port architecture (everything on 5173)
- ✅ Auto-copy helper modules
- ✅ Auto-replace Docker network addresses
- ✅ Proper Flink job submission (`flink run`)
- ✅ Simplified startup (`npm run dev` = just Vite)

### Modified
- 📝 `vite.config.js` - Uses execute plugin instead of backend launcher
- 📝 `package.json` - Changed dev script to just `vite`
- 📝 Frontend components - Unchanged (same API contracts)

---

## 🎓 Key Learnings

### 1. Docker Networking
When running inside Docker containers, `localhost` refers to the container itself, not the host or other containers. Use container names: `kafka:9093` not `localhost:9092`.

### 2. PyFlink Execution
PyFlink scripts must be submitted to a Flink cluster via `flink run`, not executed directly with `python`. Direct execution tries to start a new local cluster, which fails without proper Java setup.

### 3. Helper Modules
Generated scripts often import helper modules (like `llm_call.py`). These must be in the same directory as the script or in Python's path. Auto-copying solves this.

### 4. SSE Streaming
Server-Sent Events provide one-way real-time streaming from server to client. Perfect for execution logs. Format: `data: {JSON}\n\n`

### 5. Node.js Child Processes
Using `spawn()` allows Node.js to execute external commands (like Docker) and stream output in real-time. `stdio: ['ignore', 'pipe', 'pipe']` captures stdout/stderr.

---

## 🚦 Current Status

### ✅ Working
- Visual pipeline builder
- Custom nodes creation
- Python code generation
- Script execution submission
- Flink job submission
- Real-time output streaming (submission logs)
- Results panel UI
- Helper module auto-copy
- Docker network address conversion
- Export functionality

### ⚠️ In Progress
- Long-running job monitoring (jobs run detached)
- Kafka result consumption in UI
- Job status tracking after submission

### 🔮 Future Enhancements
- Attached mode execution (see live processing output)
- Kafka consumer integration (show results in UI)
- Job cancellation (kill Flink jobs)
- Historical execution viewer
- Pipeline templates
- Parameter presets

---

## 📝 Configuration

### Ports
- **Frontend/API:** 5173 (Vite dev server)
- **Flink UI:** 8082 (jobmanager)
- **Kafka:** 9092 (host), 9093 (Docker internal)
- **Zookeeper:** 2181

### Directories
- **Scripts:** `scripts/` - Generated Python scripts
- **Results:** `results/` - Execution logs and output
- **Helpers:** `running/Scripts/` - Source for helper modules

### Docker
- **Compose file:** `running/Docker/env-compose.yml`
- **Network:** Default bridge network
- **Volumes:** Scripts directory mounted to `/scripts` in containers

---

## 🆘 Getting Help

**Check Logs:**
1. Terminal - Execution logs with `[Execute]` prefix
2. Browser Console (F12) - Frontend errors
3. Flink Web UI - Job errors and logs
4. `results/exec_XXX.log` - Full execution logs

**Common Commands:**
```bash
# Restart everything
Ctrl+C
npm run dev

# Check Docker
docker ps
docker logs jobmanager
docker logs kafka

# Check Kafka topics
docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Check scripts
ls scripts/
cat scripts/exec_XXXXX.py

# Check results
ls results/
cat results/exec_XXXXX.log
```

---

## 📄 License & Credits

Built with:
- React + ReactFlow (visual pipeline builder)
- Vite (dev server and build tool)
- Apache Flink + PyFlink (stream processing)
- Apache Kafka (message streaming)
- Docker (containerization)
- Node.js (backend execution)

---

**End of Documentation**

*For latest updates, check the git log or CHANGELOG.md*
